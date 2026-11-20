"""Swarm memory: binding names across agents, fixed consensus rules, and order-free merging with summaries."""
import random
import unittest

from cael_unified import swarm
from cael_unified.swarm import Claim, Link, Rule, Shards, State, claims_from_text, gossip, merged, tree


def C(entity, attribute, value, agent, **kw):
    return Claim(entity, attribute, value, agent, **kw)


class BindingTest(unittest.TestCase):
    def test_short_name_joins_the_one_longer_name(self):
        v = State([C('Dr. Sam Lee', 'job', 'doctor', 'A'), C('Sam', 'mood', 'happy', 'B'), C('Lee', 'age', '40', 'C')]).view()
        self.assertEqual(v.get('Sam', 'job').value, 'doctor')
        self.assertEqual(v.get('sam lee', 'mood').value, 'happy')
        self.assertEqual(v.get('Lee', 'age').value, '40')

    def test_two_possible_people_stay_apart(self):
        v = State([C('Sam Lee', 'job', 'doctor', 'A'), C('Sam Park', 'job', 'chef', 'B'), C('Sam', 'mood', 'happy', 'C')]).view()
        self.assertEqual(v.get('Sam', 'job').status, 'unknown')
        self.assertTrue(any('ambiguous' in n for n in v.notes))

    def test_explicit_links(self):
        s = State([C('Sam Lee', 'job', 'doctor', 'A'), C('Sam', 'mood', 'happy', 'B')], [Link('Sam', 'Sam Lee', 'distinct', 'B')])
        v = s.view()
        self.assertEqual(v.get('Sam', 'job').status, 'unknown')
        self.assertTrue(any('kept apart' in n for n in v.notes))
        v = State([C('the chef', 'mood', 'tired', 'A'), C('Marco', 'job', 'cook', 'B')], [Link('the chef', 'Marco', 'same', 'C')]).view()
        self.assertEqual(v.get('Marco', 'mood').value, 'tired')

    def test_pronouns_are_not_sent(self):
        with self.assertRaises(ValueError):
            C('she', 'mood', 'happy', 'A')


