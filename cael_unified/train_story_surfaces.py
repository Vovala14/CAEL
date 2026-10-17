"""Fit a fresh counted story grammar; preserve the verified event programs/plans."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from curriculum import EVENTS, tokens

ROOT = Path(__file__).resolve().parents[1]
ADDITIONS = {
    'INTRO': ['One quiet morning , <A> was near the <P> .'],
    'WANT': ['<A> decided to look for the <I> .'],
    'SEARCH': ['<A> looked carefully around the <P> .'],
    'FIND': ['After a careful search , <A> found the <I> .'],
    'HAPPY': ['<A> smiled with relief .'],
    'MEET': ['At the <P> , <A> met <B> .'],
    'SHARE': ['<A> kindly gave the <I> to <B> .'],
    'THANK': ['<B> thanked <A> with a smile .'],
    'TOGETHER': ['The friends were glad to be together .'],
    'RETURN': ['<A> brought the <I> back to <B> .'],
    'CAREFUL': ['<A> promised to look after the <I> .'],
    'HOME': ['At the end of the visit , <A> went home .'],
    'FAIL': ['The first attempt was hard .'],
    'PRACTICE': ['<A> practiced patiently each day .'],
    'SUCCESS': ['After practicing , <A> learned to <S> .'],
    'AFRAID': ['<B> felt scared and wanted company .'],
    'COMFORT': ['<A> stayed with <B> and offered gentle words .'],
    'CALM': ['With <A> nearby , <B> felt calm again .'],
}


def fit():
    original = ROOT/'models/cael-story-0.1/model.json'
    model = json.loads(original.read_text())
    texts = {event: forms + ADDITIONS.get(event, []) for event, forms in EVENTS.items()}
    symbols = sorted({token for forms in texts.values() for text in forms for token in tokens(text)} | {'<END>'})
    ids = {symbol: index for index, symbol in enumerate(symbols)}
    states, starts = [], {}
    observations = 0
    for event, forms in sorted(texts.items()):
        start = len(states)
        states.append(Counter())
        starts[event], edges = start, {}
        for text in forms:
            state = start
            # Counts are repeated authored surface observations, not new real stories.
            count = 100
            observations += count
            for token in tokens(text) + ['<END>']:
                symbol = ids[token]
                if (state, symbol) not in edges:
                    edges[(state, symbol)] = len(states)
                    states.append(Counter())
                following = edges[(state, symbol)]
                states[state][(symbol, following)] += count
                state = following
    model.update(version='0.2.6-local', symbols=symbols, grammar_starts=starts,
                 grammar=[[[t, n, count] for (t, n), count in sorted(state.items())] for state in states],
                 surface_training_observations=observations, unique_surface_templates=sum(map(len,texts.values())),
                 source_program_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
    out = ROOT/'models/cael-story-0.2.6'
    out.mkdir(parents=True, exist_ok=True)
    (out/'model.json').write_text(json.dumps(model, indent=2))
    (out/'report.json').write_text(json.dumps(dict(authored_extra_templates=len(ADDITIONS),
        counted_surface_observations=observations, distinct_surface_templates=sum(map(len,texts.values())),
        event_programs_and_plans_unchanged=True, benchmark_training_rows=0,
        external_data=False, general_language_quality_unverified=True),indent=2))
    print(json.dumps(dict(path=str(out), templates=sum(map(len,texts.values())), sha256=hashlib.sha256((out/'model.json').read_bytes()).hexdigest())))


if __name__ == '__main__':
    fit()
