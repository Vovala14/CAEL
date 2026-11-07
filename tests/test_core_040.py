"""Independent invariants/oracles for core engines, not benchmark examples."""
import copy
import itertools
import json
import random
import unittest
from cael_unified.reasoning import Reasoner
from cael_unified.reasoning_logic import LogicCA, Unparsed
from cael_unified.reasoning_world import WorldCA
from cael_unified.reasoning_order import holds, ordering
from cael_unified.constraint_automaton import enumerate_orders, SearchLimit
from cael_unified.local_automata import learn_transition, OutsideDomain, reply


def label(n):
    out=''
    while True:
        out=chr(97+n%26)+out; n=n//26-1
        if n<0:return 'trait'+out


class Core040Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=Reasoner().model

    def test_long_graph_chain_and_full_causal_support(self):
        for hops in (1,25,64,110):
            context='Ivara is '+label(0)+'. '+' '.join('Every '+label(i)+' is '+label(i+1)+'.' for i in range(hops))
            engine=LogicCA(self.model); result=engine.query(context,'Is Ivara '+label(hops)+'?')
            self.assertEqual(result['answer'],'true');self.assertEqual(result['depth'],hops)
            self.assertEqual(result['support'],list(range(1,hops+2)))
            self.assertLessEqual(engine.last_stats['rule_transitions'],2*hops+1)

    def test_minimum_proof_and_duplicate_fact_order(self):
        result=LogicCA(self.model).query('Kira is warm. Kira is warm. Every warm is safe. Kira is safe.', 'Is Kira safe?')
        self.assertEqual(result['support'],[4]);self.assertEqual(result['depth'],0)
        result=LogicCA(self.model).query('Kira is warm. Kira is warm. Every warm is safe.', 'Is Kira safe?')
        self.assertEqual(result['support'],[1,3])

    def test_cycles_do_not_manufacture_evidence(self):
        result=LogicCA(self.model).query('Kira is warm. Every blue is green. Every green is blue.', 'Is Kira blue?')
        self.assertEqual(result['answer'],'unknown')

    def test_long_live_dependencies_and_historical_copies(self):
        from cael_unified.event_memory import Memory, key, resolve
        memory=Memory();memory.apply('put',dict(E='anchor',A='value',V='7'),1,'authored')
        for i in range(180):
            memory.apply('live',dict(E='node'+str(i),A='value',S='anchor' if i==0 else 'node'+str(i-1)),i+2,'authored')
        memory.apply('copy',dict(E='snapshot',A='value',S='node179'),183,'authored')
        memory.apply('put',dict(E='anchor',A='value',V='11'),184,'authored')
        self.assertEqual(memory.get(key('node179','value')),'11')
        self.assertEqual(memory.get(key('snapshot','value')),'7')
        self.assertEqual(memory.get(key('anchor','value'),'previous'),'7')
        with self.assertRaises(ValueError):resolve({'a':{'ref':'b'},'b':{'ref':'a'}},'a')

    def test_ownership_validation_is_atomic(self):
        world=WorldCA(self.model)
        for i,event in enumerate([('move','liora','hall'),('move','tavin','hall'),('take','liora','coin')],1):world.apply(event,i)
        prior=copy.deepcopy((world.cells,world.gifts,world.carried))
        for event in [('take','tavin','coin'),('give','tavin','coin','nela'),('drop','tavin','coin')]:
            with self.assertRaises(Unparsed):world.apply(event,4)
            self.assertEqual((world.cells,world.gifts,world.carried),prior)

    def test_location_refinement_of_owned_objects(self):
        world=WorldCA(self.model)
        world.apply(('uncertain','liora','hall','loft'),1)
        world.apply(('take','liora','coin'),2)
        world.apply(('exclude','liora','hall'),3)
        self.assertEqual(world.cells['liora'].locations,{'loft'})
        self.assertEqual(world.cells['coin'].locations,{'loft'})
        self.assertTrue({1,2,3}<=world.cells['coin'].support)

    def test_sparse_world_schedule_and_owner_invariant(self):
        world=WorldCA(self.model)
        for i in range(500):world.apply(('move','person'+str(i),'hall'),i)
        world.apply(('take','person0','coin'),501)
        before=world.transition_visits
        world.apply(('move','person0','loft'),502)
        self.assertEqual(world.transition_visits-before,2)
        world.apply(('drop','person0','coin'),503)
        world.apply(('move','person0','hall'),504)
        self.assertEqual(world.cells['coin'].locations,{'loft'})
        self.assertNotIn('coin',world.carried['person0'])

    def test_cross_room_transfer_is_rejected_before_gift_record(self):
        world=WorldCA(self.model)
        for i,e in enumerate([('move','liora','hall'),('move','tavin','loft'),('take','liora','coin')],1):world.apply(e,i)
        with self.assertRaises(Unparsed):world.apply(('give','liora','coin','tavin'),4)
        self.assertEqual(world.gifts,[]);self.assertEqual(world.cells['coin'].owner,'liora')

    def test_constraint_solver_matches_independent_permutation_oracle(self):
        rng=random.Random(840173)
        for _ in range(70):
            names=tuple('abcde'[:rng.randint(3,5)])
            clues=[]
            for _ in range(rng.randint(0,8)):
                op=rng.choice(['before','not_before','adjacent','not_adjacent','immediately_before','at','not_at','between','not_between'])
                a,b,c=rng.sample(names,3)
                clues.append((op,a,rng.randrange(len(names))) if op.endswith('at') else (op,a,b,c) if op.endswith('between') else (op,a,b))
            expected=tuple(p for p in itertools.permutations(names) if all(holds(c,{n:i for i,n in enumerate(p)}) for c in clues))
            got,stats=enumerate_orders(names,clues,holds)
            self.assertEqual(got,expected);self.assertTrue(stats['complete'])

    def test_larger_constraint_problem_and_ambiguity(self):
        names=['name'+label(i) for i in range(12)]
        context='Items: '+', '.join(names)+'. '+' '.join(a+' is immediately before '+b+'.' for a,b in zip(names,names[1:]))
        result=ordering(context,'Who is twelfth?')
        self.assertEqual(result['answer'],names[-1]);self.assertEqual(result['valid_orders'],1)
        self.assertEqual(ordering('Items: A, B, C. A is before B.','Who is last?')['answer'],'unknown')

    def test_search_limit_is_not_a_partial_answer(self):
        with self.assertRaises(SearchLimit):enumerate_orders(tuple('abcdefghij'),(),holds,max_nodes=20)

    def test_count_retrieval_cache_respects_k_and_tie_ids(self):
        import numpy as np
        from scipy import sparse
        from collections import OrderedDict
        from cael_unified.count_language import CountLanguage
        engine=CountLanguage.__new__(CountLanguage);engine.np=np;engine.cache=OrderedDict()
        engine.contexts=sparse.csr_matrix([[1,0],[1,0],[0,1],[1,0]])
        engine.query_features=lambda context:sparse.csr_matrix([[1.,0.]])
        self.assertEqual(engine.neighbours('query',1)[0].tolist(),[0])
        self.assertEqual(engine.neighbours('query',3)[0].tolist(),[0,1,3])
        self.assertEqual(engine.neighbours('query',1)[0].tolist(),[0])
        with self.assertRaises(ValueError):engine.neighbours('query',True)

    def test_local_transition_induction_on_fresh_rows(self):
        rng=random.Random(570143)
        rules=[(2,lambda a,i:(a[(i-1)%len(a)]+a[i]+a[(i+1)%len(a)])%2),
               (4,lambda a,i:(a[(i-1)%len(a)]+a[(i+1)%len(a)])%4),
               (3,lambda a,i:a[(i-1)%len(a)])]
        for colors,fn in rules:
            examples=[]
            for _ in range(12):
                a=[rng.randrange(colors) for _ in range(37)]
                examples.append({'input':a,'output':[fn(a,i) for i in range(len(a))]})
            q=[rng.randrange(colors) for _ in range(43)]
            result=learn_transition(examples,q)
            self.assertEqual(result['prediction'],[fn(q,i) for i in range(len(q))])
            self.assertFalse(result['neural']);self.assertFalse(result['persistent_learning'])

    def test_transition_boundary_and_invalid_metadata(self):
        for task in [dict(examples=[{'input':[0],'output':[0]},{'input':[0],'output':[1]}],query=[0]),
                     dict(examples=[{'input':[0],'output':[0]}]*2,query=[True]),
                     dict(examples=[{'input':[0],'output':[0]}]*2,query=[0],solution=[0])]:
            result=reply('Infer discrete transition: '+json.dumps(task))
            self.assertEqual(result['route'],'chat/automaton-clarify')

    def test_unified_transition_route_preserves_api_limits(self):
        from cael_unified import Assistant
        from tempfile import TemporaryDirectory
        text='Infer discrete transition: '+json.dumps(dict(examples=[dict(input=[0,1],output=[1,0])]*2,query=[1,0]))
        with TemporaryDirectory() as output:
            assistant=Assistant(output_root=output)
            self.assertEqual(assistant.respond([dict(role='user',content=text)],mode='chat',seed=7)['route'],'chat/automaton-induction')
            for n in (0,True,9):
                with self.assertRaises(ValueError):assistant.respond([dict(role='user',content=text)],mode='chat',n=n)
            with self.assertRaises(ValueError):assistant.respond([dict(role='user',content=text)],mode='chat',seed=-1)


if __name__=='__main__':unittest.main()
