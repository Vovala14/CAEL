"""Train CAEL's finite integer programs from an authored synthetic teacher."""
import argparse
import collections
import hashlib
import itertools
import json
import random
import time
from pathlib import Path

from curriculum import (ACTORS, OBJECTS, PLACES, INTENTS, SKILLS, FORMS,
    STORY_MARKERS, EVENTS, PLANS, tokens, split, hashframe, initial_rows,
    relations, teacher, packet, surface)

ROOT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')

def possible_frames():
    """Enumerate canonical frames once; unused slots cannot fake novelty."""
    for intent in INTENTS:
        for a, p in itertools.product(range(len(ACTORS)), range(len(PLACES))):
            others = [b for b in range(len(ACTORS)) if b != a] if intent in ('share','help','visit','comfort') else [(a + 1) % len(ACTORS)]
            items = range(len(OBJECTS)) if intent in ('find','share','help','lose','visit','rest') else [0]
            skills = range(len(SKILLS)) if intent == 'learn' else [0]
            for b, i, s in itertools.product(others, items, skills):
                yield dict(a=a, b=b, i=i, p=p, s=s, intent=intent)

def data(seed, excluded, counts):
    pools = {s: [] for s in counts}
    for f in possible_frames():
        if hashframe(f) not in excluded:
            pools[split(f)].append(f)
    rng = random.Random(seed)
    for tag in pools:
        rng.shuffle(pools[tag])
        if len(pools[tag]) < counts[tag]:
            raise ValueError(f'{tag}: requested {counts[tag]}, available {len(pools[tag])}')
        pools[tag] = pools[tag][:counts[tag]]
    return pools

