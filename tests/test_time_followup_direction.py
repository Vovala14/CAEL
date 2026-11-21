"""A follow-up that moves the last clock time takes its direction from the words next to the amount, not from any
direction word anywhere in the message. Regression for a 0.4.4 report: "delayed 20 minutes, not earlier ..." gave 10:05."""
import unittest

from cael_unified import reasoner

FIRST = 'My train departs at 09:40 and the trip takes 45 minutes. When do I arrive?'
SAID = '**10:25** (9:40 + 45 minutes = 10:25).'


def ask(text):
    r = reasoner.follow([dict(role='user', content=FIRST), dict(role='assistant', content=SAID), dict(role='user', content=text)])
    return r and r['response']


class TimeFollowupDirection(unittest.TestCase):
    def test_delay_adds(self):
        for text in ('The train is delayed by 20 minutes. When do I arrive now?',
                     'If the train leaves 20 minutes late, what time do I arrive?',
                     'It is delayed 20 minutes, not earlier as I first thought. When do I arrive?',
                     'The train is delayed by 20 minutes. Do I arrive later or sooner?',
                     'What if it runs 20 minutes behind, would I arrive sooner than 11?',
                     # fix1 report: "earlier" describes the original departure, "delayed" is the change
                     'The train is delayed 20 minutes from the earlier 09:40. When do I arrive?',
                     'It got delayed 20 minutes from the earlier 09:40 departure. When do I arrive now?',
                     'My earlier train is delayed by 20 minutes. When do I arrive?',
                     'Delayed 20 minutes from the earlier time, so when do I arrive?'):
            with self.subTest(text=text):
                self.assertTrue((ask(text) or '').startswith('**10:45**'), ask(text))

    def test_earlier_subtracts(self):
        for text in ('What if it arrives 20 minutes earlier?',
                     'What if the trip takes 20 minutes less, not more?',
                     'What if the later train gets in 20 minutes earlier?'):
            with self.subTest(text=text):
                self.assertTrue((ask(text) or '').startswith('**10:05**'), ask(text))

    def test_plain_what_if_still_adds(self):
        self.assertTrue((ask('What if it takes another 20 minutes?') or '').startswith('**10:45**'))

    def test_both_ways_asks(self):
        got = ask('What if 20 minutes later or earlier?') or ''
        self.assertIn('10:45', got)
        self.assertIn('10:05', got)
        self.assertTrue(got.startswith('Do you mean'), got)


if __name__ == '__main__':
    unittest.main()