class ConsensusTest(unittest.TestCase):
    def test_many_copies_of_a_search_result_do_not_outvote_one_statement(self):
        s = State([C('lamp', 'colour', 'red', f'web{i}', kind='retrieved') for i in range(100)])
        s.add(C('lamp', 'colour', 'blue', 'reader'))
        cell = s.view().get('lamp', 'colour')
        self.assertEqual((cell.status, cell.value, cell.support), ('known', 'blue', ('reader',)))

    def test_later_reading_wins_and_same_position_conflicts(self):
        s = State([C('Sam', 'room', 'kitchen', 'A', at=(0, 1)), C('Sam', 'room', 'garden', 'B', at=(1, 1))])
        self.assertEqual(s.view().get('Sam', 'room').value, 'garden')
        s.add(C('Sam', 'room', 'office', 'C', at=(1, 1)))
        cell = s.view().get('Sam', 'room')
        self.assertEqual(cell.status, 'conflict')
        self.assertEqual(cell.sides, {'garden': ('B',), 'office': ('C',)})

    def test_an_agents_correction_replaces_its_claim(self):
        s = State([C('Sam', 'room', 'office', 'C', clock=1, at=(1, 1)), C('Sam', 'room', 'garden', 'B', at=(1, 1))])
        self.assertEqual(s.view().get('Sam', 'room').status, 'conflict')
        s.add(C('Sam', 'room', 'garden', 'C', clock=2, at=(1, 1)))
        self.assertEqual(s.view().get('Sam', 'room').value, 'garden')
        s.add(C('Sam', 'room', 'office', 'C', clock=3, at=(1, 1)))                # and back again: the highest clock counts
        self.assertEqual(s.view().get('Sam', 'room').status, 'conflict')

    def test_values_compare_by_meaning(self):
        s = State([C('Ana', 'apples', '3', 'A'), C('Ana', 'apples', '6/2', 'B'), C('Sam', 'room', 'The Kitchen', 'C'),
                   C('Sam', 'room', 'kitchen', 'D')])
        self.assertEqual(s.view().get('Ana', 'apples').status, 'known')
        self.assertEqual(s.view().get('Sam', 'room').support, ('C', 'D'))

    def test_changes_apply_on_top_of_another_agents_value(self):
        s = State([C('Ana', 'apples', '2', 'B', at=(1, 1), op='add'), C('Ana', 'apples', '1', 'C', at=(2, 1), op='subtract')])
        self.assertEqual(s.view().get('Ana', 'apples').status, 'unknown')
        s.add(C('Ana', 'apples', '3', 'A', at=(0, 1)))
        self.assertEqual(s.view().get('Ana', 'apples').value, '4')
        s.add(C('Ana', 'apples', '10', 'D', at=(1, 5)))          # a later stated value: only the change after it counts
        self.assertEqual(s.view().get('Ana', 'apples').value, '9')

    def test_rules_from_one_agent_apply_to_facts_from_another(self):
        s = State([C('Felix', 'kind', 'cat', 'A')], rules=[Rule('kind', 'cat', 'colour', 'black', 'B'),
                                                           Rule('colour', 'black', 'visible at night', 'no', 'C')])
        v = s.view()
        self.assertEqual(v.get('Felix', 'colour').value, 'black')
        self.assertEqual(v.get('Felix', 'visible at night').value, 'no')
        s.add(C('Felix', 'colour', 'white', 'D'))
        v = s.view()
        self.assertEqual(v.get('Felix', 'colour').value, 'white')               # stated beats derived ...
        self.assertTrue(any('rule exception' in n for n in v.notes))         # ... and the disagreement is reported
        self.assertEqual(v.get('Felix', 'visible at night').status, 'unknown')
        s = State([C('Felix', 'kind', 'cat', 'A')], rules=[Rule('kind', 'cat', 'colour', 'black', 'B'),
                                                           Rule('kind', 'cat', 'colour', 'ginger', 'C')])
        self.assertEqual(s.view().get('Felix', 'colour').status, 'conflict')


def random_world(rng, agents=12, claims=300, spread=3):
    names = ['Sam', 'Sam Lee', 'Lee', 'Ana', 'Ana Ruiz', 'Dr. Ana Ruiz', 'Ruiz', 'Felix', 'lamp', 'Marco', 'the chef', 'Sam Park']
    attrs = ['room', 'mood', 'apples', 'kind', 'colour']
    values = {'room': ['kitchen', 'garden', 'office'], 'mood': ['happy', 'sad'], 'apples': ['1', '2', '3', '5'],
              'kind': ['cat', 'dog'], 'colour': ['black', 'red', 'white']}
    out = []
    for _ in range(claims):
        a = rng.choice(attrs)
        kind = rng.choice(['stated', 'stated', 'derived', 'retrieved', 'default', 'trusted', 'doubted', 'confirmed'])
        op = rng.choice(['add', 'subtract']) if a == 'apples' and kind == 'stated' and rng.random() < 0.4 else 'set'
        out.append(Claim(rng.choice(names), a, rng.choice(values[a]), f'agent{rng.randrange(agents)}', clock=rng.randrange(4),
                         kind=kind, at=(rng.randrange(spread), rng.randrange(spread)) if rng.random() < 0.8 else (), op=op))
    links = [Link(rng.choice(names), rng.choice(names), rng.choice(['same', 'distinct']), 'linker') for _ in range(3)]
    links = [l for l in links if l.pair[0] != l.pair[1]]
    rules = [Rule('kind', 'cat', 'colour', 'black', 'r1'), Rule('colour', 'black', 'mood', 'happy', 'r2')]
    return out, links, rules


def split(rng, items, parts):
    buckets = [[] for _ in range(parts)]
    for item in items:
        buckets[rng.randrange(parts)].append(item)
    return buckets


