"""Regression for cross-request rule leakage, explicit reuse and concurrency."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from cael_unified import ltm,rules

def seed(memory,name='sprout_total'):
    return memory.add_rule(name,['u'],f'def {name}(u):\n    return u * 7 + 2\n',
                           'affine growth total result',8)

def test_default_request_is_ephemeral_and_nested_scope_reuses_it(tmp_path,monkeypatch):
    path=tmp_path/'unrequested.json';monkeypatch.setenv('CAEL_LTM',str(path))
    with ltm.request_memory() as first:
        seed(first)
        with ltm.request_memory() as nested:assert nested is first
    with ltm.request_memory() as second:
        assert second is not first and second.rule('sprout_total') is None
    assert not path.exists()

def test_explicit_sessions_reuse_only_their_own_rules():
    first,second=ltm.Memory(persistent=False),ltm.Memory(persistent=False)
    with ltm.request_memory(first):seed(ltm.memory())
    with ltm.request_memory(first):assert ltm.memory().rule('sprout_total') is not None
    with ltm.request_memory(second):assert ltm.memory().rule('sprout_total') is None

def test_no_fuzzy_or_incidental_name_reuse():
    store=ltm.Memory(persistent=False);seed(store)
    assert store.find_rule('Write a different function for affine growth total result') is None
    assert store.find_rule('Write sprout_total with a different contract') is None
    assert store.find_rule('Reuse the learned function sprout_total') is not None

def test_parallel_requests_cannot_observe_each_others_rule():
    barrier=threading.Barrier(4)
    def work(i):
        with ltm.request_memory() as store:
            seed(store,'shoot_'+str(i));barrier.wait(timeout=10)
            return set(ltm.memory().data['rules'])=={'shoot_'+str(i)}
    with ThreadPoolExecutor(max_workers=4) as pool:assert all(pool.map(work,range(4)))

def test_exception_does_not_leak_scope():
    with pytest.raises(RuntimeError):
        with ltm.request_memory() as store:
            seed(store);raise RuntimeError('synthetic request failed')
    with ltm.request_memory() as clean:assert not clean.data['rules']

def test_learned_rule_uses_bounded_vm_and_refuses_unsupported():
    store=ltm.Memory(persistent=False);rule=seed(store)
    assert rules.run_rule(rule,(9,))==65
    with pytest.raises(ValueError):
        rules.run_rule(dict(name='sprout_total',code='def sprout_total(u):\n    import os\n    return u\n'),(9,))
    with pytest.raises(ValueError):
        rules.run_rule(dict(name='sprout_total',code='def sprout_total(u):\n    while True:\n        u += 1\n'),(9,))

def test_actual_assistant_defaults_are_isolated_but_explicit_session_works(tmp_path):
    from pathlib import Path
    from cael_unified.assistant import Assistant
    from cael_unified.bundle import ROOT
    store=ltm.Memory(persistent=False);seed(store)
    anonymous=Assistant(ROOT/'models/cael-0.3.7.cael',tmp_path/'anonymous')
    explicit=Assistant(ROOT/'models/cael-0.3.7.cael',tmp_path/'explicit',learning_memory=store)
    message=[dict(role='user',content='Run sprout_total on 9')]
    first=anonymous.respond(message,n=1,seed=71,mode='chat')
    owned=explicit.respond(message,n=1,seed=71,mode='chat')
    second=anonymous.respond(message,n=1,seed=71,mode='chat')
    assert owned['route']=='chat/rules-use' and '**65**' in owned['response']
    assert first['route']!='chat/rules-use' and second['route']!='chat/rules-use'
    assert store.rule('sprout_total')['uses']==1
