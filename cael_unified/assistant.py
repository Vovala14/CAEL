"""Shared chat/helper/emoji/photo interface for one CAEL model bundle."""
import json
from pathlib import Path
import os
import re
import secrets
import threading

from .bundle import ROOT, digest, open_bundle
from .helper import calculate
from . import smalltalk
from .promptgen import is_prompt_request

# The whole open chat window is sent with every request so nothing said in it is forgotten.
MAX_MESSAGES = 1000
# Replies that mean "I could not answer"; for a factual question these trigger the web search (web_search.py).
WEB_FALLBACK_ROUTES = frozenset({'chat/talk-unsure', 'chat/cannot-answer', 'chat/web-not-found', 'chat/web-answer-not-found',
                                 'chat/web-ambiguous', 'chat/web-unavailable', 'chat/local-other', 'chat/local-define',
                                 'chat/local-clarify', 'chat/local-unknown', 'chat/local-howto', 'chat/factual-clarify'})
MAX_CHARACTERS = 400_000
IMAGE = re.compile(r'\b(?:draw|paint|sketch|render)\b|\b(?:make|create|generate|show|give)\b.{0,45}\b(?:image|picture|photo|portrait|pic|illustration)s?\b', re.I)
CODE = re.compile(r'\b(?:python|javascript|code|function|script|program|api|resize|crop|compress|matplotlib|pillow|opencv)\b', re.I)
HOWTO = re.compile(r'^\s*(?:how|why|what is|what are|explain)\b', re.I)
STORY_REQUEST = re.compile(r'(?i)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:tell|write|create|make|generate|give)\b.{0,65}\b(?:story|tale|fable)\b')


def choice_problem(text):
    matches=list(re.finditer(r'(?m)^\s*([A-D])[.)]\s+(.+?)\s*$',text))
    if not 2<=len(matches)<=4 or [m[1] for m in matches]!=list('ABCD'[:len(matches)]):
        # The web box is one line: "Which is a mammal? A) shark B) whale C) trout D) tuna".
        matches=list(re.finditer(r'(?<![\w])([A-D])[.)]\s+(.+?)(?=\s+[A-D][.)]\s+|\s*$)',text))
        if not 2<=len(matches)<=4 or [m[1] for m in matches]!=list('ABCD'[:len(matches)]):
            return None
    context=text[:matches[0].start()].strip()
    # Three or more A-D options are a multiple-choice question even in continuation style
    # ("It ends at A) 3:55 B) 4:05 C) 3:45"); with two, a question cue is still required.
    if not context or (len(matches)<3 and not re.search(r'(?i)\b(?:choose|select|which|question|answer|continuation)\b|\?',context)):
        return None
    if text[matches[-1].end():].strip():
        return None
    # Strip only a standalone output-format instruction, never story premises.
    context=re.sub(r'(?im)^Choose the correct continuation\. Reply with only A, B, C, or D\.\s*','',context).strip()
    return context,[m[2] for m in matches]


def route_request(text, mode='auto'):
    if mode not in ('auto', 'chat', 'emoji', 'image', 'prompt', 'story'):
        raise ValueError('Unknown assistant mode')
    if mode in ('auto','chat'):
        if is_prompt_request(text):
            return 'prompt'
        if STORY_REQUEST.search(text) and not CODE.search(text):
            return 'story'
    if mode != 'auto':
        return mode
    if choice_problem(text):
        return 'chat'
    if not CODE.search(text) and not HOWTO.search(text):
        if re.search(r'\bemojis?\b', text, re.I):
            return 'emoji'
        if IMAGE.search(text):
            return 'image'
        if re.search(r'\b(?:make|create|generate|show)\b', text, re.I):
            from cael_image.general_curriculum import curriculum
            if any(re.search(r'\b' + re.escape(w) + r'\b', text, re.I) for _, words in curriculum('expanded').values() for w in words):
                return 'image'
    return 'chat'


def picture_reply(message):
    return message.get('role') == 'assistant' and message['content'].startswith('Created ') and ' image' in message['content'][:60]


def new_picture_request(text):
    """'make a portrait of a man' is a new picture even right after one; 'make it blue' or 'draw it again' is not."""
    return bool(IMAGE.search(text)) and not re.search(r'(?i)\b(?:it|them|that|again|same|instead)\b', text)


def picture_follow_up(messages):
    """'make it blue' right after a picture: an edit of that picture, not a chat message."""
    from cael_image.scene import is_edit
    text = messages[-1]['content']
    return len(messages) >= 3 and picture_reply(messages[-2]) and is_edit(text) and not new_picture_request(text)


