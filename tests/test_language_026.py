"""Novel names, information access, helper limits and story conversation state."""
import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from cael import CAEL, Unsupported
from cael_unified.helper import calculate
from cael_unified.reasoning import Reasoner
from cael_unified.reasoning_logic import Unparsed
from cael_unified.social_reasoning import SocialCA
from cael_unified.assistant import Assistant

BASE = ('Zora and Neri entered the studio. Zora put the compass in the cabinet. '
        'Zora left the studio. Neri moved the compass to the basket.')


class SocialTests(unittest.TestCase):
    def test_absent_observer_retains_false_belief(self):
        engine = SocialCA()
        self.assertEqual(engine.query(BASE, 'Where will Zora look for the compass?')['answer'], 'cabinet')
        self.assertEqual(engine.query(BASE, 'Where will Neri look for the compass?')['answer'], 'basket')
        self.assertEqual(engine.query(BASE, 'Where is the compass really?')['answer'], 'basket')

    def test_present_observer_updates(self):
        context = BASE.replace('Zora left the studio. ', '')
        self.assertEqual(SocialCA().query(context, 'Where does Zora think the compass is?')['answer'], 'basket')

    def test_return_does_not_reveal_hidden_location(self):
        result = SocialCA().query(BASE+' Zora returned to the studio.', 'Where will Zora look for the compass?')
        self.assertEqual(result['answer'], 'cabinet')

    def test_seeing_corrects_belief(self):
        context = BASE+' Zora returned to the studio. Zora saw the compass in the basket.'
        self.assertEqual(SocialCA().query(context, 'Where will Zora look for the compass?')['answer'], 'basket')

    def test_report_can_be_false_without_changing_reality(self):
        context = BASE+' Neri told Zora that the compass is in the suitcase.'
        self.assertEqual(SocialCA().query(context, 'Where will Zora look for the compass?')['answer'], 'suitcase')
        self.assertEqual(SocialCA().query(context, 'Where is the compass really?')['answer'], 'basket')

    def test_unmentioned_person_is_unknown(self):
        self.assertEqual(SocialCA().query(BASE, 'Does Vex know where the compass is?')['answer'], 'unknown')

    def test_mistaken_belief_does_not_count_as_knowledge(self):
        self.assertEqual(SocialCA().query(BASE, 'Does Zora know where the compass is?')['answer'], 'no')
        self.assertEqual(SocialCA().query(BASE, 'Does Neri know where the compass is?')['answer'], 'yes')

    def test_no_partial_parse_of_unsupported_event(self):
        with self.assertRaises(Unparsed):
            SocialCA().query(BASE+' Neri secretly swapped the compass with a painted copy.', 'Where will Zora look for the compass?')

    def test_multi_room_scenario_abstains(self):
        with self.assertRaises(Unparsed):
            SocialCA().query(BASE+' Zora entered the attic.', 'Where will Zora look for the compass?')

    def test_absent_actor_cannot_act_without_returning(self):
        with self.assertRaises(Unparsed):
            SocialCA().query(BASE+' Zora put the compass in the suitcase.', 'Where will Zora look for the compass?')

    def test_new_query_does_not_reuse_other_visitors_beliefs(self):
        engine = SocialCA()
        engine.query(BASE, 'Where will Zora look for the compass?')
        self.assertEqual(engine.query('The compass is in the basket.', 'Where will Zora look for the compass?')['answer'], 'unknown')

    def test_reasoner_routes_beliefs_offline(self):
        result = Reasoner().respond('Given: '+BASE+' Where will Zora look for the compass?')
        self.assertEqual(result['route'], 'chat/reasoning-belief')
        self.assertTrue(result['response'].startswith('Zora will look for the compass in the cabinet.'))
        self.assertFalse(result['reasoning']['internet_used'])

    def test_continuation_choice_is_option_order_invariant(self):
        context = BASE+' Zora will look for the compass in'
        self.assertEqual(SocialCA().choose(context, [' the basket.', ' the cabinet.', ' nowhere.', ' the studio.']), 1)
        self.assertEqual(SocialCA().choose(context, [' the cabinet.', ' nowhere.', ' the studio.', ' the basket.']), 0)


class HelperTests(unittest.TestCase):
    def test_exact_percentages_and_changes(self):
        for text, expected in [('What is 15% of 240?', '36'), ('Increase 80 by 25%', '100'), ('Decrease 80 by 25%', '60')]:
            self.assertTrue(calculate(text)['response'].endswith('= '+expected))

    def test_words_and_fractions(self):
        self.assertEqual(calculate('Calculate 7 divided by 3')['response'], '7 / 3 = 7/3')
        self.assertTrue(calculate('12 plus 5 times 2')['response'].endswith('= 22'))

    def test_unit_conversions(self):
        for text, expected in [('Convert 2.5 km to meters', '2500'), ('90 minutes in hours', '3/2'), ('12 inches to feet', '1'), ('500 grams to kg', '1/2')]:
            self.assertIn('= '+expected+' ', calculate(text)['response'])

    def test_unsupported_units_and_dimension_mismatch(self):
        for text in ('2 kg to meters', '10 USD to EUR', '20 celsius to fahrenheit', '5 mercury to liters'):
            self.assertIsNone(calculate(text))

    def test_arithmetic_bounds_remain(self):
        for text in ('1/0', '2**100000', '__import__("os")', '1e999999'):
            self.assertIsNone(calculate(text))


class StoryTests(unittest.TestCase):
    def test_story_override_checksum_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'research').mkdir()
            bad = root/'bad-model.json'
            bad.write_text('{}')
            (root/'research/active_models.json').write_text(json.dumps(dict(story=dict(path=str(bad),sha256='wrong'))))
            engine = Assistant(output_root=root/'outputs')
            with patch('cael_unified.assistant.ROOT',root), self.assertRaisesRegex(ValueError,'checksum changed'):
                engine.respond([dict(role='user',content='Tell a story about a cat finding a ball.')])

    def test_object_location_and_recipient(self):
        engine = CAEL()
        engine.story('Tell a story about a dog sharing a ball with a bird in the park.')
        self.assertEqual(engine.ask('Where is the ball?')['response'], 'The ball is in the park.')
        self.assertEqual(engine.ask('Who received the ball?')['response'], 'The bird received the ball.')
        self.assertEqual(engine.ask('What does the bird have?')['response'], 'The bird has the ball.')

    def test_no_receipt_in_finding_story(self):
        engine = CAEL()
        engine.story('Tell a story about a dog finding a ball in the park.')
        with self.assertRaises(Unsupported):
            engine.ask('Who received the ball?')

    def test_bedtime_tale_and_followups_preserve_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Assistant(output_root=folder)
            first = 'Tell a bedtime tale about a dog sharing a ball with a bird in the park.'
            messages = [dict(role='user',content=first)]
            with patch.object(engine._facts, 'respond', side_effect=AssertionError('Unexpected lookup')):
                result = engine.respond(messages, seed=12)
                self.assertEqual(result['route'], 'chat/story')
                messages += [dict(role='assistant',content=result['response']),dict(role='user',content='Who received the ball?')]
                self.assertEqual(engine.respond(messages,seed=99)['response'], 'The bird received the ball.')


if __name__ == '__main__':
    unittest.main()