class MergeTest(unittest.TestCase):
    """The same view whatever the order, grouping, repetition or summarising."""

    def test_order_grouping_and_summaries_do_not_change_the_view(self):
        statuses = set()
        for seed in range(40):
            rng = random.Random(seed)
            claims, links, rules = random_world(rng, claims=60 + 20 * (seed % 10), spread=1 + seed % 3)
            flat = State(claims, links, rules)
            want = flat.view().table()
            statuses |= {cell[0] for cells in want.values() for cell in cells.values()}
            parts = [State(c, links if i == 0 else (), rules if i == 1 else ()) for i, c in enumerate(split(rng, claims, 9))]
            shuffled = parts[:]
            rng.shuffle(shuffled)
            self.assertEqual(merged(shuffled).view().table(), want, seed)
            self.assertEqual(merged(parts + parts[:4]).view().table(), want, seed)                # repeats change nothing
            for fanout in (2, 3, 8):
                self.assertEqual(tree(shuffled, fanout)[0].view().table(), want, (seed, fanout))
            summary = flat.summary()
            self.assertEqual(tree(shuffled, 3)[0], summary, seed)                                  # the same set, too
            self.assertLessEqual(len(summary), len(flat))
            self.assertEqual(summary.view().table(), want, seed)
            self.assertEqual(summary.summary(), summary, seed)
            # summarising early never loses something a later merge needs
            early = merged([parts[0].summary(), parts[1].summary()]).summary()
            self.assertEqual(merged([early] + parts[2:]).view().table(), want, seed)
        self.assertEqual(statuses, {'known', 'conflict', 'unknown'})                              # every outcome was exercised

    def test_gossip_without_a_coordinator_converges(self):
        sent = {}
        for delta in (True, False):
            rng = random.Random(7)
            claims, links, rules = random_world(rng, agents=40, claims=400)
            nodes = [State(c) for c in split(rng, claims, 40)]
            nodes[0].merge(State(links=links, rules=rules))
            rounds, sent[delta] = gossip(nodes, rng, delta=delta)
            self.assertIsNotNone(rounds)
            self.assertLessEqual(rounds, 20)
            want = State(claims, links, rules).view().table()
            self.assertTrue(all(n.view().table() == want for n in nodes))
        self.assertLess(sent[True]['items'], sent[False]['items'] / 3)          # sending only what the puller lacks saves most of it


class ShardTest(unittest.TestCase):
    def test_sharded_views_equal_the_merged_view(self):
        for seed in range(30):
            rng = random.Random(100 + seed)
            claims, links, rules = random_world(rng, claims=60 + 20 * (seed % 10), spread=1 + seed % 3)
            want = State(claims, links, rules).view().table()
            shards = Shards(1 + seed % 7)
            for part in split(rng, claims, 5):
                shards.add(State(part))
            shards.add(State(links=links, rules=rules))
            self.assertEqual(shards.table(), want, seed)
            shards.summarise()
            self.assertEqual(shards.table(), want, seed)

    def test_one_entity_asks_only_the_nodes_holding_its_names(self):
        shards = Shards(50)
        for i in range(2000):
            shards.add(State([Claim(f'Person{i} Name{i}', 'room', 'kitchen', f'a{i}'), Claim(f'Person{i}', 'mood', 'ok', f'b{i}')]))
        cells, asked = shards.entity('Person7')
        self.assertEqual(cells['room'].value, 'kitchen')
        self.assertEqual(cells['mood'].value, 'ok')
        self.assertLessEqual(asked, 2)
        self.assertLess(max(shards.sizes()), 4000 / 20)                   # no node holds the whole world
        self.assertEqual(shards.directory_size(), 4000)                   # the shared directory: one entry per name


