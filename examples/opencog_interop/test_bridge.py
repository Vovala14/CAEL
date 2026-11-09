import copy,importlib.util,json,os,sys,types,unittest
from unittest.mock import patch
from bridge import engines,export_episode,atom_graph,scheme,validate_graph,import_atomspace,concept,claim,FORMAT
from demos import episodes,EXPECTED,KNOWN_PARSER_FAILURES


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=os.environ.get('CAEL040_ROOT')
        if not root:raise unittest.SkipTest('Set CAEL040_ROOT to the external released CAEL 0.4.0 checkout.')
        cls.backend=engines(root)

    def test_actual_released_engine_episodes(self):
        for item,expected in zip(episodes(),EXPECTED):
            result=export_episode(item,self.backend)
            self.assertEqual([q['answer'] for q in result['queries']],KNOWN_PARSER_FAILURES.get(item['id'],expected))

    def test_uncertainty_keeps_possible_locations(self):
        result=export_episode(episodes()[2],self.backend)
        self.assertEqual(result['snapshots'][0]['cells'][0]['location_status'],'one_of')
        self.assertEqual(result['snapshots'][0]['cells'][0]['possible_locations'],['cellar','studio'])
        self.assertEqual(result['snapshots'][1]['cells'][0]['possible_locations'],['cellar'])

    def test_rejected_transaction_retains_state(self):
        result=export_episode(episodes()[3],self.backend)
        self.assertFalse(result['events'][-1]['accepted'])
        self.assertEqual(result['snapshots'][-1]['cells'],result['snapshots'][-2]['cells'])

    def test_owner_and_movement_evidence_propagate(self):
        result=export_episode(episodes()[1],self.backend)
        parcel=next(c for c in result['snapshots'][-1]['cells'] if c['entity']=='parcel')
        self.assertEqual(parcel['holder'],'lena');self.assertEqual(parcel['possible_locations'],['courtyard'])
        self.assertIn(5,parcel['support']);self.assertIn(4,parcel['support'])

    def test_query_evidence_maps_to_original_event_indices(self):
        item=copy.deepcopy(episodes()[0]);item['events'].insert(0,'this is not a supported event')
        result=export_episode(item,self.backend)
        self.assertFalse(result['events'][0]['accepted']);self.assertIn(6,result['queries'][1]['support'])

    def test_explicit_negative_unknown_conflict_stay_distinct(self):
        results=[export_episode(item,self.backend) for item in [episodes()[-1],episodes()[5],episodes()[6]]]
        self.assertEqual(results[0]['queries'][1]['status'],'false')
        self.assertEqual(results[1]['queries'][0]['status'],'unknown')
        self.assertEqual(results[2]['queries'][0]['status'],'conflicting')
        self.assertEqual({c['polarity'] for c in results[2]['logic_claims']},{'positive','negative'})

    def test_every_statement_is_episode_scoped(self):
        r=export_episode(episodes()[0],self.backend);g=atom_graph(r)
        for root in g['roots']:
            self.assertEqual(root['type'],'EvaluationLink')
            self.assertTrue(root['outgoing'][0]['name'].startswith('cael:'))
        plain=[x for x in g['roots'] if x['outgoing'][0]['name'] in ('cael:possible-location','cael:holder','cael:location-status')]
        for root in plain:self.assertEqual(root['outgoing'][1]['outgoing'][0]['name'],'cael:episode:'+r['input_sha256'])

    def test_same_label_different_inputs_get_different_scopes(self):
        a=episodes()[0];b=copy.deepcopy(a);b['events'].append('Mira went to the tower')
        ga=atom_graph(export_episode(a,self.backend));gb=atom_graph(export_episode(b,self.backend))
        self.assertNotEqual(ga['roots'][0]['outgoing'][1]['outgoing'][0],gb['roots'][0]['outgoing'][1]['outgoing'][0])

    def test_json_roundtrip_and_scheme_literal_escaping(self):
        value='odd "quote" \\ and\nname λ'
        g=dict(format=FORMAT,episode_id='literal',roots=[claim('data',concept('literal'),concept(value))])
        self.assertEqual(validate_graph(g),validate_graph(json.loads(json.dumps(g))))
        s=scheme(g);self.assertIn('\\"quote\\"',s);self.assertIn('\\\\ and\\nname λ',s)

    def test_executable_atom_types_are_rejected(self):
        for kind in ['ExecutionOutputLink','EvaluationLinkWithCode','SetValueLink','DefineLink','GroundedSchemaNode','MeetLink']:
            g=dict(format=FORMAT,episode_id='bad',roots=[dict(type=kind,name='anything')])
            with self.assertRaises(ValueError):validate_graph(g)

    def test_malformed_graphs_rejected_before_dependency_import(self):
        for root in [dict(type=[]),dict(type='ConceptNode',name='x',code='eval'),dict(type='NumberNode',name='-4'),dict(type='EvaluationLink',outgoing=[None,None])]:
            g=dict(format=FORMAT,episode_id='bad',roots=[root])
            with self.assertRaises(ValueError):import_atomspace(g)

    def test_external_input_unchanged_and_separate_episodes(self):
        item=episodes()[0];before=copy.deepcopy(item);first=export_episode(item,self.backend)
        self.assertEqual(before,item)
        empty=dict(id='new',events=[],logic='',queries=[dict(engine='world',text='Where is Mira?')])
        self.assertEqual(export_episode(empty,self.backend)['queries'][0]['answer'],'unknown')
        self.assertEqual(export_episode(item,self.backend),first)

    def test_low_level_binding_contract_with_test_double(self):
        calls=[]
        class Space:
            def add_node(self,kind,name):calls.append(('node',kind,name));return ('node',kind,name)
            def add_link(self,kind,outgoing):calls.append(('link',kind,outgoing));return ('link',kind,outgoing)
        module=types.ModuleType('opencog.atomspace');module.AtomSpace=Space
        module.types=types.SimpleNamespace(**{k:k for k in ['ConceptNode','PredicateNode','NumberNode','EvaluationLink','ListLink']})
        g=dict(format=FORMAT,episode_id='binding',roots=[claim('data',concept('binding'),concept('literal'))])
        with patch.dict(sys.modules,{'opencog':types.ModuleType('opencog'),'opencog.atomspace':module}):
            space,roots=import_atomspace(g)
        self.assertEqual(len(roots),1);self.assertEqual(calls[-1][1],'EvaluationLink')

    @unittest.skipUnless(importlib.util.find_spec('opencog') is not None,'Real AtomSpace bindings are unavailable; API double is not integration proof.')
    def test_actual_atomspace_import(self):
        graph=atom_graph(export_episode(episodes()[0],self.backend));space,roots=import_atomspace(graph)
        self.assertEqual(len(roots),len(graph['roots']));self.assertTrue(all(r is not None for r in roots))


if __name__=='__main__':unittest.main()
