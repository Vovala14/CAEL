"""Run released CAEL on authored inputs and export JSON/Atomese data files."""
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
from bridge import engines,export_episode,atom_graph,scheme,import_atomspace
from demos import episodes,EXPECTED,KNOWN_PARSER_FAILURES
ap=argparse.ArgumentParser();ap.add_argument('--cael-root',required=True);ap.add_argument('--output',required=True);ap.add_argument('--atomspace',action='store_true');a=ap.parse_args()
R=Path(a.output).resolve();R.mkdir(parents=True,exist_ok=False);backend=engines(a.cael_root);counts=[]
for item,expected in zip(episodes(),EXPECTED):
    result=export_episode(item,backend);answers=[q['answer'] for q in result['queries']]
    graph=atom_graph(result)
    for suffix,value in [('input.json',item),('result.json',result),('graph.json',graph)]:
        (R/(item['id']+'.'+suffix)).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (R/(item['id']+'.scm')).write_text(scheme(graph),encoding='utf-8')
    atomspace=None
    if a.atomspace:
        space,roots=import_atomspace(graph);atomspace=dict(root_count=len(roots),all_roots_created=all(r is not None for r in roots))
    good=answers==expected;contract=answers==KNOWN_PARSER_FAILURES.get(item['id'],expected)
    counts.append(dict(id=item['id'],answers=answers,expected=expected,answers_match_desired=good,known_parser_failure=item['id'] in KNOWN_PARSER_FAILURES,
        bridge_contract_valid=contract,accepted_events=sum(e['accepted'] for e in result['events']),rejected_events=sum(not e['accepted'] for e in result['events']),atomspace=atomspace))
    print(json.dumps(counts[-1]),flush=True)
receipt=dict(at=datetime.now(timezone.utc).isoformat(),python=sys.version,cael_root=str(Path(a.cael_root).resolve()),cael_identity=backend[-1],authored_episodes=len(counts),
    answers=sum(len(x['answers']) for x in counts),answers_matching_desired=sum(a==e for x in counts for a,e in zip(x['answers'],x['expected'])),
    episodes_matching_desired=sum(x['answers_match_desired'] for x in counts),bridge_contracts_valid=sum(x['bridge_contract_valid'] for x in counts),results=counts,
    actual_atomspace_import_tested=a.atomspace,scope='Authored interoperability fixtures, not chatbot/benchmark capability scores.',
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file()})
(R/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if all(x['bridge_contract_valid'] for x in counts) else 1)