def train(out, seed=2026101317, train_count=30000, heldout_count=2000, cumulative=5000):
    started = time.monotonic()
    if (out / 'model.json').exists():
        raise FileExistsError(f'Refusing to overwrite a trained model in {out}')
    excluded = set(json.loads((ROOT / 'natural_frame_holdout.json').read_text()))
    sets = data(seed, excluded, dict(train=train_count, development=heldout_count, confirmation=heldout_count))
    rng = random.Random(seed + 1)
    valid, observations = {}, collections.Counter()
    plans = collections.defaultdict(collections.Counter)
    utterances = collections.defaultdict(collections.Counter)
    text_hashes = set()
    event_count = 0

    def learn_frame(frame, rows):
        nonlocal event_count
        p = packet(frame)
        previous = 'START'
        story = []
        for step, event in enumerate(PLANS[frame['intent']] + ['END']):
            plans[(frame['intent'], previous, step)][event] += 1
            previous = event
            if event == 'END':
                continue
            event_count += 1
            utterance = rng.choice(EVENTS[event])
            utterances[event][utterance] += 1
            story.append(surface(utterance, frame))
            for row in rows:
                key = (event, row[1], relations(row, p))
                new = teacher(row, p, event)
                if key not in valid:
                    valid[key] = [set(range(8)) for _ in range(5)]
                for field in range(5):
                    choices = [row[field+2], 0, p['a'], p['b'], p['i'], p['p'], 201, 1]
                    valid[key][field] &= {j for j, value in enumerate(choices) if value == new[field+2]}
                observations[key] += 1
                row[:] = new
        text_hashes.add(hashlib.sha256(' '.join(' '.join(story).casefold().split()).encode()).hexdigest())

    for f in sets['train']:
        learn_frame(f, initial_rows())
    episode_indices = []
    for _ in range(cumulative):
        indices = rng.sample(range(len(sets['train'])), rng.randint(2,4))
        episode_indices.append(indices)
        world = initial_rows()
        for index in indices:
            learn_frame(sets['train'][index], world)

    lex = collections.defaultdict(collections.Counter)
    for tag, values in [('actor',ACTORS),('object',OBJECTS),('place',PLACES),('skill',SKILLS)]:
        for j, word in enumerate(values):
            lex[word][f'{tag}:{j}'] += 1
    for intent, forms in FORMS.items():
        for form in forms:
            lex[form]['intent:' + intent] += 1
    for word in STORY_MARKERS:
        lex[word]['story'] += 1
    for event in EVENTS:
        if event.startswith('ANSWER_'):
            for text in EVENTS[event]:
                utterances[event][text] += 200
    rules = []
    for (event, kind, relation), values in sorted(valid.items()):
        if not all(values):
            raise ValueError(f'Cannot express teacher transition with declared opcodes: {event,kind,relation}')
        rules.append(dict(event=event, kind=kind, relation=relation,
                          ops=[min(v) for v in values], observations=observations[(event,kind,relation)]))
    symbols = sorted({t for choices in utterances.values() for s in choices for t in tokens(s)} | {'<END>'})
    symbol_ids = {t: i for i, t in enumerate(symbols)}
    states, starts = [], {}
    for event, choices in sorted(utterances.items()):
        start = len(states)
        states.append(collections.Counter())
        starts[event] = start
        edges = {}
        for text, count in sorted(choices.items()):
            state = start
            for token in tokens(text) + ['<END>']:
                t = symbol_ids[token]
                key = (state, t)
                if key not in edges:
                    edges[key] = len(states)
                    states.append(collections.Counter())
                nxt = edges[key]
                states[state][(t,nxt)] += count
                state = nxt
    model = dict(family='CAEL', family_expansion='Cellular Automaton Event Language',
        version='0.1.0', variant='CAEL Story',
        scope='closed-domain stories and cumulative event memory; not general chat',
        actors=ACTORS, objects=OBJECTS, places=PLACES, skills=SKILLS, intents=INTENTS,
        lexicon={w:dict(n) for w,n in sorted(lex.items())}, event_names=sorted(EVENTS),
        update_rules=rules,
        plan_rules=[dict(intent=k[0], previous=k[1], step=k[2], choices=dict(v)) for k,v in sorted(plans.items())],
        symbols=symbols,
        grammar=[[[t,nxt,c] for (t,nxt),c in sorted(s.items())] for s in states],
        grammar_starts=starts,
        opcode_semantics=['KEEP','ZERO','COPY_AGENT','COPY_OTHER','COPY_OBJECT','COPY_PLACE','HOME_PLACE','ONE'],
        neural_parameters=0, teacher_schema_authored=True, surface_grammar_template_like=True,
        english_parser='handwritten closed grammar', architecture='hybrid symbolic cellular event language')
    save(out / 'model.json', model)
    generated = ROOT / 'research' / out.name
    for name, frames in sets.items():
        save(generated / (name + '_frames.json'), frames)
    save(generated / 'training_episode_indices.json', episode_indices)
    save(generated / 'train_response_hashes.json', sorted(text_hashes))
    manifest = dict(model_sha256=digest(out/'model.json'), model_bytes=(out/'model.json').stat().st_size,
        seed=seed, frames={s:len(v) for s,v in sets.items()}, cumulative_training_episodes=cumulative,
        labelled_training_events=event_count, learned_update_rules=len(rules), grammar_states=len(states),
        excluded_natural_frames=len(excluded), seconds=time.monotonic()-started,
        dataset_sha256={p.name:digest(p) for p in generated.glob('*.json')},
        source_sha256={n:digest(ROOT/n) for n in ['train.py','curriculum.py','cael.py','PROTOCOL.md','natural_frame_holdout.json']})
    save(out/'manifest.json', manifest)
    print(json.dumps(manifest, indent=2))
    return manifest

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT/'models'/'cael-story-0.1')
    ap.add_argument('--seed', type=int, default=2026101317)
    ap.add_argument('--train-frames', type=int, default=30000)
    ap.add_argument('--heldout-frames', type=int, default=2000)
    ap.add_argument('--cumulative-episodes', type=int, default=5000)
    a=ap.parse_args()
    train(a.out.resolve(), a.seed, a.train_frames, a.heldout_frames, a.cumulative_episodes)