class Assistant:
    def __init__(self, bundle=None, output_root=None, language_checkpoint=None):
        self.root, self.manifest = open_bundle(bundle)
        self.output_root = Path(output_root or ROOT / 'outputs' / 'unified').resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._emoji = self._image = self._chat = self._portrait = None
        self._portrait_synthetic = None
        self._prompt = None
        self._reasoning = None
        self._language = None
        self._language_checkpoint = language_checkpoint
        from .facts import FactLookup
        self._facts = FactLookup()
        self._lock = threading.RLock()
        self._plan_context = threading.local()

    def picture_in_chat(self, text, messages, seed):
        """Chat mode cannot draw, so hand over a ready image prompt and say where to use it."""
        from .vynly import VynlyHelp
        with self._lock:
            if self._prompt is None:
                from .promptgen import PromptGenerator
                self._prompt = PromptGenerator()
            made = self._prompt.respond(text, seed, forced=True, default_kind='image')
        prompt = (made or {}).get('response', '').split('\n', 1)[-1].strip() if made and made.get('route') == 'chat/prompt-image' else ''
        if VynlyHelp.flagged(messages):
            # The vynly.co widget shows plain text, so no Markdown here.
            where = ('I can\'t draw pictures in this chat, but you can make one on Vynly with Generate (vynly.co/generate). '
                     'Here is a prompt to paste there:')
            after = 'Want it in a different style or setting? Tell me, or use the Prompt helper tab.'
            if prompt:
                return dict(route='chat/picture-in-chat', response=f'{where}\n\n{prompt}\n\n{after}', sources=[],
                            details='Chat mode has no picture engine, so CAEL\'s prompt helper wrote an image prompt instead (rule-based, non-neural).')
        else:
            where = 'Picture drawing is off in chat mode. Switch to Auto or Picture mode and ask again, or use this prompt in any image tool:'
            if self.manifest.get('profile') == 'no-images':
                where = 'This bundle has no picture model. Here is a prompt to use in an image tool:'
            after = 'Want a different style or setting? Tell me and I will rewrite the prompt.'
        if not prompt:
            return dict(route='chat/picture-in-chat', response=where.rsplit('.', 1)[0] + '. Tell me what the picture should show and I will write a prompt for it.',
                        sources=[], details='Chat mode has no picture engine; no image was made.')
        return dict(route='chat/picture-in-chat', response=f'{where}\n\n> {prompt}\n\n{after}', sources=[],
                    details='Chat mode has no picture engine, so CAEL\'s prompt helper wrote an image prompt instead (rule-based, non-neural).')

    def vynly_reply(self, text, messages):
        """A Vynly help answer when the message is about vynly.co, else None (cael_unified/vynly.py)."""
        if getattr(self, '_vynly', None) is None:
            from .vynly import VynlyHelp
            self._vynly = VynlyHelp()
        if not self._vynly.chunks or not self._vynly.about_vynly(text, messages):
            return None
        return self._vynly.answer(text, messages)

    def score_endings(self, context, endings):
        """The same unified model's native continuation likelihood interface."""
        with self._lock:
            if self._language is None:
                selected=self._language_checkpoint
                if selected is None:
                    configuration=ROOT/'research/active_models.json'
                    entry=json.loads(configuration.read_text()).get('language') if configuration.is_file() else None
                    if not entry:
                        return None
                    selected=Path(entry['path'])
                    if digest(selected)!=entry['sha256']:
                        raise ValueError('Active language model checksum changed')
                from .count_language import CountLanguage
                self._language=CountLanguage(Path(selected).parent)
            return self._language.score_endings(context,endings)

    def respond(self, messages, n=2, seed=None, mode='auto'):
        from .text_repair import repair_messages
        changes=[]
        if (mode in ('auto','chat','prompt','story') and isinstance(messages,list) and messages
                and all(isinstance(m,dict) and m.get('role') in ('user','assistant','system')
                        and isinstance(m.get('content'),str) for m in messages)
                and messages[-1]['role']=='user' and len(messages)<=MAX_MESSAGES
                and sum(len(m['content']) for m in messages)<=MAX_CHARACTERS):
            raw_route=route_request(messages[-1]['content'],mode)
            from .writing_chat import protect_input as writing_input
            from .codegen.python_tasks import protect_input as tool_input
            if raw_route not in ('image','emoji') and not choice_problem(messages[-1]['content']) and not picture_follow_up(messages) \
                    and not (mode in ('auto','chat') and (writing_input(messages[-1]['content'],messages)
                        or tool_input(messages[-1]['content'],messages))):
                messages,changes=repair_messages(messages)
        answer=self._respond(messages,n=n,seed=seed,mode=mode)
        # Last resort for factual questions CAEL could not answer: search the web, read the pages and quote the most
        # relevant sentence with its source (web_search.py). Off with CAEL_WEB_SEARCH=0.
        if (mode in ('auto','chat') and isinstance(answer,dict) and os.environ.get('CAEL_WEB_SEARCH','1')!='0'
                and isinstance(messages,list) and messages):
            from . import web_search
            text=messages[-1].get('content','')
            route=answer.get('route','')
            # An encyclopedia article that is not about the question's subject ("The Silent Cartographer" for
            # "What does a cartographer do?") counts as not answered too.
            off_topic=False
            if route.startswith('chat/web-wikipedia') and answer.get('sources'):
                from urllib.parse import unquote
                subject=set(web_search.terms(web_search.subject_of(text)))
                link=answer['sources'][0].get('url','')
                title=set(web_search.terms(re.sub(r'\s*\(.*','',unquote(link.rsplit('/',1)[-1]).replace('_',' '))))
                definition=bool(re.match(r"(?i)\s*(?:what|who)(?:'s| is| are| does| do)\s+(?:an?\s+|the\s+)?[\w\s-]+?(?:\s+do|\s+mean)?\s*\??$",text))
                off_topic=bool(subject) and bool(title) and '/wiki/' in link and (
                    not subject<=title or (definition and bool(title-subject-{'the'})))   # "Bikini barista" for "barista"
            if (route in WEB_FALLBACK_ROUTES or off_topic) and web_search.should_search(text):
                found=web_search.answer(text)
                if found is not None:
                    answer=found
        if isinstance(answer,dict) and isinstance(messages,list) and messages and isinstance(messages[-1].get('content'),str):
            from .verify import apply
            answer=apply(messages[-1]['content'],answer)
        if changes:
            note='Spelling interpretation: '+'; '.join(repr(c['original'])+' → '+repr(c['replacement']) for c in changes)+'.'
            answer=dict(answer,input_corrections=changes,details=answer.get('details','')+'\n'+note)
        return answer

    def _respond(self, messages, n=2, seed=None, mode='auto'):
        if not isinstance(messages, list) or not messages or not all(isinstance(m, dict) and m.get('role') in ('user', 'assistant', 'system') and isinstance(m.get('content'), str) for m in messages):
            raise ValueError('Invalid message format')
        if messages[-1]['role'] != 'user':
            raise ValueError('Messages must end with a user request')
        if len(messages) > MAX_MESSAGES or sum(len(m['content']) for m in messages) > MAX_CHARACTERS:
            raise ValueError('Conversation exceeds the local context limit')
        if type(n) is not int or not 1 <= n <= 8:
            raise ValueError('Choose between 1 and 8 outputs')
        seed = secrets.randbelow(2 ** 31) if seed is None else int(seed)
        if not 0 <= seed < 2 ** 31:
            raise ValueError('Seed must be between 0 and 2147483647')
        text = messages[-1]['content'].strip()
        if not text:
            raise ValueError('Request is empty')
        plan_context=getattr(self,'_plan_context',None)
        if plan_context is None:
            plan_context=self._plan_context=threading.local()
        if mode in ('auto','chat'):
            # A tool's operation list is one specification, not unrelated chat
            # commands. Execute only pure, bounded compiler-produced tools.
            from .codegen.python_tasks import reply as task_reply,structured_request
            answer=task_reply(text,messages)
            if answer is not None:return answer
            if structured_request(text):
                from .codegen.task_tools import reply as build_tool
                answer=build_tool(text,messages)
                if answer is not None:return answer
        # Plan explicit multi-step requests before a single-step writing,
        # reasoning or factual route can consume the entire message. The guard
        # belongs to this execution thread, not another user's concurrent chat.
        if mode in ('auto','chat') and not getattr(plan_context,'running',False):
            from . import orchestrator
            steps=orchestrator.plan(text)
            if steps:
                plan_context.running=True
                try:
                    board=orchestrator.run(steps,lambda step,history:self._respond(
                        history+[dict(role='user',content=step)],n=1,seed=(seed+len(history))%2**31,mode=mode),messages)
                finally:
                    plan_context.running=False
                return orchestrator.report(board)
        # Resolve an explicit prose-editing exchange before factual pronoun
        # rewriting or splitting a learner's sentence into executable steps.
        if mode in ('auto', 'chat'):
            from .writing_chat import reply as writing_reply
            answer = writing_reply(text, messages)
            if answer is not None:
                return answer
            # An explicit ordering scenario owns its clues and continuations;
            # generic conversational/comparison routes must not discard them.
            from .reasoning_order import chat_scope as ordering_scope
            if ordering_scope(text,messages):
                if self._reasoning is None:
                    from .reasoning import Reasoner
                    self._reasoning=Reasoner()
                answer=self._reasoning.respond(text,messages)
                if answer is not None:
                    return answer
        # A follow-up ("and what about Germany?", "when was he born?") is answered as the full question it stands for.
        if mode in ('auto', 'chat') and not getattr(plan_context, 'rewriting', False):
            from . import chat_extra
            full = chat_extra.rewrite(messages)
            if full and full.strip().lower() != text.lower():
                plan_context.rewriting = True
                try:
                    answer = self._respond(messages[:-1] + [dict(messages[-1], content=full)], n=n, seed=seed, mode=mode)
                finally:
                    plan_context.rewriting = False
                return dict(answer, understood_as=full, details=answer.get('details', '') + f'\nUnderstood as: "{full}".')
        route = route_request(text, mode)
        if route == 'chat' and mode == 'auto' and picture_follow_up(messages):
            route = 'image'
        if route == 'image' and self.manifest.get('profile') == 'no-images':
            return self.picture_in_chat(text, messages, seed)
        if route == 'image' and mode == 'auto' and self.vynly_reply(text, messages) is not None:
            route = 'chat'          # "how do I generate an image on Vynly?" is a help question, not a drawing request
        # A picture request in chat-only mode (the vynly.co widget has no drawing): write the prompt instead.
        if route == 'chat' and mode == 'chat' and route_request(text, 'auto') == 'image' and self.vynly_reply(text, messages) is None:
            return self.picture_in_chat(text, messages, seed)
        with self._lock:
            if route == 'image':
                return self.image_reply(text, n, seed, messages)
            if route == 'emoji':
                return self.emoji_reply(text, n, seed)
            if route == 'prompt':
                if self._prompt is None:
                    from .promptgen import PromptGenerator
                    self._prompt = PromptGenerator()
                return self._prompt.respond(text,seed,forced=True,default_kind='image' if mode=='prompt' else 'task')
            if route == 'story':
                return self.story_reply(messages,seed,required=True)
            # Questions about vynly.co, where CAEL is the helper chatbot (cael_unified/vynly.py).
            answer = self.vynly_reply(text, messages)
            if answer is not None:
                return answer
            # Exact everyday quantities: powers, fractions, units, speed, prices, "N times as many" (quantities.py).
            from . import quantities
            answer = quantities.reply(text)
            if answer is not None:
                return answer
            # Well-known world facts (world_facts.py), then superlatives / counts / years found in Wikipedia's
            # opening paragraphs (answer_finder.py). Both answer only clear question shapes.
            from . import world_facts, answer_finder
            answer = world_facts.reply(text) or answer_finder.reply(text)
            if answer is not None:
                return answer
            # "What is the capital of Canada?": the structured Wikidata answer, not a long local paragraph.
            if re.match(r"(?i)^\s*(?:what(?:'s| is) |tell me |name )?(?:the )?capital (?:city )?of [^?.!,]{2,40}[?.!]*\s*$", text):
                try:
                    answer = self._facts.structured_faq(re.sub(r'(?i)\bcapital city of\b', 'capital of', text.strip().rstrip('?.! ')))
                except Exception:
                    answer = None
                if answer is not None:
                    return answer
            choice=choice_problem(text)
            if choice:
                context,endings=choice
                from .choice_helpers import reply as helper_choice_reply
                answer=helper_choice_reply(context,endings,self._reasoning)
                if answer is not None:
                    return answer
                from .symbolic_choice import reply as symbolic_choice_reply
                answer=symbolic_choice_reply(context,endings,self._reasoning)
                if answer is not None:
                    return answer
                scores=self.score_endings(context,endings)
                if scores is not None:
                    chooser=self.choice_settings()
                    if chooser:
                        # Reviewed whole-system chooser (research/leaderboard_040): language model,
                        # local evidence retrieval and exact word-problem arithmetic.
                        from .choice import Evidence, arc_evidence, choose
                        if getattr(self,'_evidence',None) is None:
                            self._evidence=Evidence()
                            self._arc_evidence=arc_evidence() if chooser.get('arc_weight') else None
                        best,how=choose(context,endings,scores,self._evidence,chooser['weight'],chooser['short_limit'],
                                        extra=[(self._arc_evidence,chooser.get('arc_weight',0.0))])
                        detail=('Chosen by the whole-system chooser: count language model plus evidence from the local '
                                'Wikipedia snapshot and ARC science corpus, or exact arithmetic for word problems ('+how['route']+'). Not a live web lookup.')
                    else:
                        best=max(range(len(scores)),key=lambda i:scores[i]['sum_lnp']/max(1,scores[i]['tokens']))
                        detail='Non-neural conditional count language component. Training attribution is listed under data sources and licences. This is a statistical choice, not a verified factual lookup.'
                    return dict(route='chat/choice-count',response=f'{"ABCD"[best]}. {endings[best]}',sources=[],
                                details=detail,choice=best,continuation_scores=scores)
            # An active task tool belongs to this conversation. Resolve its
            # specification/use before a coincidentally named global rule.
            from .codegen.task_tools import reply as task_tool_reply
            answer = task_tool_reply(text, messages=messages)
            if answer is not None:
                return answer
            # Learned rules: sequences, reusing a rule by name, the rule list, and feedback on a rule (rules.py).
            from . import rules
            answer = rules.reply(text, messages)
            if answer is not None:
                return answer
            # "Write a Python script that searches the web for ...": CAEL's own search, as a runnable script (web_search.py).
            from . import web_search
            answer = web_search.script_reply(text)
            if answer is not None:
                return answer
            # Python questions first: the helper would otherwise send "what does this code do?" to a web lookup.
            from .codegen import chat as codegen
            answer = codegen.reply(text, seed, messages=messages)
            if answer is not None:
                return answer
            # Word questions (meanings, synonyms, forms, spelling) from the offline dictionary, before any web lookup.
            from .helper_math import reply as exact_math_reply
            answer = exact_math_reply(text)
            if answer is not None:
                return answer
            from . import dictionary, grammar
            answer = grammar.reply(text) or dictionary.reply(text)
            if answer is not None:
                return answer
            # Everyday writing: summaries, emails, name ideas, simple explanations, comparisons (compose_text.py).
            from . import compose_text
            answer = compose_text.reply(text, seed)
            if answer is not None:
                return answer
            from . import everyday
            answer = everyday.reply(text, seed)
            if answer is not None:
                return answer
            # Conditionals, comparisons, all/no/some, word problems, time, analogies, common sense (reasoning_extra.py).
            from . import reasoning_extra
            answer = reasoning_extra.reply(text)
            if answer is not None:
                return answer
            # Everyday statements, tips, opinions, fun facts (chat_extra.py).
            from . import chat_extra
            answer = chat_extra.reply(text, messages, seed)
            if answer is not None:
                return answer
            from .helper_chat import reply as helper_reply
            answer = helper_reply(text,messages)
            if answer:
                return answer
            answer = smalltalk.reply(messages, seed)
            if answer is not None:
                return answer
            if self._reasoning is None:
                from .reasoning import Reasoner
                self._reasoning = Reasoner()
            answer = self._reasoning.respond(text,messages)
            if answer is not None:
                return answer
            if text.lower().startswith(('who ', 'where ', 'what does ', 'what is ')):
                result=self.story_reply(messages,seed)
                if result is not None:
                    return result
            # Advice and how-to: CAEL's own answer, worked out from what many sources agree on (thinking.py).
            from . import thinking
            answer = thinking.reply(text, messages, seed)
            if answer is not None:
                return answer
            # Otherwise a human-written reply to a closely matching request, labelled as such (chat_corpus.py).
            from . import chat_corpus
            answer = chat_corpus.reply(text, messages)
            if answer is not None:
                return answer
            answer = self._facts.respond(text, messages=messages)
            if answer is not None:
                return answer
            # Small talk must not stand in for an answer it cannot give.
            if re.fullmatch(r'(?i)\s*(?:https?://|www\.)\S+\s*', text):
                return dict(route='chat/cannot-answer', sources=[], details='Bare links are not opened or read.',
                            response='I cannot open or read links. Ask me a question about the topic instead.')
            parsed = self._facts.knowledge_query.parse(text)
            if parsed and parsed['terms'] and not re.search(r"(?i)\b(?:you|your|yours|yourself|up|going|doing|time)\b", text):
                return dict(route='chat/cannot-answer', sources=[], details='Factual question without a verified source answer; the chat fallback was not used.',
                            response='I cannot answer that reliably. I did not find a verified source for it.')
            if self._chat is None:
                from .legacy_chat.cael_v4 import V4, load_v2
                self._chat = V4(load_v2(self.root / 'chat'))
            result = dict(self._chat.respond(messages))
            result['route'] = 'chat/local-' + result.get('route', 'unknown')
            # The old model often answers with a guessed emotional reaction ("Nice! I'm happy for you").
            # Keep it only when the message really carries that feeling; otherwise ask, instead of guessing.
            felt, reacted = smalltalk.polarity(text), smalltalk.reaction(result.get('response', ''))
            if reacted and felt != reacted:
                result.update(route='chat/local-clarify', response=smalltalk.clarify(text, seed),
                              details='The fallback reply guessed a feeling the message does not express, so CAEL asks instead.')
            # Dead ends ("I don't have reliable knowledge...", "Tell me more about that") get a real reply instead: a looser
            # corpus match, or a conversational reaction with a follow-up question (chat_extra.converse).
            if result['route'] in ('chat/local-clarify', 'chat/local-other', 'chat/local-define', 'chat/local-howto', 'chat/local-opinion',
                                   'chat/local-recommend', 'chat/local-write', 'chat/local-smalltalk', 'chat/local-unknown'):
                better = chat_corpus.reply(text, messages, open_ended_only=False) or chat_extra.converse(text, messages, seed)
                if better is not None:
                    return better
            return result

    def story_reply(self,messages,seed,required=False):
        """Reconstruct story state from this conversation only."""
        from cael import CAEL, Unsupported
        path=self.root/'story/model.json'
        config=ROOT/'research/active_models.json'
        entry=json.loads(config.read_text()).get('story') if config.is_file() else None
        if entry:
            path=Path(entry['path'])
            if digest(path)!=entry['sha256']:raise ValueError('Active story model checksum changed')
        story=CAEL(path)
        text=messages[-1]['content'].strip()
        question=text.lower().startswith(('who ','where ','what does ','what is '))
        try:
            if question:
                previous=next((messages[i]['content'] for i in range(len(messages)-2,-1,-1)
                    if messages[i]['role']=='user' and i+1<len(messages)-1
                    and messages[i+1]['role']=='assistant' and messages[i+1]['content'].startswith('Story:\n')
                    and not is_prompt_request(messages[i]['content'])),None)
                if not previous:raise Unsupported('No supported story in this conversation.')
                if not re.search(r'(?i)\b(?:story|tale|fable)\b',previous):previous='Tell a story about '+previous
                story.story(previous,seed)
                result=story.ask(text)
            else:
                if required and not re.search(r'(?i)\b(?:story|tale|fable)\b',text):text='Tell a story about '+text
                result=story.story(text,seed)
                result['response']='Story:\n'+result['response']
            return dict(result,route='chat/story',sources=[],details='A short story from the trained integer CA planner, world memory and counted grammar. Supports a finite vocabulary and eight goals.')
        except Unsupported as error:
            if required or STORY_REQUEST.search(text):
                return dict(route='chat/story-unsupported',response=str(error)+' Try a finding, sharing, helping, losing, visiting, resting, learning or comforting goal. For example: “Tell a story about an astronaut finding a compass in a space station.”',sources=[])
            return None

    def emoji_reply(self, text, n, seed):
        import torch
        torch.set_num_threads(4)
        if self._emoji is None:
            from .emoji import EmojiTool
            self._emoji = EmojiTool(self.root / 'emoji' / 'model.pt', self.root / 'emoji' / 'references.pt')
        subject = re.sub(r'(?i)^\s*(?:please\s+)?(?:make|create|generate|draw|show|give)(?:\s+me)?\s+(?:an?\s+)?', '', text)
        subject = re.sub(r'(?i)\bemojis?\s*(?:of|for)?\b', '', subject).strip(' .!?')
        original_subject = subject
        self._emoji.ensure()
        self._emoji.last_learn = None
        phrase_key = re.sub(r'[^a-z0-9]+', '', subject.lower())
        if phrase_key in self._emoji.learned:
            subject = phrase_key
        else:
            subject = self._emoji.prepare(subject)
        folder = self.output_root / ('emoji_' + secrets.token_hex(8))
        info = self._emoji.generate(subject, n=n, seed=seed, outdir=folder)
        details = '64x64 integer CA emoji; new words can use reviewed online references. Unmatched words may be ignored.'
        if info.get('fetched'):
            sources = info['fetched']
            shared = any('BY-SA' in item['licence'] for item in sources)
            attribution = dict(sources=sources, modification='Source shapes normalized to 64x64 and used through learned cellular counts.',
                               output_terms='CC BY-SA 4.0; retain attribution' if shared else 'Retain source attribution and the recorded source-license terms')
            (folder / 'attribution.json').write_text(json.dumps(attribution, indent=2), encoding='utf-8')
            details += ' Public reference sources: ' + '; '.join(item['source'] + ' (' + item['licence'] + ')' for item in sources)
            from .licensing import image_credits
            details += '\n' + image_credits(sources)
        response = f'Created {n} emoji for {original_subject}.'
        learned = self._emoji.last_learn
        if learned:
            response += ' ' + ('Learned this word from licensed internet references.' if learned[0] == 'learned' else 'Used saved licensed references for this word.')
        elif not info.get('known_words') and not info.get('fetched'):
            response = f'I could not match {original_subject} to my vocabulary or licensed online references. These {n} outputs are unguided emoji.'
        return dict(route='emoji/generated', response=response,
                    paths=info['paths'], grid=info['grid'], seed=seed,
                    details=details, sources=info.get('fetched', []), tool=info)

    def choice_settings(self):
        """The reviewed multiple-choice settings (weight, short_limit) when active_models.json selects them."""
        overrides = ROOT / 'research' / 'active_models.json'
        config = json.loads(overrides.read_text(encoding='utf-8')).get('choice') if overrides.is_file() else None
        if not config:
            return None
        from .bundle import digest as file_digest
        for name, expected in config.get('code', {}).items():
            if file_digest(ROOT / 'cael_unified' / f'{name}.py') != expected:
                raise ValueError(f'Reviewed chooser code changed: {name}.py')
        return config

    def hybrid(self):
        """The reviewed hybrid (PCA layout + patch synthesis) model, when active_models.json selects it."""
        if getattr(self, '_hybrid', None) is None:
            self._hybrid = False
            overrides = ROOT / 'research' / 'active_models.json'
            config = json.loads(overrides.read_text(encoding='utf-8')).get('hybrid_image') if overrides.is_file() else None
            if config:
                if digest(Path(config['path'])) != config['sha256']:
                    raise ValueError('Active hybrid image model checksum changed')
                from cael_image.hybrid import HybridModel
                self._hybrid = (HybridModel(config['path']), config)
        return self._hybrid or None

    def hybrid_request(self, text):
        """The parsed picture request (subject, colour, style, count, background), or None."""
        active = self.hybrid()
        if not active:
            return None
        from cael_image.request import parse
        model, _ = active
        aliases = model.meta['aliases'] or {t: [t.replace('_', ' ')] for t in model.topics}
        try:
            request = parse(text, {t: aliases.get(t, [t.replace('_', ' ')]) for t in model.topics})
        except ValueError:
            return None
        return request if request['subject'] in model.topics else None

    def picture_scene(self, messages, seed):
        """The scene a request asks for: a new picture, or the conversation's last picture with this edit applied.

        Returns (scene, what changed or None), or None when the request names nothing the hybrid model can draw.
        Raises SceneError with a reason when the request is understood but cannot be drawn.
        """
        from cael_image.scene import edit, is_edit, parse
        active = self.hybrid()
        if not active:
            return None
        model, _ = active
        aliases = model.meta['aliases'] or {t: [t.replace('_', ' ')] for t in model.topics}
        text = messages[-1]['content'].strip()
        if picture_follow_up(messages) or (is_edit(text) and not new_picture_request(text) and len(messages) >= 3
                                           and picture_reply(messages[-2])):
            # Replay the chain of picture requests and edits that led to the last picture.
            chain = []
            for i in range(len(messages) - 2, 0, -2):
                if not (picture_reply(messages[i]) and messages[i - 1]['role'] == 'user'):
                    break
                chain.append(messages[i - 1]['content'])
                if route_request(messages[i - 1]['content']) == 'image' and not is_edit(messages[i - 1]['content']):
                    break
            chain.reverse()
            if chain:
                try:
                    scene = parse(chain[0], aliases, model.topics, seed=0)
                except ValueError:
                    scene = None
                if scene is not None:
                    for step in chain[1:]:
                        try:
                            scene = edit(scene, step, aliases, model.topics)[0]
                        except ValueError:
                            pass
                    return edit(scene, text, aliases, model.topics, seed)
        try:
            return parse(text, aliases, model.topics, seed), None
        except ValueError as error:
            if type(error).__name__ == 'SceneError':
                raise
            return None

    def scene_images(self, scene, change, n, seed):
        import numpy as np
        import torch
        from PIL import Image
        from cael_image.draw import draw
        from cael_image.scene import plausibility, render, simple, summary
        model, config = self.hybrid()
        settings = config.get('settings', {})
        reasons = [o['why'] for o in scene['objects'] if o['why']]
        if simple(scene):
            obj = scene['objects'][0]
            request = dict(subject=obj['topic'], colour=obj['colour'], count=obj['count'], style=scene['style'],
                           background=scene['background'], notes=list(scene['notes']))
            images, info = draw(model, request, n=n, seed=seed, settings=settings, clean_background=False)
            info['subject'] = summary(scene)
            if obj['colour'] or obj['count'] > 1 or scene['background'] not in (None, 'plain'):
                info['notes'].append('Changing colour, number or background is experimental and may look rough.')
        else:
            images, info = render(model, scene, n=n, seed=seed, settings=settings)
            if len(scene['objects']) > 1:
                info['notes'] = info['notes'] + ['Pictures with several objects are composed from separate cut-outs and may look rough.']
        info['notes'] = list(dict.fromkeys(reasons + plausibility(scene) + info['notes']))
        info['change'] = change
        size = config.get('display_size', 128)
        shown = np.stack([np.asarray(Image.fromarray(im).resize((size, size), Image.Resampling.LANCZOS)) for im in images])
        info.update(seed=seed, scene=scene, limitation=(f'{model.size}x{model.size} hybrid image: PCA layout plus patch synthesis from Stable '
                    'Diffusion 1.5 training renders (CreativeML OpenRAIL-M). No neural network runs here. The request is read into '
                    'objects, colours, sizes and placements; layouts follow your placements and real-world sizes.'))
        return torch.from_numpy(shown), info

    def hybrid_topic(self, text):
        request = self.hybrid_request(text)
        return request['subject'] if request else None

    def hybrid_images(self, text, n, seed):
        import numpy as np
        import torch
        from PIL import Image
        from cael_image.draw import draw
        model, config = self.hybrid()
        request = self.hybrid_request(text)
        # A plain request keeps the picture as synthesised; colour/count/scene edits need a cut-out.
        images, info = draw(model, request, n=n, seed=seed, settings=config.get('settings', {}), clean_background=False)
        size = config.get('display_size', 128)
        shown = np.stack([np.asarray(Image.fromarray(im).resize((size, size), Image.Resampling.LANCZOS)) for im in images])
        edited = bool(request['colour'] or request['count'] > 1 or request['background'] not in (None, 'plain'))
        if edited:
            info['notes'].append('Changing colour, number or background is experimental and may look rough.')
        info.update(seed=seed, limitation=(f'{model.size}x{model.size} hybrid image: PCA layout plus patch synthesis from Stable '
                    'Diffusion 1.5 training renders (CreativeML OpenRAIL-M). No neural network runs here. Each picture combines '
                    'patches from a few training images; see sources for the largest single-source share.'))
        return torch.from_numpy(shown), info

    def image_reply(self, text, n, seed, messages=None):
        import torch
        from PIL import Image
        from cael_image.general_appearance import GeneralAppearance
        torch.set_num_threads(4)
        if self._image is None:
            checkpoint = torch.load(self.root / 'image' / 'model.pt', map_location='cpu', weights_only=True)
            self._portrait_guard_references = checkpoint['guard_references']
            fallback = GeneralAppearance(checkpoint)
            overrides = ROOT / 'research' / 'active_models.json'
            if overrides.is_file():
                configuration = json.loads(overrides.read_text(encoding='utf-8'))
                if configuration.get('general_image'):
                    selected = Path(configuration['general_image']['path'])
                    if digest(selected) != configuration['general_image']['sha256']:
                        raise ValueError('Active image model checksum changed')
                    checkpoint = torch.load(selected, map_location='cpu', weights_only=True)
                    self._image = GeneralAppearance(checkpoint, fallback=fallback,
                                                    enabled_subjects=configuration['general_image'].get('enabled_subjects'))
            if self._image is None:
                self._image = fallback
        # The main (hybrid) model draws people better than the older portrait models; they are only a fallback.
        hybrid_people = bool(self.hybrid()) and {'woman', 'man'} <= set(self.hybrid()[0].topics)
        portrait = bool(re.search(r'\bportrait\b|head.and.shoulders', text, re.I)) and not re.search(r'\b(man|men|male|boy)\b', text, re.I) \
            and not hybrid_people
        explicit_portrait = bool(re.search(r'\bportrait\b|head.and.shoulders', text, re.I)) and not hybrid_people
        portrait_subject = 'man' if re.search(r'\b(man|men|male)\b', text, re.I) else 'woman'
        portrait_override = None
        overrides = ROOT / 'research' / 'active_models.json'
        if explicit_portrait and overrides.is_file():
            portrait_override = json.loads(overrides.read_text(encoding='utf-8')).get('portrait_image')
        try:
            if portrait_override and portrait_subject in portrait_override.get('enabled_subjects', []):
                if self._portrait_synthetic is None:
                    selected = Path(portrait_override['path'])
                    if digest(selected) != portrait_override['sha256']:
                        raise ValueError('Active portrait model checksum changed')
                    checkpoint = torch.load(selected, map_location='cpu', weights_only=True)
                    if not set(checkpoint['priors']) <= {'woman', 'man'} or checkpoint.get('image_size') not in (128, 256):
                        raise ValueError('Unsupported focused portrait model')
                    self._portrait_synthetic = GeneralAppearance(checkpoint)
                images, info = self._portrait_synthetic.generate(portrait_subject, n=n, seed=seed)
                info['subject'] = 'adult ' + portrait_subject + ' portrait'
            elif portrait:
                from cael_image.portrait_deformation import DeformationPrior
                from cael_image.portrait_appearance import sample_guarded_appearance
                if self._portrait is None:
                    self._portrait = torch.load(self.root / 'portrait' / 'model.pt', map_location='cpu', weights_only=True)
                settings = self._portrait['settings']
                prior = DeformationPrior(self._portrait['prior'], warp_strength=settings['warp_strength'])
                images, checks = sample_guarded_appearance(prior, n, seed, self._portrait_guard_references,
                                                          variation=settings['variation'], sharpen=settings['sharpen'])
                info = dict(subject='adult woman portrait', seed=seed, checks=checks,
                            limitation='Unconditional 64x64 portraits of adult women; caption attributes are not learned controls.',
                            guard_limit=self._portrait['guard_limit'])
            elif (picture := self.picture_scene(messages or [dict(role='user', content=text)], seed)) is not None:
                images, info = self.scene_images(*picture, n, seed)
            else:
                from cael_image.general_curriculum import curriculum
                from cael_image.general_appearance import resolve_subject
                known_aliases = {key: list(value[1]) for key, value in curriculum('expanded').items()}
                known_aliases['woman'] = [word for word in known_aliases['woman'] if word not in ('person', 'people', 'portrait')]
                intended = resolve_subject(text, known_aliases, seed)
                if intended not in self._image.checkpoint['priors']:
                    raise ValueError(f'The {intended.replace("_", " ")} category has not finished training in the active image model')
                images, info = self._image.generate(text, n=n, seed=seed)
        except ValueError as exc:
            available = self.hybrid()[0].topics if self.hybrid() else self._image.checkpoint['priors']
            return dict(route='image/unsupported', response=str(exc) + '. Available subjects: ' + ', '.join(t.replace('_', ' ') for t in available), paths=[])
        folder = self.output_root / ('image_' + secrets.token_hex(8))
        folder.mkdir(parents=True, exist_ok=False)
        paths = []
        for i, pixels in enumerate(images.numpy()):
            path = folder / f'image_{i:02d}_{pixels.shape[0]}.png'
            Image.fromarray(pixels).save(path)
            paths.append(str(path))
        grid = folder / 'grid.png'
        cell_size = max(128, images.shape[1])
        canvas = Image.new('RGB', (cell_size * n, cell_size))
        for i, pixels in enumerate(images.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((cell_size, cell_size), Image.Resampling.NEAREST), (cell_size * i, 0))
        canvas.save(grid)
        (folder / 'generation.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
        notes = (' ' + ' '.join(info['notes'])) if info.get('notes') else ''
        if info.get('change'):
            notes = ' ' + info['change'] + notes
        return dict(route='image/generated', response=f'Created {n} small images of {info["subject"]}.' + notes,
                    paths=paths, grid=str(grid), seed=seed, details=info['limitation'], tool=info)
