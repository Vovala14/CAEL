"""Required real-binding integration; mocks/skips cannot produce success here."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import traceback
import unittest

from bridge import (NODES, LINKS, atom_graph, engines, export_episode,
                    import_atomspace, validate_graph)
from demos import episodes, EXPECTED


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def native_atom(atom, nameserver):
    kind = nameserver(atom.type)
    if kind in NODES:
        return dict(type=kind, name=atom.name)
    if kind not in LINKS:
        raise AssertionError('Unexpected stored type: '+kind)
    return dict(type=kind, outgoing=[native_atom(child, nameserver) for child in atom.out])


def normalize_alias(atom, alias):
    if 'name' in atom:
        return atom
    return dict(type='EdgeLink' if alias and atom['type']=='EvaluationLink' else atom['type'],
                outgoing=[normalize_alias(child, alias) for child in atom['outgoing']])


def count_unique(graph, alias):
    found = set()
    def visit(atom):
        found.add(canonical(normalize_alias(atom, alias)))
        for child in atom.get('outgoing', []):
            visit(child)
    for atom in graph['roots']:
        visit(atom)
    return len(found)


def native_query(space, types, predicate, prefix, relation='EdgeLink'):
    """Execute a fixed authored Meet template, never an imported user program."""
    value = space.add_node(types.VariableNode, '$cael_bridge_result')
    declared = space.add_link(types.VariableList, [value])
    arguments = [space.add_node(getattr(types, kind), str(name)) for kind, name in prefix]
    body = space.add_link(getattr(types, relation), [
        space.add_node(types.PredicateNode, 'cael:'+predicate),
        space.add_link(types.ListLink, arguments+[value])])
    query = space.add_link(types.MeetLink, [declared, body])
    return sorted(atom.name for atom in query.execute().to_list())


def main(output, upstream_root):
    # Import the compiled extension before unittest can use an API double.
    import opencog.atomspace as actual
    assert actual.__file__.endswith('.so'), 'A real Linux compiled extension is required'
    from opencog.atomspace import AtomSpace, types, get_type_name
    output.mkdir(parents=True, exist_ok=False)
    record = dict(at_utc=datetime.now(timezone.utc).isoformat(), passed=False,
                  python=sys.version, platform=platform.platform(),
                  binding_file=actual.__file__, binding_sha256=sha(actual.__file__),
                  real_atomspace_imported=True, mock_qualifies=False, checks=[])
    def save(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    def check(label, condition):
        record['checks'].append(dict(name=label, passed=bool(condition)))
        if not condition:
            raise AssertionError(label)
    try:
        pins = json.loads((Path(__file__).parent/'UPSTREAM_PINS.json').read_text())
        record['upstream_pins'] = pins
        for project in ('cogutil', 'atomspace'):
            current = subprocess.check_output(['git', '-C', str(upstream_root/project), 'rev-parse', 'HEAD'], text=True).strip()
            check(project+' source pin', current==pins[project])
        import test_bridge
        tests = unittest.defaultTestLoader.loadTestsFromTestCase(test_bridge.BridgeTests)
        with (output/'unit_tests.log').open('w', encoding='utf-8') as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(tests)
        record['unit_tests'] = dict(run=result.testsRun, failed=len(result.failures),
                                   errors=len(result.errors), skipped=len(result.skipped))
        check('all unit tests including real import pass with zero skips',
              result.wasSuccessful() and result.testsRun==16 and not result.skipped)
        backend = engines(os.environ['CAEL040_ROOT'])
        record['cael_identity'] = backend[-1]
        check('exact released model', backend[-1]['model_sha256']=='a7f52da1f5afc6776af91d451a7273a269593642cd5f6d8a2883c4e34fab0bd4')
        record['evaluation_is_edge_alias'] = types.EdgeLink==types.EvaluationLink
        alias = record['evaluation_is_edge_alias']
        answers = []
        roundtrips = []
        for spec, expected in zip(episodes(), EXPECTED):
            exported = export_episode(spec, backend)
            answers.extend(zip([q['answer'] for q in exported['queries']], expected))
            save(spec['id']+'.input.json', spec)
            save(spec['id']+'.result.json', exported)
            for representation in ('EdgeLink', 'EvaluationLink'):
                graph = atom_graph(exported, representation)
                space, roots = import_atomspace(graph)
                before = len(space)
                decoded = [native_atom(atom, get_type_name) for atom in roots]
                expected_roots = [normalize_alias(atom, alias) for atom in graph['roots']]
                check(spec['id']+' '+representation+' full read-back', decoded==expected_roots)
                check(spec['id']+' '+representation+' exact unique atom count', before==count_unique(graph, alias))
                _, repeated = import_atomspace(graph, space)
                check(spec['id']+' '+representation+' idempotent insertion', len(space)==before and roots==repeated)
                roundtrips.append(dict(episode=spec['id'], representation=representation,
                                       roots=len(roots), unique_atoms=before, read_back_exact=True))
                save(spec['id']+'.'+representation+'.graph.json', graph)
        record['original_authored_fixtures'] = dict(episodes=9, query_answers=len(answers),
              desired_answers_matched=sum(a==e for a,e in answers), parser_failures_retained=2)
        check('the two original parser failures remain disclosed', len(answers)==17 and sum(a==e for a,e in answers)==15)
        record['roundtrips'] = roundtrips

        # Fresh synthetic scope/history fixtures in one actual shared AtomSpace.
        specs = [dict(id='same-label', events=['Zuri went to the loft', 'Zuri went to the pond'], logic='', queries=[]),
                 dict(id='same-label', events=['Zuri went to the studio', 'Zuri went to the tower'], logic='', queries=[])]
        shared = AtomSpace()
        exported = [export_episode(s, backend) for s in specs]
        for item in exported:
            import_atomspace(atom_graph(item), shared)
        scope_a = 'cael:episode:'+exported[0]['input_sha256']
        scope_b = 'cael:episode:'+exported[1]['input_sha256']
        def locations(scope, step):
            return native_query(shared, types, 'possible-location', [
                ('ConceptNode', scope), ('NumberNode', step), ('ConceptNode', 'zuri')])
        check('native query retrieves first historical state', locations(scope_a,1)==['loft'])
        check('native query retrieves latest state', locations(scope_a,2)==['pond'])
        check('same human label stays in separate input scope', locations(scope_b,2)==['tower'])
        check('missing snapshot has no fabricated fact', locations(scope_a,3)==[])
        save('shared_scope.inputs.json', specs)
        save('shared_scope.results.json', exported)

        logic_spec = dict(id='literal-polarities', events=[],
                          logic='Uma is calm. Uma is not calm.', queries=[])
        logical = export_episode(logic_spec, backend)
        logic_space, _ = import_atomspace(atom_graph(logical))
        scope = ('ConceptNode', 'cael:episode:'+logical['input_sha256'])
        check('native queries preserve both explicit polarities', native_query(logic_space,types,'logical-claim',
              [scope,('ConceptNode','uma'),('ConceptNode','calm')])==['negative','positive'])
        check('lack of a claim is not a negative claim', native_query(logic_space,types,'logical-claim',
              [scope,('ConceptNode','uma'),('ConceptNode','bitter')])==[])
        before = len(shared)
        invalid = atom_graph(exported[0])
        invalid['roots'].append(dict(type='ExecutionOutputLink', outgoing=[]))
        rejected = False
        try:
            import_atomspace(invalid, shared)
        except ValueError:
            rejected = True
        check('malformed graph rejected before shared-space mutation', rejected and len(shared)==before)

        # Bounded same-payload diagnostic, five fresh spaces per size/style.
        timings = []
        for size in (32,64,128):
            spec = dict(id='insertion-'+str(size), events=[
                'Zuri went to the '+('loft','courtyard','studio')[i%3] for i in range(size)], logic='', queries=[])
            payload = export_episode(spec, backend)
            for representation in ('EdgeLink','EvaluationLink'):
                graph = atom_graph(payload, representation)
                loads, queries, counts = [], [], []
                for repeat in range(5):
                    start = time.perf_counter()
                    space, roots = import_atomspace(graph)
                    loads.append(time.perf_counter()-start)
                    counts.append(len(space))
                    start = time.perf_counter()
                    got = native_query(space, types, 'possible-location', [
                        ('ConceptNode','cael:episode:'+payload['input_sha256']),
                        ('NumberNode',size),('ConceptNode','zuri')], representation)
                    queries.append(time.perf_counter()-start)
                    check('diagnostic query '+str(size)+' '+representation+' '+str(repeat),
                          got==[('loft','courtyard','studio')[(size-1)%3]])
                timings.append(dict(events=size, representation=representation, roots=len(roots),
                       unique_atoms=counts, insertion_seconds=loads, query_seconds=queries,
                       median_insertion_seconds=statistics.median(loads), median_query_seconds=statistics.median(queries)))
        record['same_payload_diagnostics'] = timings
        record['limitations'] = [
            'Authored integration fixtures and tiny same-host diagnostics, not benchmarks or a general speed ranking.',
            'Native Meet queries retrieve stored reported data; they do not establish OpenCog reasoning accuracy.',
            'Sensory source/examples were examined, not built or integrated in this job.',
            'No CAEL weight/source repair, neural runtime or model answer service was used.']
        record['passed'] = True
    except Exception:
        record['error'] = traceback.format_exc()
        traceback.print_exc()
    finally:
        record['files'] = {p.name:sha(p) for p in output.iterdir() if p.is_file()}
        save('receipt.json', record)
        print(json.dumps({k:record.get(k) for k in ['passed','unit_tests','original_authored_fixtures','error']}, indent=2))
    return 0 if record['passed'] else 1


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--upstream-root', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.output, args.upstream_root))
