"""CAEL 0.4.3 work: remainders and fractions, the Supporter's waiting and what-if turns, casual rewrites, follow-up knowledge
and coherence's kind check. Conversations here are development cases, not the self-test's own."""
import unittest

from cael_unified import calc_agent, coherence, followup_kb, support, writer_agent


def talk(module, turns):
    msgs, out = [], []
    for t in turns:
        msgs.append(dict(role='user', content=t))
        r = module.respond(msgs)
        out.append(r)
        msgs.append(dict(role='assistant', content=(r or {}).get('response', '')))
    return out


class Remainder(unittest.TestCase):
    def test_split_the_rest(self):
        r = talk(calc_agent, ["A trip costs $1,800 and we pay a 20% deposit now. How much is the deposit?",
                              "If we split the rest equally between 3 people, how much does each pay?"])
        self.assertIn('$360', r[0]['response'])
        self.assertIn('**$480 each**', r[1]['response'])

    def test_fraction_then_months(self):
        r = talk(calc_agent, ["A bike costs $640. I pay a quarter up front. How much is that?",
                              "And if I pay the remainder over 8 months, how much per month?"])
        self.assertIn('**$160**', r[0]['response'])
        self.assertIn('**$60 per month**', r[1]['response'])

    def test_left_to_pay(self):
        r = talk(calc_agent, ["The sofa is $1,200 and I put half down. How much do I pay now?", "How much is left to pay?"])
        self.assertIn('**$600**', r[1]['response'])


class Supporter(unittest.TestCase):
    def test_terrified_and_what_ifs(self):
        r = talk(support, ["I have a job interview tomorrow and I'm terrified.", "What if my mind goes blank?", "Any tips for tonight?",
                           "What if they ask something I don't know?"])
        self.assertTrue(all(x is not None for x in r))
        self.assertIn('blank', r[1]['response'])
        self.assertIn('tonight', r[2]['response'])
        self.assertIn("not sure", r[3]['response'])

    def test_waiting_for_results_is_not_a_setback(self):
        r = talk(support, ["I'm so anxious about my exam results coming out on Friday.", "I'm scared I failed.", "How do I stop worrying?"])
        self.assertIn('Waiting', r[0]['response'])
        self.assertNotIn('feedback', r[2]['response'])
        self.assertIn('results', r[2]['response'])


class Casual(unittest.TestCase):
    def test_casual_is_not_warmer(self):
        r = talk(writer_agent, ["Write a short note to my neighbour thanking her for watering my plants.", "Can you make it more casual?"])
        self.assertIn('Hi ', r[1]['response'])
        self.assertIn('Cheers', r[1]['response'])
        self.assertNotIn('With love', r[1]['response'])


class FollowUps(unittest.TestCase):
    def test_car_brakes(self):
        msgs = [dict(role='user', content='My car brakes squeak when I stop.'), dict(role='assistant', content='ok'),
                dict(role='user', content='How do I clean them?')]
        r = followup_kb.respond(msgs)
        self.assertIn('brake cleaner', r['response'])

    def test_part_question(self):
        msgs = [dict(role='user', content='The brakes on my bicycle make a horrible screech.'), dict(role='assistant', content='ok'),
                dict(role='user', content='Could it be the pads?')]
        self.assertIn('pads', followup_kb.respond(msgs)['response'])

    def test_unknown_thing_is_left_alone(self):
        msgs = [dict(role='user', content='My piano sounds out of tune.'), dict(role='assistant', content='ok'),
                dict(role='user', content='How do I clean it?')]
        self.assertIsNone(followup_kb.respond(msgs))


class Coherence(unittest.TestCase):
    def test_bike_advice_for_a_car_is_off_topic(self):
        turns = ['My car brakes squeak when I stop.', 'Is it the pads?']
        self.assertTrue(coherence.wrong_kind(turns, 'Toe the pads in towards the rim of your bike.'))
        self.assertFalse(coherence.wrong_kind(turns, 'Check the pads and the discs.'))

    def test_resolved_question(self):
        msgs = [dict(role='user', content='Our kitchen sink drain smells bad.'), dict(role='assistant', content='ok'),
                dict(role='user', content='How do I clean it?')]
        self.assertEqual(coherence.resolved_question(msgs), 'How do I clean our kitchen sink drain?')


if __name__ == '__main__':
    unittest.main()
