"""Evaluate CAEL within its authored synthetic schema, not a general AI benchmark."""
import argparse
import hashlib
import importlib.util
import json
import random
import time
from pathlib import Path
import numpy as np
from cael import CAEL, Unsupported
from curriculum import hashframe, initial_rows, teacher, packet, PLANS

ROOT=Path(__file__).resolve().parent

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')

def score_single(model, frames):
    result=dict(frames=len(frames),exact_plans=0,correct_state_rows=0,correct_fact_queries=0,grammar_terminations=0)
    for i,f in enumerate(frames):
        model.world=model.initial_world()
        ref=initial_rows()
        events=model.plan(f,seed=i)
        assert [model.events[e] for e in events]==PLANS[f['intent']]
        result['exact_plans']+=1
        p=packet(f)
        for event in events:
            ref=[teacher(row,p,model.events[event]) for row in ref]
            model.apply(event,f)
            assert np.array_equal(model.world,np.array(ref,np.int32)), ('single state mismatch',i,f)
            result['correct_state_rows']+=len(ref)
        model.last_frame=dict(f)
        for row in ref:
            queries=[]
            if row[1]==1:
                name=model.model['actors'][row[0]-1]
                if row[3]:queries.append(('Where is the '+name+'?',row[3]))
                if row[5]:queries.append(('Who helped the '+name+'?',row[5]))
            else:
                name=model.model['objects'][row[0]-101]
                if row[2]:queries.append(('Who has the '+name+'?',row[2]))
                if row[4]:queries.append(('Who found the '+name+'?',row[4]))
            for text,expected in queries:
                assert model.ask(text)['value']==expected,(i,text)
                result['correct_fact_queries']+=1
        if i<100:
            for event in events:
                assert model.render(event,f,('grammar',i,event)).endswith('.')
                result['grammar_terminations']+=1
        if (i+1)%500==0:
            print('single',i+1,'/',len(frames),flush=True)
    return result

def episode_score(model, episodes, unsupported_types=(Unsupported,)):
    result=dict(episodes=len(episodes),successful_episodes=0,missing_rule_episodes=0,state_mismatch_episodes=0,state_rows_checked=0)
    misses=[]
    for index,frames in enumerate(episodes):
        model.world=model.initial_world()
        ref=initial_rows()
        failed=False
        for frame in frames:
            p=packet(frame)
            for event in PLANS[frame['intent']]:
                ref=[teacher(row,p,event) for row in ref]
                try:
                    model.apply(model.eid[event],frame)
                except unsupported_types as exc:
                    result['missing_rule_episodes']+=1
                    misses.append(dict(episode=index,event=event,error=str(exc)))
                    failed=True
                    break
                result['state_rows_checked']+=len(ref)
                if not np.array_equal(model.world,np.array(ref,np.int32)):
                    result['state_mismatch_episodes']+=1
                    misses.append(dict(episode=index,event=event,error='state mismatch'))
                    failed=True
                    break
            if failed:
                break
        if not failed:
            result['successful_episodes']+=1
    result['first_failures']=misses[:10]
    return result

