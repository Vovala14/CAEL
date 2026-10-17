"""Evaluate official held-out text tasks; benchmark questions never train the model."""
from collections import Counter
import hashlib
import json
import re
import time
from .bundle import ROOT
from .reasoning_data import DATA, TASKS, babi, pronto, signature
from .reasoning_logic import LogicCA, Unparsed
from .reasoning_world import WorldCA
from .reasoning_relations import relations
from .reasoning_order import solve_order, condition


def main():
    started=time.monotonic()
    model_path=ROOT/'models/cael-reasoning-v1/model.json'
    model=json.loads(model_path.read_text(encoding='utf-8'))
    logic=LogicCA(model)
    scores={}
    failures=[]
    for task in TASKS:
        correct=answered=total=0
        for row in babi(task,'test'):
            total+=1
            context=' '.join(text for _,text in row['context'])
            try:
                if task==15:
                    result=logic.query(context,row['question'])
                elif task in (18,19):
                    result=relations(context,row['question'])
                else:
                    result=WorldCA(model).query(context,row['question'])
                answer=result['answer']
                answered+=answer not in ('unknown','conflicting')
                equal=set(answer.lower().split(','))==set(row['answer'].lower().split(',')) if task==8 else answer.lower()==row['answer'].lower()
                correct+=equal
            except Unparsed as error:
                answer='unsupported: '+str(error)
                equal=False
            if not equal and sum(f.get('task')==task for f in failures)<3:
                failures.append(dict(task=task,question=row['question'],expected=row['answer'],actual=answer,context=context))
        scores[str(task)]=dict(correct=correct,answered=answered,total=total)
        print('bAbI',task,json.dumps(scores[str(task)]),flush=True)
    pronto_scores={}
    training=set(model['training']['training_context_hashes'])
    direct_correct=total_correct=total=overlap=0
    for row in pronto():
        if row['slot']!='test_example':
            continue
        total+=1
        family='Horn-style' if any(name in row['file'] for name in ('AndIntro','AndElim','ProofsOnly')) else 'Other/OOD logic'
        score=pronto_scores.setdefault(family,Counter())
        score['total']+=1
        overlap+=signature(row['question']) in training
        try:
            result=logic.query(row['question'],row['query'])
            score['parsed']+=1
            equal=result['answer']=='true'  # These are positive "Prove:" tasks.
            score['correct']+=equal
            total_correct+=equal
            # One-step / recall ablation: remove rules while retaining source facts.
            facts,_=logic.parse(row['question'])
            fact_text=' '.join(f"{e} is {'not ' if n else ''}{p}." for (e,p,n),_ in facts)
            direct=logic.query(fact_text,row['query'])['answer']=='true'
            direct_correct+=direct
            score['direct_fact_correct']+=direct
        except Unparsed:
            score['unsupported']+=1
    pronto_total=total
    print('PrOntoQA',json.dumps(pronto_scores),flush=True)
    ordering_scores={}
    for n in (3,5,7):
        data=json.loads((DATA/f'ordering_{n}.json').read_text(encoding='utf-8'))
        correct=total=0
        for row in data['examples']:
            total+=1
            try:
                names,solutions=solve_order(row['input'])
                entailed=[]
                for choice in row['target_scores']:
                    op,a,b=condition(choice,names)
                    value=all(order.index(a)<order.index(b) if op=='before' else order.index(a)==b for order in solutions) if solutions else False
                    if value:
                        entailed.append(choice)
                correct+=len(entailed)==1 and row['target_scores'][entailed[0]]==1
            except Unparsed as error:
                if sum(f.get('task')=='ordering' for f in failures)<6:
                    failures.append(dict(task='ordering',context=row['input'],error=str(error)))
        ordering_scores[str(n)]=dict(correct=correct,total=total)
        print('Ordering',n,json.dumps(ordering_scores[str(n)]),flush=True)
    report=dict(model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),babi=scores,pronto=pronto_scores,
                pronto_direct_fact_ablation_correct=direct_correct,pronto_multistep_correct=total_correct,pronto_total=pronto_total,
                pronto_train_test_context_overlap=overlap,ordering=ordering_scores,failures=failures,seconds=round(time.monotonic()-started,2),
                limitations='Synthetic bounded-language benchmarks, not general factual QA. bAbI uses case-insensitive exact matches (set matches for item lists). Solvers and grammar schema are authored; event lexicons and transition counts are trained. PrOntoQA proof targets are positive-only; negative/unknown controls require separate tests. BIG-bench ordering was evaluation-only, but its public task schema was inspected during implementation.')
    (ROOT/'models/cael-reasoning-v1/report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