class ReadingTest(unittest.TestCase):
    def test_agents_reading_parts_of_one_story(self):
        story = ['Ana has 3 apples. The lamp\'s colour is red.',
                 'Ana gains 2 apples. Change the colour of the lamp to blue.',
                 "Ana's mood is happy. Ana loses 1 apple."]
        states = [State(claims_from_text(f'reader{i}', part, part=i)) for i, part in enumerate(story)]
        v = merged(reversed(states)).view()
        self.assertEqual(v.get('Ana', 'apples').value, '4')
        self.assertEqual(v.get('lamp', 'colour').value, 'blue')
        self.assertEqual(v.get('Ana', 'mood').value, 'happy')
        self.assertEqual(v.get('Ana', 'apples').support, ('reader0', 'reader1', 'reader2'))

    def test_swarm_answers_a_question(self):
        story = ["Ana has 3 apples. The lamp's colour is red.",
                 'Ana gains 2 apples. Change the colour of the lamp to blue.',
                 "Ana's mood is happy. Ana loses 1 apple."]
        self.assertEqual(swarm.answer(story, 'How many apples does Ana have?')['response'], '**4** (reader1, reader2, reader3)')
        self.assertTrue(swarm.answer(story, 'What colour is the lamp?')['response'].startswith('**blue**'))
        self.assertEqual(swarm.answer(story, 'Where is Sam?')['route'], 'chat/swarm-unknown')
        self.assertIsNone(swarm.answer(story, 'Who painted the Mona Lisa?'))
        r = swarm.answer(['Ana gains 2 apples.', 'Ana loses 1 apple.'], 'How many apples does Ana have?')
        self.assertIn('only changes are known', r['response'])


def U(text):
    return [dict(role='user', content=text)]


class SwarmDeskTest(unittest.TestCase):
    """The Swarm desk in chat: labelled accounts or parts and one question."""

    def reply(self, text):
        return swarm.chat_reply(U(text))

    def test_separate_accounts_that_differ_are_reported(self):
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Where is Sam?')
        self.assertEqual(r['route'], 'chat/swarm-conflict')
        self.assertIn('**kitchen** (Witness 1)', r['response'])
        self.assertIn('**garden** (Witness 2)', r['response'])
        r = self.reply("Report A: The van's colour is white. Report B: The van's colour is white. Report C: The van's colour is grey. "
                       'What colour is the van?')
        self.assertIn('**white** (Report A, Report B)', r['response'])         # two reports against one is still not a vote
        self.assertEqual(r['route'], 'chat/swarm-conflict')

    def test_agreeing_accounts(self):
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam is in the kitchen. Where is Sam?')
        self.assertEqual(r['response'], '**kitchen** (Witness 1, Witness 2). The sources agree.')

    def test_parts_are_a_timeline(self):
        r = self.reply('Part 1: Ana has 3 apples. Part 2: Ana gains 2 apples. Part 3: Ana loses 1 apple. How many apples does Ana have?')
        self.assertEqual(r['response'], '**4** (Part 1, Part 2, Part 3)')
        r = self.reply('Day 1: Sam went to the kitchen. Day 2: Sam moved to the office. Where is Sam now?')
        self.assertEqual(r['response'], '**office** (Day 2)')

    def test_says_labels_pronouns_and_which_questions(self):
        r = self.reply('Source 1 says the meeting is on Monday. Source 2 says it is on Tuesday. Which is right?')
        self.assertIn('**Monday** (Source 1); **Tuesday** (Source 2)', r['response'])
        r = self.reply('Source 1 says the meeting is on monday. Source 2 says the meeting is on Monday at 3pm. When is the meeting?')
        self.assertEqual(r['response'], '**Monday** (Source 1, Source 2). The sources agree. Time: **3pm** (Source 2).')
        r = self.reply('Report 1: the train is at 9:15. Report 2: the train is at 9:45. What time is the train?')
        self.assertIn('**9:15** (Report 1); **9:45** (Report 2)', r['response'])

    def test_left_alone(self):
        for text in ('Ana has 3 apples. Ana gains 2 apples. How many apples does Ana have?',
                     'Step 1: Preheat the oven. Step 2: Mix the flour and sugar. How long should it bake?',
                     'Part 1: I love hiking. Part 2: I hate rain. What should I do this weekend?',
                     'Source A says I should rest. Source B says I should run. Which is right?',
                     "Source A: The lamp's colour is red. Source B: Sam went to the hall. Where is Ana?",
                     'Witness 1: Sam went to the kitchen. Day 2: Sam went to the garden. Where is Sam?'):
            self.assertIsNone(self.reply(text), text)


