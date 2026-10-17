"""Train public-fact routing on authored paraphrases, with unseen place holdouts."""
import json
from .bundle import ROOT
from .news_policy import tokens, intent_features
from .train_news_policy import fit
from .request_policy import RequestPolicy, slot_features

TEMPLATES = {
    'weather': ['weather in <{}>', '<{}> weather today', 'forecast for <{}>', 'will it rain in <{}> tomorrow',
                'how hot is it in <{}>', 'temperature in <{}>', 'is it windy in <{}>', 'will it snow in <{}>',
                'what is the weather like in <{}>', 'give me the forecast for <{}> please'],
    'sports': ['<{}> updates', 'latest <{}> news', 'give me <{}> headlines', 'what is happening in <{}>',
               'recent <{}> news please', '<{}> news today'],
    'live-sports': ['what is the {} score', 'live {} scores', '{} fixtures today', 'who won the {} match',
                    'when is the next {} game', '{} results today', 'show {} standings', 'latest {} league table'],
    'faq': ['what is {}', 'who is {}', 'where is {}', 'explain {}', 'tell me about {}', 'define {}',
            'what is the capital of {}', 'how many people live in {}', 'when was {} born'],
    'other': ['write a story about {}', 'make an image of {}', 'hello {}', 'help me with {}',
              'write code for {}', 'your {} model', 'my {} settings', 'write a poem about {}',
              'what does weather mean', 'define temperature', 'explain rain', 'what is football',
              'news about {}', '{} headlines'],
}
SUBJECTS = {
    'weather': ['London', 'Paris', 'New York', 'Tokyo', 'Jerusalem', 'Berlin', 'Los Angeles', 'Rome'],
    'sports': ['sports', 'football', 'basketball', 'tennis', 'NBA', 'Formula One', 'cricket', 'baseball'],
    'live-sports': ['football', 'NBA', 'tennis', 'Manchester United', 'Arsenal', 'Lakers', 'F1', 'cricket'],
    'faq': ['France', 'Canada', 'Albert Einstein', 'photosynthesis', 'a capybara', 'Mount Everest', 'Japan', 'gravity'],
    'other': ['Canada', 'sports', 'weather', 'news', 'Paris', 'football', 'temperature', 'rain'],
}
HELD = {
    'weather': [('will it rain in <{}> tonight', 'Cape Town'), ('<{}> forecast please', 'Tel Aviv'),
                ('what is the temperature in <{}> tomorrow', 'San Francisco'), ('is it snowing in <{}>', 'Helsinki'),
                ('weather for <{}> right now', 'Mexico City'), ('wind in <{}> today', 'Sydney')],
    'sports': [('show me recent <{}> updates', 'hockey'), ('<{}> headlines please', 'rugby'),
               ('any <{}> news today', 'cycling'), ('latest <{}> updates briefly', 'Olympics')],
    'live-sports': [('what was the {} score', 'Chelsea'), ('{} fixtures tomorrow', 'Liverpool'),
                    ('who won the {} game', 'Celtics'), ('{} league standings', 'hockey')],
    'faq': [('what is the capital of {}', 'Norway'), ('when was {} born', 'Marie Curie'),
            ('where is {}', 'Lake Baikal'), ('what is {}', 'an axolotl'), ('how many people live in {}', 'Sweden')],
    'other': [('write a {} news article', 'hockey'), ('my {} settings', 'weather'), ('draw {}', 'rain'),
              ('what is the {} model trained on', 'your'), ('{}', 'hello'), ('{}', '2 + 7')],
}


def example(template, subject, intent):
    marked = template.format(subject)
    if '<' in marked:
        before, rest = marked.split('<', 1)
        middle, after = rest.split('>', 1)
        labels = [0] * len(tokens(before)) + [1] * len(tokens(middle)) + [0] * len(tokens(after))
    else:
        labels = [0] * len(tokens(marked))
    text = marked.replace('<', '').replace('>', '')
    return dict(text=text, words=tokens(text), labels=labels, intent=intent,
                subject=subject.lower() if '<' in marked else '')


def main():
    train = [example(template, subject, intent) for intent, templates in TEMPLATES.items()
             for template in templates for subject in SUBJECTS[intent]]
    train += [example('please ' + template + ' briefly', subject, intent) for intent, templates in TEMPLATES.items()
              for template in templates for subject in SUBJECTS[intent]]
    model = dict(format='cael-request-policy-v1', architecture='Averaged linear classifiers and token slot taggers',
                 intents={}, slots={}, training_examples=len(train), source='Authored request paraphrases; no facts memorized')
    for intent in TEMPLATES:
        model['intents'][intent] = fit(train, lambda row: intent_features(row['words']), lambda row: int(row['intent'] == intent))
    for intent in ('weather', 'sports'):
        rows = [dict(words=row['words'], index=i, target=target) for row in train if row['intent'] == intent
                for i, target in enumerate(row['labels'])]
        model['slots'][intent] = fit(rows, lambda row: slot_features(row['words'], row['index']), lambda row: row['target'])
    out = ROOT / 'models' / 'cael-request-policy-v1'
    out.mkdir(exist_ok=True)
    (out / 'policy.json').write_text(json.dumps(model, indent=2), encoding='utf-8')
    policy = RequestPolicy()
    held = [example(template, subject, intent) for intent, cases in HELD.items() for template, subject in cases]
    cases = []
    for row in held:
        actual = policy.parse(row['text'])
        cases.append(dict(text=row['text'], expected=row['intent'], subject=row['subject'], actual=actual,
                          correct=actual['intent'] == row['intent'] and (not row['subject'] or actual['subject'] == row['subject'])))
    report = dict(training_examples=len(train), correct=sum(c['correct'] for c in cases), total=len(cases), cases=cases,
                  limitation='Authored holdout paraphrases and unseen subjects; not independent user evaluation or fact accuracy')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    research = ROOT / 'research' / 'request_policy_022'
    research.mkdir(exist_ok=True)
    (research / 'train.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in train), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
