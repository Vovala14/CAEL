"""Regression tests from the ASTRA 6.2 blind test (2026-11-20). TEST-INFORMED: these conversations were seen in the blind
run, and their blind score (14/40 for the best setup, build 24117ba7…) stays the record for that build. Expected behaviour
follows the reviewer's published key column. These tests use the desks directly, without the web."""
import re
import unittest

from cael_unified import evidence, reasoner, swarm

CASES = {
    'B01': (["Log A: The courier was in the arcade. Report B: The courier was Nila.", "Correction to Report B: the courier was Pavi. Where does that put Pavi?"], r'arcade'),
    'B02': (["My badge is orange. My mug is white.", "What colour is it? I mean one of those two objects, but I haven't said which."], r'(?i)which one'),
    'B03': (["Log A: At noon the dial was blue. Log B: At noon the dial was yellow.", "Log B correction: at noon the dial was blue. Do the logs still disagree about the colour?"], r'^\*\*No\*\*.*blue'),
    'B04': (["How many sides does a hexagon have?"], r'\*\*6\.\*\*'),
    'B05': (["Good evening! Would you mind telling me which is smaller, minus seven or minus three?"], r'^\*\*minus seven\*\*'),
    'B06': (["Report A: The parcel is in the loft. Report B: The parcel is in the shed.", "For the parcel's location, trust Report B. Where is the parcel?"], r'^\*\*shed\*\*'),
    'B07': (["I personally saw the ferry at North Pier at 8am. Witness A: At 10am the ferry was at East Pier. Where was the ferry last confirmed by me?"], r'^\*\*North Pier\*\*'),
    'B08': (["Hi there, can you work out how many hours 150 minutes is, please?"], r'\*\*2\.5 hours\*\*'),
    'B09': (["Sensor A: The bin is empty. Report B: As for the bin, the smeared line might say someone refilled it afterward. Is it definitely still empty?"], r'Not for certain.*refilled'),
    'B12': (["Thanks for helping. Could you tell me how many millimetres are left to reach 1 metre if I already have 64 centimetres?"], r'\*\*360 millimetres\*\*'),
    'B13': (["Morning! If you have a second, what's three dozen minus five?"], r'^\*\*31\*\*'),
    'B15': (["Report A: The scarf is red. Report B: The scarf is blue. Report C: The scarf is blue. Ignore Report A. What colour do the remaining reports give?"], r'^\*\*blue\*\*'),
    'B16': (["Hey, can you tell me how many more seats a coach with 52 seats has than one with 37, please?"], r'^\*\*15 seats\*\*'),
    'B17': (["Witness A: The cloak was green. Witness B: The cloak was grey. What colour was the cloak?"], r'disagree.*green.*grey'),
    'B18': (["The spare keys are in the biscuit tin.", "Where are they?"], r'biscuit tin'),
    'B19': (["Witness 1: The pianist was in the studio. Witness 2: The pianist was Roni.", "Witness 2 retracts the identification. We don't know who the pianist was. Where does this leave Roni?"], r'unknown'),
    'B21': (["My lantern is purple.", "What colour is it?"], r'purple'),
    'B22': (["Sensor A: At 7am the freezer was open. Sensor B: At 9am the freezer was closed. Was the freezer open at 7am?"], r'\*\*Yes\*\*: open'),
    'B24': (["My radio was in the den.", "I moved it to the porch.", "Where is it now?"], r'porch'),
    'B25': (["All the marbles in this bag are glass. This blue marble is in the bag. What is it made of?"], r'^\*\*Glass\.\*\*'),
    'B26': (["Witness A: Mara said the fox was in the garden. Witness B: I heard Mara say that too. Did either witness say they personally saw the fox?"], r'^\*\*No\.\*\*'),
    'B28': (["Hi! One quick thing before I go. Yesterday was Monday in my story. What day is tomorrow in that story?"], r'^\*\*Wednesday\*\*'),
    'B30': (["Hey, please remind me, is 91 a prime number?"], r'^\*\*No\*\*.*7 × 13'),
    'B31': (["Witness A: I saw Jo in the lobby. Witness B: I saw Jordan in the yard. Jo and Jordan are different people. Where was Jo?"], r'^\*\*lobby\*\*'),
    'B32': (["A carton contains eight bottles.", "If they are shared equally by four people, how many bottles does each person get?"], r'^\*\*2 bottles\*\*'),
    'B35': (["Log A: The trolley was at the mill at 4pm. Log B: The trolley was at the dock at 6pm. Where exactly was it at 5pm, if no movements between sightings were recorded?"], r'Not known exactly'),
    'B36': (["Camera A: At 6am the cart was near the kiln. Log B: At 1pm the cart was near the gate. Where was the cart last seen, and according to whom?"], r'\*\*gate\*\* \(Log B\)'),
    'B37': (["Convert 3 kilograms to grams."], r'\*\*3,000 grams\*\*'),
    'B38': (["Witness A: I saw the kite on the roof. Report B: I copied Witness A's account about the kite. How many independent sightings of the kite are described?"], r'^\*\*One\.\*\*'),
    'B39': (["Thanks in advance. Could you put these in ascending order for me: 11, 2, 20, 5?"], r'^\*\*2, 5, 11, 20\*\*'),
}


def history(turns):
    out = []
    for i, t in enumerate(turns):
        out.append(dict(role='user', content=t))
        if i < len(turns) - 1:
            out.append(dict(role='assistant', content='ok'))
    return out


class BlindRegressionTest(unittest.TestCase):
    def test_desk_answers(self):
        for case, (turns, expected) in CASES.items():
            msgs = history(turns)
            r = swarm.chat_reply(msgs) or reasoner.respond(msgs)
            self.assertIsNotNone(r, case)
            self.assertRegex(r['response'], re.compile(expected, re.S), case)

    def test_evidence_check(self):
        draft = dict(route='chat/web-single', response='Some medical advice about joints.')
        r = evidence.check([dict(role='user', content='What is the serial number on the back of my kitchen clock?')], draft)
        self.assertEqual(r['route'], 'chat/evidence-missing')
        self.assertIn("can't see your kitchen clock", r['response'])
        r = evidence.check([dict(role='user', content='How many sides does a hexagon have?')],
                           dict(route='chat/web-checked', response='The common length of the sides equals the radius.'))
        self.assertEqual(r['route'], 'chat/evidence-missing')
        ok = dict(route='chat/web-exact', response='**Four.** Violins commonly have four strings.')
        self.assertIs(evidence.check([dict(role='user', content='How many strings does a violin have?')], ok), ok)
        ok = dict(route='chat/web-single', response='Paris is in the north of France.')
        self.assertIs(evidence.check([dict(role='user', content='Where is Paris?')], ok), ok)


if __name__ == '__main__':
    unittest.main()
