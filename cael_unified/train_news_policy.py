"""Train and evaluate a linear topic-slot model on authored request paraphrases."""
import hashlib
import json
from pathlib import Path
import random

from .bundle import ROOT
from .news_policy import NewsPolicy, intent_features, slot_features, tokens, score

TRAIN_TOPICS = ['Israel', 'France', 'technology', 'football', 'artificial intelligence', 'space exploration',
                'electric cars', 'climate change', 'Japan', 'Google', 'Ukraine', 'health research']
TEST_TOPICS = ['Canada', 'Brazil', 'robotics', 'quantum computers', 'ocean conservation', 'Nintendo']
CONFIRM_TOPICS = ['South Korea', 'semiconductors', 'renewable energy storage', 'marine biology', 'Australia']
CONFIRM_TEMPLATES = ['give me <{topic}> headlines please', 'please show the recent news on <{topic}>',
                     'what are the newest developments about <{topic}>', '<{topic}> updates briefly']
TRAIN_TEMPLATES = [
    'latest news about <{topic}>', '<{topic}> news', 'news in <{topic}> today',
    'give me the latest <{topic}> news', 'any news on <{topic}>', 'headlines about <{topic}>',
    'what is happening in <{topic}>', 'what happened in <{topic}> today',
    "what's new with <{topic}>", 'recent developments in <{topic}>',
    'tell me the news about <{topic}> briefly', '<{topic}> headlines today',
    'show me updates about <{topic}>', 'what are the latest updates on <{topic}>',
    'a short news update on <{topic}> please', 'news for <{topic}>',
]
TEST_TEMPLATES = [
    'please give me <{topic}> news today', 'latest headlines from <{topic}>',
    'tell me about recent news in <{topic}>', 'any updates on <{topic}> today',
    '<{topic}> news please', 'what is the latest news about <{topic}>',
]
NEGATIVE = ['write a news article about {topic}', 'create a newsletter about {topic}',
            'make an image of {topic}', 'what is {topic}', 'explain {topic}',
            'write a story about {topic}', 'draw {topic}', 'how do news agencies cover {topic}',
            'write python code to fetch news for {topic}', 'what does news mean',
            'is your news model trained', 'hello', '2 + 7', 'who are you',
            'weather in {topic}', 'write a short poem about {topic}']
GENERAL = ['news', 'latest news', 'world news', 'global headlines', 'what is in the news',
           'give me today news', 'international news please', 'show me the latest headlines']


def example(template, topic, positive):
    marked = template.format(topic=topic)
    left = marked.find('<')
    if left >= 0:
        before, rest = marked.split('<', 1)
        middle, after = rest.split('>', 1)
        words = tokens(before) + tokens(middle) + tokens(after)
        labels = [0] * len(tokens(before)) + [1] * len(tokens(middle)) + [0] * len(tokens(after))
        text = marked.replace('<', '').replace('>', '')
    else:
        text = marked
        words = tokens(text)
        labels = [0] * len(words)
    return dict(text=text, words=words, labels=labels, news=int(positive), topic=topic if left >= 0 else '')


def fit(examples, feature_fn, label_fn, seed=220021):
    rng = random.Random(seed)
    rows = [(feature_fn(row), label_fn(row)) for row in examples]
    weights = {}
    sums = {}
    timestamps = {}
    step = 0
    for _ in range(35):
        rng.shuffle(rows)
        for features, target in rows:
            step += 1
            predicted = int(score(weights, features) > 0)
            if predicted == target:
                continue
            update = 1 if target else -1
            for key, value in features.items():
                sums[key] = sums.get(key, 0.) + (step - timestamps.get(key, 0)) * weights.get(key, 0.)
                timestamps[key] = step
                weights[key] = weights.get(key, 0.) + update * value
    return {key: round((sums.get(key, 0.) + (step - timestamps.get(key, 0)) * value) / step, 8)
            for key, value in weights.items()}


def main():
    out = ROOT / 'models' / 'cael-news-policy-v1'
    out.mkdir(exist_ok=True)
    train = [example(template, topic, True) for template in TRAIN_TEMPLATES for topic in TRAIN_TOPICS]
    train += [example(template, topic, False) for template in NEGATIVE for topic in TRAIN_TOPICS]
    train += [example(template, '', True) for template in GENERAL]
    train += [example('please ' + template + ' briefly', topic, True) for template in TRAIN_TEMPLATES for topic in TRAIN_TOPICS]
    held = [example(template, topic, True) for template in TEST_TEMPLATES for topic in TEST_TOPICS]
    held += [example(template, topic, False) for template in NEGATIVE for topic in TEST_TOPICS]
    intent = fit(train, lambda row: intent_features(row['words']), lambda row: row['news'])
    slots = [dict(words=row['words'], index=i, target=label) for row in train if row['news'] for i, label in enumerate(row['labels'])]
    topic_weights = fit(slots, lambda row: slot_features(row['words'], row['index']), lambda row: row['target'])
    model = dict(format='cael-news-policy-v1', architecture='Averaged linear perceptrons for news intent and token topic slots',
                 intent=intent, topic=topic_weights, training_examples=len(train), training_tokens=len(slots),
                 seed=220021, current_facts_stored=False, source='Authored synthetic request paraphrases, not news articles')
    model_path = out / 'policy.json'
    model_path.write_text(json.dumps(model, indent=2), encoding='utf-8')
    policy = NewsPolicy(model_path)
    correct = exact = positive = 0
    failures = []
    for row in held:
        parsed = policy.parse(row['text'])
        correct += int(bool(parsed) == bool(row['news']))
        if row['news']:
            positive += 1
            exact += int(parsed is not None and parsed['topic'] == row['topic'].lower())
        if bool(parsed) != bool(row['news']) or row['news'] and (not parsed or parsed['topic'] != row['topic'].lower()):
            failures.append(dict(text=row['text'], expected=row['topic'] if row['news'] else None, actual=parsed))
    report = dict(train_examples=len(train), heldout_examples=len(held), heldout_topics=TEST_TOPICS,
                  heldout_positive_templates=TEST_TEMPLATES, intent_correct=correct, intent_total=len(held),
                  topic_exact=exact, topic_total=positive, failures=failures,
                  limitation='Authored paraphrase holdout only; not independent real-user understanding or news truthfulness',
                  model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest())
    confirmation = [example(template, topic, True) for template in CONFIRM_TEMPLATES for topic in CONFIRM_TOPICS]
    confirmed = []
    for row in confirmation:
        parsed = policy.parse(row['text'])
        confirmed.append(dict(text=row['text'], correct=bool(parsed and parsed['topic'] == row['topic'].lower()), actual=parsed))
    report['confirmation'] = dict(correct=sum(row['correct'] for row in confirmed), total=len(confirmed), cases=confirmed,
                                  limitation='Separate authored templates and topic strings; same author and feature family')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    research = ROOT / 'research' / 'news_policy_022'
    research.mkdir(exist_ok=True)
    for name, examples in [('train', train), ('heldout', held)]:
        (research / (name + '.jsonl')).write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
