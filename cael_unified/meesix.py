"""Mr. Meesix: one short-lived agent per task, at most six at a time. Each takes one task, finishes it, and vanishes.

Mr. Meesix is also the team that answers each task (team.py): the Planner, Solver, Generalist, Researchers, Critic,
Counsellor and Editor of a task are Mr. Meesix agents too, each with that one job.

A message is cut into its separate tasks ("What's 15% of 80? Also, who painted the Mona Lisa?" is two). Every task gets
its own Meesix. An agent holds nothing but its task: it tries the exact solvers first (arithmetic word problems, logic),
then hands the task to the full CAEL pipeline, returns its answer, and is gone. Nothing is kept between agents, so one
task's wording cannot leak into another's answer. With more than six tasks the rest wait for a free place.

No model is involved: an agent is a plain function call on a worker thread. The agents of one message
work at the same time: the pipeline is safe to call from several threads (the public worker already does), so a
message with three look-ups waits for the slowest one, not for the sum of the three.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import solve_logic, solve_math

LIMIT = 6                       # agents alive at one time
ALIVE = set()                   # names of the agents working right now (empty again when a message is done)
LAST = []                       # what the agents of the last message did: (name, task, route, seconds)
_COUNT = threading.Lock()
INSIDE = threading.local()      # .task is True on a thread that is one of the six task agents (team.py then adds no agent of its own)
PRONOUN = re.compile(r"(?i)\b(?:it|its|they|them|their|that|this|those|these|he|she|him|her|his|one|ones|there|then|same)\b")
LEAD = re.compile(r"(?i)^\s*(?:also|and|oh|plus|next|then|second(?:ly)?|third(?:ly)?|finally|lastly|one more(?: thing)?|another (?:thing|question)|"
                  r"by the way|btw|separately|unrelated|on another note|last (?:one|question)|quick question|while (?:i'm|you're) at it)\b[,:;.!\s-]*")
OPTION = re.compile(r'(?m)^\s*[A-D][).]\s+\S')
WEAK = re.compile(r'fallback|unknown|clarify|unsupported|checked-none|insufficient|failed|last-resort')
FOLLOW = re.compile(r"(?i)^\s*(?:and|or|but|so)?\s*(?:what about|how about|what if|and if|and for|and in|and at|and with|why is that|why not|how so|really)\b")
ASK = re.compile(r"(?i)\b(?:what|who|whom|whose|when|where|why|how|which|is|are|was|were|do|does|did|can|could|should|would|will|"
                 r"tell me|explain|give me|list|name|write|define|describe|calculate|work out|convert|translate)\b")


def specialists(messages):
    """The exact solvers, in order. A dict reply, or None when none of them is sure."""
    # A question with lettered options (A) ... B) ...) belongs to the multiple-choice path, which picks
    # one of the options. The arithmetic solver read chains like "Every kind_1 is a kind_2." as sums
    # and replied with a number, so no option was chosen at all.
    if len(OPTION.findall(messages[-1].get('content') or '')) >= 2:
        return None
    # The established sharing and rates helpers keep their problems: they ask "whole items or fractions?" and refuse
    # unsafe input, and their follow-ups depend on their own replies.
    from . import helper_groups, helper_rates
    for helper in (helper_groups, helper_rates):
        try:
            if helper.reply(messages[-1]['content'], messages) is not None:
                return None
        except Exception:
            pass
    try:        # the plain "has / receives / loses" ledger keeps its state for "why?" and "Add: ..." follow-ups
        from . import helper_quantities
        kept = helper_quantities.reply(messages[-1]['content'], messages)
        if kept is not None and kept.get('route') == 'helper/quantity':
            return None
    except Exception:
        pass
    for solver in (solve_math, solve_logic):
        try:
            got = solver.respond(messages)
        except Exception:
            got = None
        if got:
            return got
    return None


def tasks_of(text):
    """The separate tasks in one message: each question with the statements that lead up to it."""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(])|\n+', text.strip()) if s.strip()]
    groups, held = [], []
    for s in sents:
        held.append(s)
        if s.endswith('?'):
            groups.append(held); held = []
    if len(groups) < 2:
        return [text]
    if held:                                    # closing remarks belong to the last question
        groups[-1] += held
    out = []
    for i, g in enumerate(groups):
        question = LEAD.sub('', g[-1]) if i else g[-1]
        body = ' '.join(g[:-1] + [question]).strip()
        core = LEAD.sub('', question)
        words = re.findall(r"[A-Za-z']+", core)
        # a question that leans on what came before ("And for 18?", "Why is that?") is not a task of its own
        leans = LEAD.match(question) is not None and len(words) < 4 or FOLLOW.match(g[-1]) is not None
        if i and (len(words) < 2 or leans or not ASK.search(core) or (PRONOUN.search(core) and len(g) == 1)):
            return [text]
        out.append(body[0].upper() + body[1:] if body else body)
    return out


class Meesix:
    """One agent for one task. `run` is its whole life."""

    def __init__(self, number, task, context=''):
        self.name = f'Meesix-{number}'
        self.task = task
        self.context = context          # what the message said before this task, used only if the task alone is not enough

    def run(self, history, engine, options):
        started = time.perf_counter()
        with _COUNT:
            ALIVE.add(self.name)
        try:
            from . import team          # each task gets the whole team: solver, generalist, researchers, critic
            INSIDE.task = True
            messages = history + [dict(role='user', content=self.task)]
            result = team.single(messages, engine, options)
            if self.context and WEAK.search(str(result.get('route', ''))):
                # the task leaned on the earlier part of the message after all: once more, with that part in front
                again = history + [dict(role='user', content=self.context + ' ' + self.task)]
                retry = team.single(again, engine, options)
                if not WEAK.search(str(retry.get('route', ''))):
                    result = retry
            return dict(result, agent=self.name, task=self.task, seconds=round(time.perf_counter() - started, 3))
        finally:
            INSIDE.task = False
            with _COUNT:
                ALIVE.discard(self.name)        # the task is done: the agent is gone


def run(messages, engine, **options):
    """Answer the last user message with task agents. None when it is a single task no exact solver takes
    (the normal pipeline then answers it as before)."""
    history, last = messages[:-1], messages[-1]['content']
    tasks = tasks_of(last)
    del LAST[:]
    if len(tasks) == 1:
        started = time.perf_counter()
        result = specialists(messages)
        if result is not None:
            LAST.append(('Meesix-1', last, result.get('route'), round(time.perf_counter() - started, 3)))
            return dict(result, agents=1)
        return None
    agents, said = [], ''
    for i, t in enumerate(tasks):
        agents.append(Meesix(i + 1, t, said.strip()))
        said += ' ' + ' '.join(x for x in re.split(r'(?<=[.!?])\s+', t) if not x.endswith('?'))
    from . import team as _team
    _team.warm()                                # shared modules and databases loaded once, not six times at once
    with ThreadPoolExecutor(max_workers=LIMIT) as pool:
        futures = [pool.submit(a.run, history, engine, options) for a in agents]
        results = []
        for a, f in zip(agents, futures):
            try:
                results.append(f.result())
            except Exception as exc:
                results.append(dict(route='chat/meesix-failed', response='I could not finish this part.', agent=a.name, task=a.task,
                                    seconds=0.0, error=repr(exc)))
    del agents                                  # every agent has finished and is dropped
    LAST.extend((r['agent'], r['task'], r.get('route'), r['seconds']) for r in results)
    parts = []
    for r in results:
        question = re.split(r'(?<=[.!?])\s+', r['task'])[-1]
        parts.append(f"**{question}**\n{str(r.get('response', '')).strip()}")
    sources = [s for r in results for s in (r.get('sources') or [])]
    reply = dict(route='chat/meesix', response='\n\n'.join(parts), agents=len(results),
                 parts=[dict(agent=r['agent'], task=r['task'], route=r.get('route'), seconds=r['seconds']) for r in results],
                 details='; '.join(f"{r['agent']}: {r.get('route')} in {r['seconds']} s" for r in results))
    if sources:
        reply['sources'] = sources
    return reply


def unfold(messages):
    """"My dog is called Rex. What is my dog called?" in one message: the statements as an earlier turn, the question as
    the turn to answer. None when the last message is not statements followed by one question."""
    sents = [x.strip() for x in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"(])', messages[-1]['content'].strip()) if x.strip()]
    if len(sents) < 2 or not sents[-1].endswith('?') or any(x.endswith('?') for x in sents[:-1]):
        return None
    return messages[:-1] + [dict(role='user', content=' '.join(sents[:-1])), dict(role='assistant', content='Got it.'),
                            dict(role='user', content=sents[-1])]