def turns(*texts):
    out = []
    for i, t in enumerate(texts):
        out.append(dict(role='user', content=t))
        if i < len(texts) - 1:
            out.append(dict(role='assistant', content='Noted.'))
    return out


class SwarmDeskUpgradeTest(unittest.TestCase):
    """Accounts over several messages, trust, more statement forms, yes/no and earlier-value questions."""

    def reply(self, *texts):
        return swarm.chat_reply(turns(*texts))

    def test_accounts_spread_over_messages(self):
        r = self.reply('Witness 1: Sam went to the kitchen.', 'Witness 2: Sam went to the garden.', 'Where is Sam?')
        self.assertEqual(r['route'], 'chat/swarm-conflict')
        for text in ('What is the capital of France?', 'Thanks! Can you also tell me a joke?', 'Where is Ana?'):
            self.assertIsNone(self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden.', text), text)

    def test_trust_and_doubt(self):
        r = self.reply('Witness 1 says Sam went to the kitchen. Witness 2 says Sam went to the garden.', 'Witness 2 was drunk. Where is Sam?')
        self.assertEqual(r['response'], '**kitchen** (Witness 1). Witness 2 said **garden**. '
                                        'I set that aside because you said not to rely on Witness 2.')
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Witness 3: Sam went to the garden. '
                       'Trust Witness 1. Where is Sam?')
        self.assertTrue(r['response'].startswith('**kitchen** (Witness 1). Witness 2 and Witness 3 said **garden**.'), r['response'])
        r = self.reply('Report A: The van was white. Report B: The van was grey. Report C: The van was grey. Ignore Report C. '
                       'What colour was the van?')
        self.assertEqual(r['route'], 'chat/swarm-conflict')
        self.assertIn('(Left out, as you asked: Report C.)', r['response'])
        r = self.reply("Source 1 says the meeting is on Monday. Source 2 says it is on Tuesday. Don't trust Source 1. When is the meeting?")
        self.assertTrue(r['response'].startswith('**Tuesday** (Source 2)'), r['response'])
        self.assertEqual(swarm.trust_of('Do not trust the second witness. Witness 3 is reliable.'),
                         {'witness 2': 'doubted', 'witness 3': 'trusted'})

    def test_adjectives_and_yes_no(self):
        self.assertEqual(self.reply('Witness 1: The van was white. Witness 2: The van looked white. Was the van white?')['response'],
                         '**Yes**: white (Witness 1, Witness 2). The sources agree.')
        self.assertTrue(self.reply('Witness 1: The car was red. Witness 2: the car was red. Was the car blue?')['response'].startswith('**No**: red'))
        self.assertEqual(self.reply('Witness 1: Sam was nervous. Witness 2: Sam was calm. How did Sam seem?')['route'], 'chat/swarm-conflict')
        self.assertEqual(self.reply('Day 1: Sam went to the kitchen. Day 2: Sam moved to the office. Is Sam in the office?')['response'],
                         '**Yes**: office (Day 2)')

    def test_earlier_values_on_a_timeline(self):
        days = 'Day 1: Sam went to the kitchen. Day 2: Sam moved to the office. Day 3: Sam went to the garden. '
        self.assertEqual(self.reply(days + 'Where was Sam at first?')['response'], 'At first: **kitchen** (Day 1)')
        self.assertEqual(self.reply(days + 'Where was Sam on Day 2?')['response'], 'By Day 2: **office** (Day 2)')
        self.assertEqual(self.reply(days + 'Where is Sam?')['response'], '**garden** (Day 3)')
        r = self.reply('Part 1: Ana has 3 apples. Part 2: Ana gains 2 apples. Part 3: Ana loses 1 apple. '
                       'How many apples did Ana have after Part 2?')
        self.assertEqual(r['response'], 'By Part 2: **5** (Part 1, Part 2)')
        self.assertIsNone(self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Where was Sam at first?'))

    def test_accounts_without_a_question_are_noted(self):
        r = self.reply('Witness 1: Sam went to the kitchen.', 'Witness 2: Sam went to the garden.')
        self.assertEqual(r['response'], 'Noted. Witness 2: Sam was in the **garden**. So far the accounts differ on where Sam was. '
                                        'Add more accounts, or ask your question.')
        for text in ('Witness 1: Sam went to the kitchen. I am worried about the whole thing honestly.',
                     'Step 1: Preheat the oven. Step 2: Mix the flour.'):
            self.assertIsNone(self.reply(text), text)

    def test_one_reader_for_the_users_own_statements(self):
        self.assertEqual(self.reply('My car is red. What colour is my car?')['response'], '**red**, as you told me.')
        self.assertEqual(self.reply('My car is red.', 'Actually my car is blue now.', 'What colour is my car?')['response'],
                         '**blue**, as you told me.')
        self.assertEqual(self.reply('My keys are in the kitchen.', 'Where are my keys?')['response'], 'In the **kitchen**, as you told me.')
        self.assertTrue(self.reply('Sam is happy. Is Sam sad?')['response'].startswith('**No**, happy'))
        self.assertEqual(self.reply('My sister is visiting on Saturday. When is my sister visiting?')['response'],
                         '**Saturday**, as you told me.')
        self.assertEqual(self.reply('My flight leaves at 9:40.', 'What time does my flight leave?')['response'], '**9:40**, as you told me.')
        self.assertEqual(self.reply('My keys are in the kitchen.')['response'], 'Noted: your keys are in the kitchen. Ask me any time.')
        self.assertEqual(self.reply('Actually my car is blue now.')['response'], 'Noted: your car is blue. Ask me any time.')
        for text in ('My boss is angry.', 'My car is red and I hate it.', 'I feel sad today.', 'Then add some salt and stir.',
                     'The van was white.', 'Mystery is fun.'):
            self.assertIsNone(self.reply(text), text)
        for convo in (('My car is red.', 'My car got resprayed last week.', 'What colour is my car?'),   # not followed: no stale answer
                      ('Where is Paris?',), ('I went to the shop. Where is the shop?',),
                      ('My cat is called Tom. What is my cat called?',),
                      ('Ana has 3 apples. Ana gains 2 apples. How many apples does Ana have?',)):
            self.assertIsNone(self.reply(*convo), convo)

    def test_a_trusted_value_keeps_later_changes(self):
        # a change placed after a trusted value; the summary must not drop it
        s = State([C('Ana', 'apples', '3', 'A', kind='trusted', at=(0, 1)), C('Ana', 'apples', '9', 'B', at=(2, 1)),
                   C('Ana', 'apples', '2', 'C', at=(1, 1), op='add')])
        self.assertEqual(s.view().get('Ana', 'apples').value, '5')
        self.assertEqual(s.summary().view().get('Ana', 'apples').value, '5')


class SwarmRound5Test(unittest.TestCase):
    """Sightings at times, descriptions bound to names, sources proved wrong, and "why?"."""

    def reply(self, *texts):
        return swarm.chat_reply(turns(*texts))

    def test_sightings_at_different_times_are_not_a_conflict(self):
        two = 'Witness 1: Sam was in the kitchen at 2pm. Witness 2: Sam was in the garden at 3pm. '
        self.assertEqual(self.reply(two + 'Where is Sam?')['response'],
                         '**garden** (Witness 2). That is the latest sighting, at 3pm. Earlier: **kitchen** at 2pm (Witness 1).')
        self.assertEqual(self.reply(two + 'Where was Sam at 2pm?')['response'], 'At 2pm: **kitchen** (Witness 1).')
        r = self.reply('Witness 1: At 3pm, Sam was in the kitchen. Witness 2: Sam was in the garden at 3pm. Where was Sam at 3pm?')
        self.assertTrue(r['response'].startswith('At 3pm, the sources disagree'), r['response'])
        self.assertEqual(swarm.minutes('12:30pm'), 750)
        self.assertEqual(swarm.minutes('noon'), 720)

    def test_descriptions_bind_to_names(self):
        self.assertEqual(self.reply('Witness 1: The driver was Sam. Witness 2: The driver was in the garden. Where is Sam?')['response'],
                         '**garden** (Witness 2). This rests on Witness 1: the driver was Sam.')
        r = self.reply('Witness 1: The man in the red hat went to the kitchen. Witness 2: The man in the red hat was Marco. '
                       'Where is Marco?')
        self.assertTrue(r['response'].startswith('**kitchen** (Witness 1)'))
        self.assertEqual(swarm.described('Sam was the driver'), ('the driver', 'Sam'))
        for clause in ('The van was White', 'The meeting is Monday', 'Sam said the van was white'):
            self.assertIsNone(swarm.described(clause), clause)
        # a description is not a longer name for one of its own words
        v = State([C('man in the red hat', 'room', 'hall', 'A'), C('hat', 'colour', 'red', 'B')]).view()
        self.assertEqual(v.get('hat', 'room').status, 'unknown')

    def test_reported_speech_is_not_a_fact(self):
        unread = []
        self.assertEqual(claims_from_text('A', 'Sam said the van was white.', unread=unread, timeline=False), [])
        self.assertEqual(len(unread), 1)

    def test_a_source_proved_wrong_counts_less_elsewhere(self):
        r = self.reply('Witness 1: Sam went to the kitchen. The van was white. Witness 2: Sam went to the garden. The van was grey.',
                       'It turns out Sam was in the kitchen. What colour was the van?')
        self.assertEqual(r['response'], '**white** (Witness 1). Witness 2 said **grey**. '
                                        'I set that aside because Witness 2 got where Sam was wrong, going by what you told me.')
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden.', 'I know Sam was in the kitchen. Where was Sam?')
        self.assertEqual(r['response'], '**kitchen** (what you told me). Witness 2 said **garden**. '
                                        'I set that aside because it goes against what you told me.')
        # a source the user said to trust is not demoted
        r = self.reply('Witness 1: Sam went to the kitchen. The van was white. Witness 2: Sam went to the garden. The van was grey. '
                       'Trust Witness 2.', 'It turns out Sam was in the kitchen. What colour was the van?')
        self.assertTrue(r['response'].startswith('**grey** (Witness 2)'), r['response'])

    def test_why_shows_each_sources_words(self):
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Witness 2 was drunk. Where is Sam?', 'Why?')
        self.assertEqual(r['route'], 'chat/swarm-why')
        self.assertIn('- Witness 1: "Sam went to the kitchen" (used)', r['response'])
        self.assertIn('- Witness 2: "Sam went to the garden" (set aside: you said not to rely on it)', r['response'])
        r = self.reply('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Where is Sam?', 'How do you know?')
        self.assertIn('Two against one is not proof.', r['response'])
        r = self.reply('Day 1: Sam went to the kitchen. Day 2: Sam moved to the office. Where is Sam?', 'Why?')
        self.assertIn('(replaced by a later part)', r['response'])
        for convo in (('Why is the sky blue?',), ('My car is red. What colour is my car?', 'Why?'),
                      ('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Where is Sam?', 'Why is the sky blue?')):
            self.assertIsNone(self.reply(*convo), convo)


class ReviewFixesTest(unittest.TestCase):
    """Changes after an outside review of 0.4.4: corrections withdraw links, confirmed vs seen, reader coverage, rewrites."""

    def reply(self, *texts):
        return swarm.chat_reply(turns(*texts))

    def test_a_correction_withdraws_what_rested_on_a_link(self):
        told = ('Witness 1: The driver was Sam. Witness 2: The driver ran to the station.', 'Witness 1: Actually the driver was Tom.')
        self.assertTrue(self.reply(*told, 'Where is Tom?')['response'].startswith('**station** (Witness 2). This rests on Witness 1: '
                                                                                  'the driver was Tom.'))
        self.assertTrue(self.reply(*told, 'Where is Sam?')['response'].startswith('Nobody places Sam now.'))
        why = self.reply(*told, 'Where is Tom?', 'Why?')['response']
        self.assertIn('"the driver was Sam" (withdrawn', why)
        r = self.reply('Witness 1: The driver was Sam. Witness 2: The driver ran to the station.', 'Witness 1: Sorry, the driver was not Sam.',
                       'Where is Sam?')
        self.assertNotIn('station', r['response'])
        from cael_unified.swarm import Link, live_links
        old, new = Link('the driver', 'Sam', 'same', 'W1', 1), Link('the driver', 'Tom', 'same', 'W1', 2)
        self.assertEqual(live_links({old, new}), {new})

    def test_a_rule_chain_is_recomputed_when_a_premise_falls(self):
        s = State([C('Felix', 'kind', 'cat', 'A'), C('Felix', 'kind', 'dog', 'B')],
                  rules=[Rule('kind', 'cat', 'colour', 'black', 'R'), Rule('colour', 'black', 'visible', 'no', 'R')])
        v = s.view()
        self.assertEqual(v.get('Felix', 'kind').status, 'conflict')
        self.assertEqual(v.get('Felix', 'colour').status, 'unknown')           # nothing derived from a disputed premise
        self.assertEqual(v.get('Felix', 'visible').status, 'unknown')

    def test_last_confirmed_and_last_seen_differ(self):
        told = ('Witness 1: The van was in Acre at 11am.', 'I can confirm the van was in Haifa at 9.')
        self.assertEqual(self.reply(*told, 'Where was the van last confirmed?')['response'], '**Haifa** (what you told me).')
        self.assertEqual(self.reply(*told, 'Where was the van last seen?')['response'], 'Last seen at 11am: **Acre** (Witness 1).')
        r = self.reply(*told, 'Where is the van?')['response']
        self.assertTrue(r.startswith('**Haifa** (what you told me). That is as of 9am. A later sighting ranks lower: **Acre** at 11am'), r)
        self.assertNotIn('set that aside', r)

    def test_unread_sentences_about_the_subject_are_flagged(self):
        r = self.reply('Witness 1: Sam went to the kitchen. Then he drove off in the van. Witness 2: Sam went to the kitchen. Where is Sam?')
        self.assertIn('I could not read this sentence, which may change the answer: Witness 1: "he drove off in the van"', r['response'])
        r = self.reply('Witness 1: Sam went to the kitchen. The weather was lovely and warm. Witness 2: Sam went to the garden. Where is Sam?')
        self.assertNotIn('could not read', r['response'])                        # not about Sam
        self.assertEqual(r['swarm']['unread'], {'Witness 1': ['The weather was lovely and warm']})

    def test_rewrites_keep_what_is_asked(self):
        from cael_unified import swarm_compute
        self.assertFalse(swarm_compute.preserves('How many more miles do I need to reach 10 miles if I have walked 10 km?',
                                                 'Convert 10 km to miles.'))
        self.assertTrue(swarm_compute.preserves('How many miles is 10 kilometers?', 'Convert 10 kilometers to miles.'))
        found = swarm_compute.readings(U('How many more miles do I need to reach 10 miles if I have walked 10 km?'))
        self.assertEqual([n for n, _ in found], ['as asked'])


class SwarmInChatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        import tempfile
        from pathlib import Path
        from cael_unified import Assistant
        tmp = Path(tempfile.mkdtemp())
        os.environ.update(CAEL_LTM=str(tmp / 'ltm.json'), CAEL_MEMORY_FILE=str(tmp / 'memory.json'))
        cls.engine = Assistant(output_root=tmp / 'o')

    def test_the_team_hands_labelled_accounts_to_the_swarm(self):
        r = self.engine.respond(U('Witness 1: Sam went to the kitchen. Witness 2: Sam went to the garden. Where is Sam?'),
                                n=1, seed=137, mode='chat')
        self.assertEqual(r['route'], 'chat/swarm-conflict')
        self.assertTrue(any('Swarm' in step['agent'] for step in r.get('team', [])))


if __name__ == '__main__':
    unittest.main()
