"""0.4.4 fixes for mistakes seen in development probes: jokes, recipe steps, myths, a bare "Why?", leg counts, visits."""
import unittest

from cael_unified import common_asks, reasoner, situations


def U(t):
    return dict(role='user', content=t)


def A(t):
    return dict(role='assistant', content=t)


class CommonAsksTest(unittest.TestCase):
    def test_jokes(self):
        r = common_asks.respond([U('Thanks! Can you tell me a joke?')])
        self.assertEqual(r['route'], 'chat/joke')
        self.assertTrue(r['response'].startswith('Sure! '))
        first = common_asks.respond([U('Tell me a joke.')])['response']
        again = common_asks.respond([U('Tell me a joke.'), A(first), U('Another one!')])['response']
        self.assertNotEqual(first, again)
        self.assertIsNone(common_asks.respond([U('Another one!')]))          # nothing to follow on from

    def test_recipe_steps(self):
        self.assertEqual(common_asks.respond([U('Then add some salt and stir.')])['route'], 'chat/recipe-step')
        for text in ('Add 5 and 7', 'Leave me alone', 'Mix it up a bit, I am bored', 'Add the numbers 4 and 9.'):
            self.assertIsNone(common_asks.respond([U(text)]), text)

    def test_myths(self):
        self.assertTrue(common_asks.respond([U('Is it true that all swans are white?')])['response'].startswith('**No.**'))
        self.assertIn('months', common_asks.respond([U('Do goldfish really have a 3 second memory?')])['response'])
        self.assertIsNone(common_asks.respond([U('I saw a swan today, it was white.')]))

    def test_bare_why_after_a_fact(self):
        self.assertEqual(common_asks.why_question([U('What is the capital of Italy?'), A('The capital of Italy is **Rome**.'), U('Why?')]),
                         'Why is Rome the capital of Italy?')
        self.assertIsNone(common_asks.why_question([U('Why?')]))
        off = dict(route='chat/web-single', response='Vienna and Bratislava are close.\nSource: What are the two closest capital cities? (x)')
        self.assertEqual(common_asks.why_checked('Why is Rome the capital of Italy?', off)['route'], 'chat/why-no-source')
        on = dict(route='chat/web-single', response='Canberra was a compromise.\nSource: When was Canberra founded? (x)')
        self.assertEqual(common_asks.why_checked('Why is Canberra the capital of Australia?', on), on)


class LegsAndVisitsTest(unittest.TestCase):
    def test_legs(self):
        r = reasoner.respond([U('I have 2 dogs and 3 cats. How many legs are there if I count only the dogs?')])
        self.assertTrue(r['response'].startswith('**8 legs**'))
        self.assertIn('The cats are not counted', r['response'])
        self.assertTrue(reasoner.respond([U('A farm has 3 cows and 5 chickens. How many legs are there in total?')])['response'].startswith('**22 legs**'))
        self.assertIsNone(reasoner.respond([U('How many legs do I have?')]))

    def test_visit_ideas(self):
        self.assertEqual(situations.respond([U('My brother is visiting next week. Any ideas for things to do?')])['route'], 'chat/situation')
        r = situations.respond([U('My brother is visiting next week. Any ideas for things to do?'), A('...'), U('It might rain though.')])
        self.assertTrue(r['response'].startswith('For bad weather'))
        self.assertIsNone(situations.respond([U('My brother is visiting next week.')]))


class TestInformedFixesTest(unittest.TestCase):
    """Fixes made after the sealed swarm-vs-single run (test-informed)."""

    def test_sums_in_words(self):
        self.assertTrue(reasoner.respond([U('What is 9 times 6?')])['response'].startswith('**54**'))
        self.assertTrue(reasoner.respond([U('Ok so um what is 7 times 8?')])['response'].startswith('**56**'))
        self.assertIsNone(reasoner.respond([U('I worked 9 times 6 days')]))

    def test_swarm_readings(self):
        from cael_unified import swarm_compute
        got = dict((n, m[-1]['content']) for n, m in swarm_compute.readings([U('Good evening! Can you convert 10 kilometres to miles please?')]))
        self.assertEqual(got['request'], 'Convert 10 kilometres to miles.')
        got = dict((n, m[-1]['content']) for n, m in swarm_compute.readings([U('How many miles is 10 kilometers?')]))
        self.assertEqual(got['convert'], 'Convert 10 kilometers to miles.')
        self.assertEqual(len(swarm_compute.readings([U('What is the capital of Spain?')])), 1)

    def test_swarm_pick_rules(self):
        from cael_unified import swarm_compute
        asked = dict(route='chat/web-single', response='The Times is a newspaper.')
        exact = dict(route='chat/reason-arith', response='**54** (9 × 6 = 54).')
        reply, picked, _ = swarm_compute.choose([('as asked', asked), ('core', exact)], [U('x')])
        self.assertEqual(picked, 'core')
        same = dict(route='chat/web-single', response='Other words.')
        reply, picked, _ = swarm_compute.choose([('as asked', asked), ('core', same)], [U('x')])
        self.assertEqual(picked, 'as asked')          # another reading must be strictly better


class SwarmReaderFixesTest(unittest.TestCase):
    def test_reader_fixes(self):
        from cael_unified import swarm
        say = lambda t: swarm.chat_reply([U(t)])['response']
        self.assertEqual(say('Day 1: Ben had 10 coins. Day 2: Ben spent 4 coins. Day 3: Ben found 2 coins. How many coins does Ben have?'),
                         '**8** (Day 1, Day 2, Day 3)')
        self.assertTrue(say('Scout A says the camp is by the lake. Scout B says the camp is by the lake. Where is the camp?').startswith('**lake**'))
        self.assertTrue(say('Log 1: The server was down at 2pm. Log 2: The server was up at 3pm. Is the server up?').startswith('**Yes**: up'))
        self.assertEqual(say('Part 1: The kettle was full. Part 2: Then it was empty. Is the kettle full?'), '**No**: empty (Part 2)')
        r = swarm.chat_reply([U('Witness 1: Zoe went to the library. Witness 2: Zoe went to the gym.'), A('ok'),
                              U('Witness 2 was half asleep. Where did Zoe go?')])
        self.assertTrue(r['response'].startswith('**library** (Witness 1)'))


if __name__ == '__main__':
    unittest.main()