def main(model_path, out):
    started=time.monotonic()
    manifest=json.loads((model_path.parent/'manifest.json').read_text())
    assert digest(model_path)==manifest['model_sha256']
    for name,sha in manifest['source_sha256'].items():
        assert digest(ROOT/name)==sha, ('training source changed',name)
    data=ROOT/'research'/model_path.parent.name
    for name,sha in manifest['dataset_sha256'].items():
        assert digest(data/name)==sha, ('training/evaluation data changed',name)
    frames={s:json.loads((data/(s+'_frames.json')).read_text()) for s in ('train','development','confirmation')}
    keys={s:{hashframe(f) for f in rows} for s,rows in frames.items()}
    assert all(len(keys[s])==len(frames[s]) for s in frames)
    assert not keys['train']&keys['development'] and not keys['train']&keys['confirmation'] and not keys['development']&keys['confirmation']
    excluded=set(json.loads((ROOT/'natural_frame_holdout.json').read_text()))
    assert not keys['train']&excluded
    save(out/'split_audit.json',dict(canonical_frame_disjoint=True,counts={s:len(k) for s,k in keys.items()},natural_frames_excluded=len(excluded),hashes_verified=True))
    model=CAEL(model_path)
    singles={s:score_single(model,frames[s]) for s in ('development','confirmation')}
    legacy_spec=importlib.util.spec_from_file_location('cael_legacy_reference',ROOT/'reference'/'legacy_engine.py')
    legacy=importlib.util.module_from_spec(legacy_spec)
    legacy_spec.loader.exec_module(legacy)
    baseline_path=ROOT/'reference'/'model.json'
    assert digest(baseline_path)=='25bf1c55aff6198640799f8f860b031f2b693d7ef67eae3647d1916aa83ce363'
    baseline=legacy.EventCA(baseline_path)
    rng=random.Random(2026101320)
    cumulative={}
    for s in ('development','confirmation'):
        episodes=[rng.sample(frames[s],rng.randint(2,4)) for _ in range(200)]
        save(data/(s+'_evaluation_episodes.json'),episodes)
        cumulative[s]=dict(source=episode_score(baseline,episodes,(legacy.Unsupported,)),candidate=episode_score(model,episodes))
    natural=[]
    trained_texts=set(json.loads((data/'train_response_hashes.json').read_text()))
    for i,prompt in enumerate(json.loads((ROOT/'natural_prompts.json').read_text())):
        m=CAEL(model_path)
        try:
            response=m.story(prompt,20261016+i)
            same_frame=hashframe(response['frame']) in keys['train']
            same_text=hashlib.sha256(' '.join(response['response'].casefold().split()).encode()).hexdigest() in trained_texts
            assert not same_frame and not same_text
            questions=[]
            f=response['frame']
            a=m.model['actors'][f['a']]; b=m.model['actors'][f['b']]; item=m.model['objects'][f['i']]
            for q in [f'Where is the {a}?',f'Who has the {item}?',f'Who found the {item}?',f'Who helped the {b}?']:
                try:questions.append(dict(question=q,**m.ask(q)))
                except Unsupported as exc:questions.append(dict(question=q,supported=False,reason=str(exc)))
            natural.append(dict(prompt=prompt,supported=True,**response,questions=questions,frame_in_training=same_frame,full_response_in_training=same_text))
        except Unsupported as exc:
            natural.append(dict(prompt=prompt,supported=False,reason=str(exc)))
    save(out/'raw_examples.json',natural)
    passed=all(v['exact_plans']==v['frames'] for v in singles.values()) and all(v['candidate']['successful_episodes']==v['candidate']['episodes'] and v['candidate']['successful_episodes']>=v['source']['successful_episodes'] for v in cumulative.values())
    summary=dict(family='CAEL',version='0.1.0',variant='CAEL Story',
        model_sha256=digest(model_path),baseline_sha256=digest(baseline_path),
        model_bytes=model_path.stat().st_size,training=manifest,single_frame=singles,cumulative=cumulative,
        natural_prompts=dict(total=len(natural),supported=sum(x['supported'] for x in natural),outside_scope=sum(not x['supported'] for x in natural)),
        acceptance_passed=passed,seconds=time.monotonic()-started,
        scope='same authored synthetic world; no general-chat/ToM/leaderboard/independent-quality claim',
        evaluation_code_sha256=digest(__file__))
    save(out/'results.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='training'},indent=2))
    if not passed:
        raise SystemExit('Predeclared CAEL gate failed; inspect retained evidence before publication')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,default=ROOT/'models'/'cael-story-0.1'/'model.json')
    p.add_argument('--out',type=Path,default=ROOT/'results'/'cael-story-0.1')
    a=p.parse_args();main(a.model.resolve(),a.out.resolve())
