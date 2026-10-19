"""Authored text-only prompt quality, constraints and actual unified routing."""
import unittest
from unittest.mock import patch
from cael_unified.assistant import Assistant
from cael_unified.image_prompt import image_prompts, subject, clean_brief
from cael_unified.promptgen import PromptGenerator


class ImagePromptHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.engine = Assistant()

    def prompt(self, idea, seed=7):
        values, notes = image_prompts(idea, 1, seed)
        return values[0], notes

    def test_animal_portrait_is_not_a_person(self):
        for seed in range(10):
            text, notes = self.prompt('a watercolor portrait of a fox in a snowy forest', seed)
            self.assertEqual(notes['subject_kind'], 'animal')
            self.assertEqual(notes['style'], 'watercolor')
            self.assertNotRegex(text, r'skin|clothing|photographic|lens|fur.*person')
            self.assertIn('soft overcast light', text)

    def test_exclusion_people_never_becomes_subject(self):
        idea = 'a cobalt submarine beneath sea ice; no people; 16:9'
        text, notes = self.prompt(idea)
        self.assertTrue(text.startswith(idea))
        self.assertEqual(notes['subject'], 'submarine')
        self.assertEqual(notes['setting_context'], 'underwater')
        self.assertIn('pressure hull', text)
        self.assertNotRegex(text, r'street|portrait|skin|hair|road|clothing')

    def test_whale_keeps_water_habitat(self):
        for idea in ('a whale underwater', 'a whale'):
            for seed in range(10):
                text, notes = self.prompt(idea, seed)
                self.assertEqual(notes['subject_kind'], 'aquatic')
                self.assertEqual(notes['setting_context'], 'underwater')
                self.assertNotRegex(text, r'trail|garden|meadow|skin|fur|forest')

    def test_fish_is_not_silently_treated_as_whale(self):
        text, notes = self.prompt('a goldfish')
        self.assertEqual(notes['subject'], 'fish')
        self.assertNotIn('open ocean', text)

    def test_professions_and_indoor_night_light(self):
        for role, place in (('doctor', 'hospital'), ('engineer', 'workshop'), ('librarian', 'library')):
            for seed in range(10):
                text, notes = self.prompt(f'a {role} in a {place} at midnight', seed)
                self.assertEqual(notes['subject_kind'], 'person')
                self.assertEqual(notes['setting_context'], 'indoor')
                self.assertIn('interior practical lighting', text)
                self.assertNotRegex(text, r'moonlight|sunlight|daylight|sunrise|golden-hour')

    def test_vehicle_in_garage_at_night_stays_there(self):
        for seed in range(10):
            text, _ = self.prompt('a blue car in a garage at night', seed)
            self.assertIn('interior practical lighting', text)
            self.assertNotRegex(text, r'coastal road|city street|sunlight|daylight|moonlight')

    def test_cute_sleeping_dragon_does_not_become_menacing(self):
        for seed in range(10):
            text, notes = self.prompt('a cute sleeping dragon in a cave at night, pastel watercolor', seed)
            self.assertEqual(notes['style'], 'watercolor')
            self.assertEqual(notes['subject'], 'dragon')
            self.assertNotRegex(text, r'menacing|fire|embers|wings spread|photographic|lens|standing')
            self.assertIn('cave light', text)

    def test_astronaut_has_no_human_skin_default_or_road(self):
        text, notes = self.prompt('an astronaut on Mars')
        self.assertEqual(notes['subject_kind'], 'person')
        self.assertIn('spacesuit', text)
        self.assertEqual(notes['setting_context'], 'space')
        self.assertNotRegex(text, r'skin|street|road|forest|cafe')

    def test_wide_monochrome_focus_does_not_gain_bokeh_or_colour(self):
        idea = 'a wide landscape of mountains, everything in focus, black and white, 24mm lens'
        text, _ = self.prompt(idea)
        self.assertTrue(text.startswith(idea))
        self.assertNotRegex(text, r'shallow depth|bokeh|colour palette|vibrant|85mm|50mm|wide-angle lens')

    def test_vector_text_is_preserved_and_not_forbidden(self):
        idea = 'a logo with the text "MOON", flat vector, black and white'
        text, notes = self.prompt(idea)
        self.assertTrue(text.startswith(idea))
        self.assertEqual(notes['subject_kind'], 'graphic')
        self.assertEqual(notes['style'], 'vector')
        self.assertNotRegex(text, r'photographic|lens|anatomy|vibrant|storybook')
        self.assertNotRegex(notes['avoid'], r'lettering|logo|text')

    def test_main_subject_precedes_secondary_subject(self):
        self.assertEqual(subject('a dog with a woman in a park'), ('dog', 'animal'))
        self.assertEqual(subject('a woman with a dog in a park'), ('person', 'person'))
        self.assertEqual(subject('a snowman in a park'), ('snowman', 'object'))

    def test_active_chef_keeps_action_in_view(self):
        text, notes = self.prompt('a chef cooking in a kitchen')
        self.assertEqual(notes['subject'], 'chef')
        self.assertIn('action', text)
        self.assertNotRegex(text, r'head-and-shoulders|relaxed pose|steam rising')

    def test_explicit_background_and_negative_features_are_respected(self):
        for seed in range(10):
            text, _ = self.prompt('a hairless cat on a plain white background, no reflections', seed)
            added = text[len('a hairless cat on a plain white background, no reflections'):]
            self.assertNotRegex(added, r'coat|fur|hair|reflect|garden|forest|meadow')
            text, _ = self.prompt('a faceless woman on a plain background', seed)
            self.assertNotRegex(text[len('a faceless woman on a plain background'):], r'\b(?:face|gaze|eyes|expression)\b')

    def test_medium_specific_variants_remain_distinct_and_deterministic(self):
        for style in ('watercolor', 'pixel art', 'anime', '3D render', 'pencil sketch', 'flat vector'):
            brief = f'a {style} portrait of a fox on a plain background'
            values, notes = image_prompts(brief, 5, 81)
            self.assertEqual(len(set(values)), 5)
            self.assertEqual((values, notes), image_prompts(brief, 5, 81))
            self.assertTrue(all(value.startswith(brief) for value in values))
            self.assertTrue(all('photographic' not in value for value in values))

    def test_filler_only_asks_for_a_subject_and_counts_are_validated(self):
        self.assertEqual(PromptGenerator().respond('Write an image prompt for make an image of')['route'], 'chat/prompt-clarify')
        for count in (0, 6, True):
            with self.assertRaises(ValueError): image_prompts('a dog', count)

    def test_cleaning_preserves_ownership_punctuation_and_newlines(self):
        self.assertEqual(clean_brief('make an image of my dog; red collar'), 'my dog; red collar')
        idea = 'my dog; red collar\nno people; 16:9'
        self.assertTrue(self.prompt(idea)[0].startswith(idea))

    def test_unified_vynly_prompt_frame_never_generates_images_or_fetches(self):
        with patch.object(self.engine, 'image_reply', side_effect=AssertionError('Text only')), patch.object(self.engine._facts, 'respond', side_effect=AssertionError('No web')):
            result = self.engine.respond([dict(role='system', content='site: vynly.co'), dict(role='user', content='Write an image prompt for a doctor in a hospital at night')], mode='prompt', n=1, seed=19)
        self.assertEqual(result['route'], 'chat/prompt-image')
        self.assertIn('interior practical lighting', result['response'])
        self.assertTrue(result['response'].startswith('Image prompt:\n'))
        self.assertNotIn('avoid', result['response'].lower())
        self.assertIn('avoidance terms', result['details'])
        self.assertNotIn('paths', result)

    def test_screenshot_request_and_bare_idea_default_to_image_in_prompt_mode(self):
        for text in ('make prompt for red car', 'red car', 'improve this prompt: red car'):
            answer = self.engine.respond([dict(role='user', content=text)], mode='prompt', seed=19, n=1)
            self.assertEqual(answer['route'], 'chat/prompt-image')
            self.assertTrue(answer['prompts'][0].startswith('red car'))
            self.assertNotIn('Task brief', answer['response'])

    def test_explicit_non_image_prompt_types_stay_available(self):
        for kind in ('assistant', 'story'):
            answer = self.engine.respond([dict(role='user', content=f'Write a {kind} prompt for a lighthouse keeper')], mode='prompt', seed=19, n=1)
            self.assertEqual(answer['route'], 'chat/prompt-' + ('task' if kind == 'assistant' else kind))


if __name__ == '__main__': unittest.main()
