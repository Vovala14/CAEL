"""0.4.4: the Reasoner (word problems, puzzles, rules about individuals, follow-ups on a result), city time conversion,
everyday situations with follow-ups, and black-hole follow-ups."""
import unittest

from cael_unified import about_me, concepts, reasoner, situations


def U(t):
    return dict(role='user', content=t)


def A(t):
    return dict(role='assistant', content=t)


def ask(module, *turns):
    """Run the turns through one desk, feeding its own replies back as the assistant's."""
    history = []
    reply = None
    for t in turns:
        history.append(U(t))
        reply = module.respond(history)
        history.append(A(reply['response'] if reply else '...'))
    return reply


class ReasonerTest(unittest.TestCase):
    def check(self, text, expected):
        r = reasoner.respond([U(text)])
        self.assertIsNotNone(r, text)
        self.assertIn(expected, r['response'], text)

    def story(self, text, expected):
        r = reasoner.story_reply([U(text)])
        self.assertIsNotNone(r, text)
        self.assertIn(expected, r['response'], text)
        return r

    def test_story_sums_and_follow_up(self):
        self.story('Tom has 3 apples. He gives 1 to Sue and buys 4 more. How many does he have now?', '**6 apples**')
        self.story('Mia had 12 cookies. She ate a quarter of them and then baked 6 more. How many cookies does she have?', '**15 cookies**')
        first = 'Lily has 10 stickers. She gives 3 to her friend, then finds 5 more. How many stickers does Lily have?'
        r = self.story(first, '**12 stickers**')
        r = reasoner.respond([U(first), A(r['response']), U('What if she loses 2 of them?')])
        self.assertIn('**10 stickers**', r['response'])

    def test_story_sums_refuse_what_they_cannot_know(self):
        for text in ('Sam has 5 marbles and Joe has 3 marbles. How many do they have together?',
                     'I have 8 tokens, receive some, then give away 6. How many tokens do I have?',
                     'Sam has 20 stickers, gives 9 to Ana. How many stickers does Ana have?',
                     'Mira has 4 boxes with 6 apples each. Mira eats 3 apples. How many apples does Mira have?'):
            self.assertIsNone(reasoner.story_reply([U(text)]), text)
        self.assertIsNone(reasoner.respond([U('Tom has 3 apples. He buys 4 more. How many does he have?')]))   # left to the quantity helpers first

    def test_sum_and_difference(self):
        self.check('A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much is the ball?', '**$0.05**')
        self.check('A shirt and a tie cost $60 together. The shirt costs $20 more than the tie. How much is the shirt?', '**$40.00**')

    def test_work_rates(self):
        self.check('If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?', '**5 minutes**')
        self.check('If 4 workers take 8 days to build 2 walls, how many days would 8 workers take to build 6 walls?', '**12 days**')

    def test_primes(self):
        self.check('Is 91 a prime number?', '91 = 7 × 13')
        self.check('Is 97 prime?', '**Yes**')
        self.check('What are the prime factors of 360?', '2 × 2 × 2 × 3 × 3 × 5')

    def test_chains(self):
        self.check("What's 15% of 240, and then add 20 to it?", '**56**')
        self.check('Take 50, then double it, then subtract 7.', '**93**')

    def test_rules_about_individuals(self):
        self.check('Every cat in the house is black. Felix is in the house. What colour is Felix?', '**Black.**')
        self.check('All birds can fly. Tweety is a bird. Can Tweety fly?', 'Tweety can fly')
        self.check('No reptiles are warm-blooded. Rex is a reptile. Is Rex warm-blooded?', '**No.**')

    def test_clock_follow_ups(self):
        r = reasoner.respond([U('x'), A('**11:45** (9:45 + 2 hours = 11:45).'), U('And if I get 25 extra minutes?')])
        self.assertIn('**12:10**', r['response'])
        r = reasoner.respond([U('x'), A('**21:50** (19:40 + 2 hours 10 minutes).'), U('What if it starts half an hour later?')])
        self.assertIn('**22:20**', r['response'])

    def test_numbers_from_other_desks_are_not_carried_on(self):
        self.assertIsNone(reasoner.respond([U('x'), A('**$365** in a month.'), U('And if I buy 2 more?')]))


class CityConvertTest(unittest.TestCase):
    def test_given_time_between_cities(self):
        # Tokyo (UTC+9) and Dubai (UTC+4) have no summer time, so the gap is always 5 hours
        r = about_me.respond([U('My call is at 3pm in Tokyo. What time is that in Dubai?')])
        self.assertIn('**10:00', r['response'])
        r = about_me.respond([U('At 11pm in Dubai, what time is it in Tokyo?')])
        self.assertIn('**04:00', r['response'])
        self.assertIn('the next day', r['response'])

    def test_current_time_still_answered(self):
        self.assertEqual(about_me.respond([U('What time is it in Tokyo?')])['route'], 'chat/about-city-time')


class SituationsTest(unittest.TestCase):
    def test_family_conflict(self):
        r = ask(situations, 'I keep arguing with my brother about small things.', 'How do I bring it up without it turning into another fight?')
        self.assertIn('Own your part', r['response'])

    def test_decline_wording_fits_the_occasion(self):
        self.assertIn('you both', situations.respond([U('How do I politely decline a wedding invitation?')])['response'])
        party = situations.respond([U("I can't go to my friend's birthday party. How do I tell her?")])['response']
        self.assertNotIn('you both', party)
        self.assertIn('birthday', party)
        r = ask(situations, 'How do I politely decline a wedding invitation?', 'Should I give a reason?')
        self.assertIn("don't have to give one", r['response'])

    def test_business_savings(self):
        r = ask(situations, "I'm thinking of quitting my job to start a business. Is that crazy?", 'I have about six months of savings.')
        self.assertTrue(r['response'].startswith('Six months'))

    def test_dinners_and_vegan(self):
        r = ask(situations, 'Can you help me plan a week of dinners on a budget?', "We're vegan.")
        self.assertIn('tofu', r['response'])
        self.assertNotIn('chicken', r['response'])

    def test_cooking_and_plant_follow_ups(self):
        r = situations.respond([U("What's a good way to start learning to cook?"), A('A few things...'), U('What should I make first?')])
        self.assertIn('tomato pasta', r['response'])
        r = situations.respond([U("My plant's leaves are turning yellow. What's wrong?"), A('Yellowing leaves...'), U('I water it every day.')])
        self.assertIn('very likely the cause', r['response'])

    def test_languages(self):
        r = ask(situations, 'Should I learn Spanish or French first?', 'I want to travel in South America.')
        self.assertIn('**Spanish**', r['response'])
        r = ask(situations, 'Should I learn German or Italian?', "My partner's family lives in Milan.")
        self.assertIn('**Italian**', r['response'])

    def test_unrelated_messages_are_left_alone(self):
        self.assertIsNone(situations.respond([U('What time is it in London?')]))
        self.assertIsNone(situations.respond([U('My brother is visiting next week.')]))      # told, not asked for ideas


class BlackHoleFollowUpTest(unittest.TestCase):
    def test_follow_ups(self):
        r = ask(concepts, 'Explain what a black hole is.', 'Could Earth fall into one?')
        self.assertTrue(r['response'].startswith('No.'))
        r = ask(concepts, 'Explain black holes simply.', "How do scientists see them if light can't escape?")
        self.assertIn('Event Horizon Telescope', r['response'])


if __name__ == '__main__':
    unittest.main()
