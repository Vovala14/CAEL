"""Tests of observable state isolation, local updates and interface rejection."""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from cael import CAEL, Unsupported

ROOT=Path(__file__).resolve().parents[1]

class CAELTests(unittest.TestCase):
    def setUp(self):
        self.m=CAEL()
        self.f=dict(a=0,b=1,i=0,p=1,s=0,intent='find')

    def test_model_identity(self):
        manifest=json.loads((ROOT/'models/cael-story-0.1/manifest.json').read_text())
        self.assertEqual(hashlib.sha256(self.m.path.read_bytes()).hexdigest(),manifest['model_sha256'])
        self.assertEqual(self.m.model['family'],'CAEL')
        self.assertEqual(self.m.model['neural_parameters'],0)

    def test_local_synchronous_memory_packet(self):
        rows=self.m.initial_world()
        before=rows.copy()
        carriers=np.full((len(rows),5),-1,np.int32)
        carriers[2]=[self.m.eid['INTRO'],*self.m.parameters(self.f)[:4]]
        out,following=self.m.memory_step(rows,carriers)
        far=rows.copy();far[-1,3]=999
        other,other_carriers=self.m.memory_step(far,carriers)
        self.assertTrue(np.array_equal(rows,before))
        self.assertTrue(np.array_equal(out[:3],other[:3]))
        self.assertTrue(np.array_equal(following,other_carriers))
        self.assertEqual(following[3,0],carriers[2,0])
        self.assertEqual(following[2,0],-1)

    def test_plan_translation(self):
        grid=np.zeros((16,10),np.int32)
        grid[2,:4]=[1,self.m.iid['find'],-2,0]
        grid[2,4:]=self.m.parameters(self.f)
        shifted=np.zeros_like(grid);shifted[5]=grid[2]
        a,ea=self.m.plan_step(grid,7);b,eb=self.m.plan_step(shifted,7)
        self.assertEqual(ea[2],eb[5])
        self.assertTrue(np.array_equal(a[3],b[6]))

    def test_grammar_translation(self):
        grid=np.zeros((128,9),np.int32)
        grid[2,:2]=[1,self.m.starts[self.m.eid['INTRO']]]
        grid[2,2:8]=self.m.parameters(self.f)
        shifted=np.zeros_like(grid);shifted[5]=grid[2]
        a,ea=self.m.grammar_step(grid,7);b,eb=self.m.grammar_step(shifted,7)
        self.assertEqual(ea[2],eb[5])
        self.assertTrue(np.array_equal(a[3],b[6]))

    def test_followup_and_fork(self):
        self.m.story('Tell me a story about a dog helping a bird find a lost ball.')
        self.assertEqual(self.m.ask('Who found the ball?')['response'],'The dog found the ball.')
        self.assertEqual(self.m.ask('Who has the ball?')['response'],'The bird has the ball.')
        fork=self.m.fork();before=self.m.world.copy()
        fork.apply(fork.eid['HAVE'],self.f)
        self.assertTrue(np.array_equal(before,self.m.world))
        self.assertFalse(np.shares_memory(fork.world,self.m.world))

    def test_explicit_cumulative_state(self):
        first=dict(a=0,b=1,i=0,p=1,s=0,intent='share')
        second=dict(a=2,b=3,i=1,p=2,s=0,intent='find')
        self.m.story_frame(first)
        owner=int(self.m.world[self.m.world[:,0]==101][0,2])
        self.m.story_frame(second,reset=False)
        self.assertEqual(int(self.m.world[self.m.world[:,0]==101][0,2]),owner)
        self.assertEqual(self.m.ask('Who has the ball?')['value'],2)
        self.m.story_frame(second)
        with self.assertRaises(Unsupported):
            self.m.ask('Who has the ball?')

    def test_unsupported_prompts(self):
        for prompt in ['Explain why ice floats on water.', 'Write a story about an astronaut repairing a spaceship on Mars.', 'Tell a story about a cat building a rocket.']:
            with self.subTest(prompt=prompt),self.assertRaises(Unsupported):
                self.m.story(prompt)

    def test_unsupported_question_semantics(self):
        self.m.story('Tell a story about a cat finding a ball in a park.')
        for question in ["Who does not have the ball?",'Who has the ball before the story?', 'Where is the cat tomorrow?', 'Who found the ball and hat?']:
            with self.subTest(question=question),self.assertRaises(Unsupported):
                self.m.ask(question)

    def test_mass_noun_format(self):
        output=self.m.story('Tell a story about a fox sharing bread with a rabbit.')['response']
        self.assertIn('some bread',output)
        self.assertNotIn('a bread',output)

    def test_seeded_replay(self):
        prompt='Tell a story about a mouse finding cheese in a bakery.'
        a=self.m.story(prompt,123)
        b=self.m.story(prompt,123)
        self.assertEqual(a,b)

    def test_runtime_has_no_teacher_import(self):
        import ast
        tree=ast.parse((ROOT/'cael.py').read_text())
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            elif isinstance(node,ast.ImportFrom):imports.append(node.module)
        self.assertFalse(set(imports)&{'curriculum','torch','transformers','tensorflow'})

if __name__=='__main__':
    unittest.main()
