"""Synthetic prompt/story checks; never load images or private conversations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cael import CAEL, Unsupported
from cael_unified.assistant import Assistant, route_request
from cael_unified.promptgen import PromptGenerator, parse

ROOT=Path(__file__).resolve().parents[1]
STORY=ROOT/'models/cael-story-0.3.7-r2/model.json'
PROMPT=ROOT/'models/cael-prompts-0.3.7-r2/model.json'


class PromptTests(unittest.TestCase):
    def test_all_three_types_and_brief_preservation(self):
        model=PromptGenerator(PROMPT)
        for kind,text,brief in [
            ('image','Write an image prompt for a cobalt submarine beneath sea ice; no people; 16:9','a cobalt submarine beneath sea ice; no people; 16:9'),
            ('story','Write a story prompt about a librarian who finds a city inside a book','a librarian who finds a city inside a book'),
            ('task','Write an assistant prompt for reviewing Python code; return exactly three bullets','reviewing Python code; return exactly three bullets')]:
            result=model.respond(text,seed=7)
            self.assertEqual(result['route'],'chat/prompt-'+kind)
            self.assertIn(brief,result['response'])
            self.assertNotIn('a woman',result['response'])
            self.assertNotIn('paths',result)

    def test_prompt_constraints_and_code_newlines_survive_formatting(self):
        brief='Keep this code exactly:\n  x = 1 , 2\n  print(x)\nUse JSON only.'
        result=PromptGenerator(PROMPT).respond('Improve this prompt: '+brief,seed=11)
        self.assertIn(brief,result['response'])

    def test_five_variants_are_distinct_and_reproducible(self):
        model=PromptGenerator(PROMPT)
        request='Generate five image prompts for an origami lighthouse on a cliff'
        first=model.respond(request,seed=71)
        self.assertEqual(len(first['prompts']),5)
        self.assertEqual(len(set(first['prompts'])),5)
        self.assertEqual(first,model.respond(request,seed=71))

    def test_prompt_type_is_not_changed_by_the_subject(self):
        self.assertEqual(parse('Write an assistant prompt for a story editor')['kind'],'task')
        self.assertEqual(parse('Write a story prompt about a photo')['kind'],'story')

    def test_empty_and_excessive_requests_are_explicit(self):
        self.assertEqual(PromptGenerator(PROMPT).respond('Write a prompt')['route'],'chat/prompt-clarify')
        with self.assertRaises(ValueError):parse('Write 9 prompts for a task')
        with self.assertRaises(ValueError):parse('Write a prompt for '+'x'*8001)

    def test_prompt_requests_do_not_enter_image_or_fact_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            model=Assistant(output_root=folder)
            with patch.object(model,'image_reply',side_effect=AssertionError('No image generation')), \
                 patch.object(model._facts,'respond',side_effect=AssertionError('No web lookup')):
                for mode in ('auto','chat','prompt'):
                    result=model.respond([dict(role='user',content='Write an image prompt for a moth on moss')],mode=mode,seed=12)
                    self.assertEqual(result['route'],'chat/prompt-image')

    def test_common_request_frames_and_counts(self):
        for request in ('Can you please write an image prompt for a moth?',
                        'Help me write an image prompt for a moth?',
                        'Make up an image prompt for a moth?'):
            self.assertEqual(route_request(request),'prompt')
            self.assertEqual(parse(request)['kind'],'image')
        request='Generate 3 different image prompts for a moth on moss'
        result=PromptGenerator(PROMPT).respond(request,seed=9)
        self.assertEqual(len(result['prompts']),3)
        self.assertEqual(PromptGenerator(PROMPT).respond('Write 99 prompts for a moth')['route'],'chat/prompt-clarify')

    def test_routing_preserves_code_and_normal_image_requests(self):
        for text in ('Write a prompt generator in Python','Write a Python story generator','What is a story prompt?'):
            self.assertEqual(route_request(text),'chat')
        self.assertEqual(route_request('Make an image of a car'),'image')
        self.assertEqual(route_request('Tell a story about a dragon finding a key'),'story')

    def test_code_about_a_generator_does_not_become_a_story(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=Assistant(output_root=folder)
            with patch.object(engine,'story_reply',side_effect=AssertionError('This is a code request')), \
                 patch.object(engine._facts,'respond',return_value={'route':'fixture','response':'code request'}):
                result=engine.respond([dict(role='user',content='Write a Python story generator')])
                self.assertEqual(result['response'],'code request')


class CreativeStoryTests(unittest.TestCase):
    def test_expanded_vocabulary_is_supported(self):
        model=CAEL(STORY)
        result=model.story('Tell a story about an astronaut finding a compass in a space station.',seed=5)
        for word in ('astronaut','compass','space station'):
            self.assertIn(word,result['response'])
        self.assertEqual(model.ask('Who found the compass?')['response'],'The astronaut found the compass.')
        self.assertEqual(model.ask('Where is the compass?')['response'],'The compass is aboard the space station.')

    def test_observed_object_location_is_learned_without_inventing_ownership(self):
        model=CAEL(STORY)
        model.story('Tell a story about a detective visiting a museum with a key.',seed=3)
        self.assertEqual(model.ask('Where is the key?')['response'],'The key is in the museum.')
        with self.assertRaises(Unsupported):model.ask('Who has the key?')

    def test_constraints_are_not_silently_discarded(self):
        model=CAEL(STORY)
        for text in ('Tell a story about a cat finding a ball and a hat.',
                     'Tell a story about a dog finding a ball in a park and a forest.',
                     'Tell a story about a dog finding a ball and sharing it with a cat.'):
            with self.assertRaises(Unsupported,msg=text):model.story(text)

    def test_generating_a_prompt_does_not_create_story_state(self):
        with tempfile.TemporaryDirectory() as folder:
            model=Assistant(output_root=folder)
            history=[dict(role='user',content='Write a story prompt about a dog sharing a ball with a bird in the park.')]
            self.assertEqual(model.respond(history,seed=8)['route'],'chat/prompt-story')
            history += [dict(role='assistant',content='Prompt text'),dict(role='user',content='Who received the ball?')]
            with patch.object(model._facts,'respond',return_value={'route':'fixture','response':'No supported story'}):
                self.assertNotEqual(model.respond(history,seed=8)['route'],'chat/story')

    def test_unanswered_factual_questions_do_not_fall_back_to_small_talk(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=Assistant(output_root=folder)
            with patch.object(engine._facts,'respond',return_value=None):
                for text in ('When was Metallica formed?','https://example.com/'):
                    self.assertEqual(engine.respond([dict(role='user',content=text)],seed=1)['route'],'chat/cannot-answer',text)
                self.assertNotEqual(engine.respond([dict(role='user',content='How are you?')],seed=1)['route'],'chat/cannot-answer')

    def test_explicit_prompt_mode_does_not_create_a_story_from_its_brief(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=Assistant(output_root=folder)
            history=[dict(role='user',content='Tell a story about a dog sharing a ball with a bird in the park.')]
            response=engine.respond(history,mode='prompt',seed=9)
            history += [dict(role='assistant',content=response['response']),dict(role='user',content='Who received the ball?')]
            with patch.object(engine._facts,'respond',return_value={'route':'fixture','response':'No story'}):
                self.assertNotEqual(engine.respond(history)['route'],'chat/story')

    def test_story_mode_brief_can_be_followed_up_in_auto_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            engine=Assistant(output_root=folder)
            history=[dict(role='user',content='a dog sharing a ball with a bird in the park.')]
            result=engine.respond(history,mode='story',seed=2)
            history += [dict(role='assistant',content=result['response']),dict(role='user',content='Who received the ball?')]
            self.assertEqual(engine.respond(history)['response'],'The bird received the ball.')


if __name__=='__main__':unittest.main()
