"""Train question-form classifiers with topic and template holdouts."""
import json
from .bundle import ROOT
from .news_policy import intent_features
from .train_news_policy import fit
from .knowledge_query import KnowledgeQuery, words, form_features

FORMS = {
 'definition': ['what is {}', 'what are {}', 'explain {}', 'define {}', 'tell me about {}', 'describe {}'],
 'cause': ['why does {} happen', 'what causes {}', 'why is {} important', 'what is the cause of {}'],
 'mechanism': ['how does {} work', 'how do {} work', 'how does {} happen', 'explain the process of {}', 'how is {} produced'],
 'location': ['where is {}', 'where are {} found', 'what country is {} in', 'where does {} occur'],
 'time': ['when did {} happen', 'when was {} invented', 'when did {} start', 'when was {} born'],
 'comparison': ['compare {} and {}', 'what is the difference between {} and {}', '{} versus {}', 'difference between {} and {}'],
}
TRAIN = ['gravity', 'photosynthesis', 'electric motors', 'rain', 'computers', 'volcanoes', 'water', 'Rome',
         'the Renaissance', 'evolution', 'tennis', 'DNA', 'inflation', 'algorithms', 'music', 'democracy', 'black holes', 'light']
HELD = ['osmosis', 'earthquakes', 'Kyoto', 'a steam engine', 'the printing press', 'coral reefs']
CONFIRM = {'definition': ['what exactly is {}', 'give a definition of {}'],
           'cause': ['why do we get {}', 'why does {} occur'],
           'mechanism': ['how exactly does {} work', 'how is {} formed'],
           'location': ['where can {} be found', 'where in the world is {}'],
           'time': ['when in history did {} begin', 'when was {} first developed'],
           'comparison': ['how do {} and {} differ', 'what distinguishes {} from {}']}


def rows(topics, forms):
    return [dict(text=template.format(topic, topics[(i + 1) % len(topics)]), kind=kind)
            for kind, templates in forms.items() for template in templates for i, topic in enumerate(topics)]


def main():
    train = rows(TRAIN, FORMS)
    train += [dict(text='please ' + row['text'] + ' briefly', kind=row['kind']) for row in train]
    out = ROOT / 'models/cael-knowledge-v1'
    out.mkdir(exist_ok=True)
    model = dict(format='cael-knowledge-query-v1', architecture='Classical averaged linear question-form classifiers',
                 intents={kind: fit(train, lambda row: form_features(words(row['text'])), lambda row: int(row['kind'] == kind)) for kind in FORMS},
                 training_examples=len(train), limitations='Question forms, not arbitrary language comprehension or factual reasoning')
    (out / 'query_policy.json').write_text(json.dumps(model, indent=2), encoding='utf-8')
    policy = KnowledgeQuery()
    report = {}
    for name, cases in [('topic_holdout', rows(HELD, FORMS)), ('template_confirmation', rows(HELD, CONFIRM))]:
        scored = [dict(**row, actual=(policy.parse(row['text']) or {}).get('kind')) for row in cases]
        report[name] = dict(correct=sum(row['kind'] == row['actual'] for row in scored), total=len(scored),
                            failures=[row for row in scored if row['kind'] != row['actual']])
    report['training_examples'] = len(train)
    report['limitation'] = 'Authored paraphrases, not independent real-user comprehension tests'
    (out / 'query_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    research = ROOT / 'research/knowledge_023'
    research.mkdir(exist_ok=True)
    (research / 'query_training.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in train), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
