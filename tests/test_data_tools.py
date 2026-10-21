"""Authored data tasks: compare emitted Python with independent references."""
import copy
import re

import pytest

from cael_unified.codegen.chat import reply
from cael_unified.codegen import data_tools as data


def prompt(domain,steps,use=data.MISSING,source='',name='process'):
    text='Build a Python tool named '+name+' for '+domain+'.\n'
    if source:text+='```python\n'+source+'\n```\n'
    text+='Steps:\n'+'\n'.join(steps)
    if use is not data.MISSING:text+='\nUse it on '+repr(use)
    return text


ROWS=[{'team':'a','qty':2,'price':3,'name':'Ada','active':True},
      {'team':'b','qty':1,'price':5,'name':'Bo','active':False},
      {'team':'a','qty':3,'price':4,'name':'Cy','active':True}]


def test_record_filter_calculate_group_report_pipeline():
    steps=["keep where x['active']", "sum x['qty']*x['price'] by x['team']",
           "map entries {'team':key,'total':value}","sort by x['total'] descending"]
    plan=data.parse(prompt('records',steps,ROWS));built=data.build(plan)
    assert built['status']=='built',built
    scope={};exec(built['source'],scope)
    assert scope['process'](ROWS)==[{'team':'a','total':18}]
    more=[dict(r,team='q') for r in ROWS]+[dict(ROWS[0],team='z',qty=8)]
    assert scope['process'](more)==[{'team':'z','total':24},{'team':'q','total':18}]


@pytest.mark.parametrize('steps,expected',[
    (["select fields ['name','qty']","sort by x['qty'] descending"],[{'name':'Cy','qty':3},{'name':'Ada','qty':2},{'name':'Bo','qty':1}]),
    (["count by x['team']"],{'a':2,'b':1}),
    (["unique by x['team']","map x['name']"],['Ada','Bo']),
    (["group by x['team']","map entries {'key':key,'n':len(value)}"],[{'key':'a','n':2},{'key':'b','n':1}]),
    (["index by x['team'] keeping first","values of mapping","map x['name']"],['Ada','Bo']),
    (["index by x['team'] keeping last","keys of mapping"],['a','b']),
    (["sum x['qty']*x['price']"],23),
    (["map x.get('missing', 0)","sum"],0),
    (["take the last 0 records","count"],0),
])
def test_record_primitives_match_cpython(steps,expected):
    result=data.build(data.parse(prompt('records',steps,ROWS)))
    assert result['status']=='built',result
    assert result['value']==expected
    scope={};exec(result['source'],scope)
    assert scope['process'](ROWS)==expected


@pytest.mark.parametrize('text,steps,expected',[
    (' A\r\nb\n',['split lines','strip each value','casefold each value','keep nonempty values','join with "|"'],'a|b'),
    ('AA,bb;CC',['split on ","','lowercase each value',"join with ';'"],'aa;bb;cc'),
    (' A a B! a. ',['split words',"map x.strip('!.').casefold()",'keep nonempty values','count by x'],{'a':3,'b':1}),
    ('Stra\u00dfe STRASSE',['split words','casefold each value','unique by x','join with ";"'],'strasse'),
    ('a\nb\n',['split lines','join with " "','split words','count'],2),
    ('a  b',['split words','map {"word":x,"length":len(x)}','sort by x["word"] descending'],[{'word':'b','length':1},{'word':'a','length':1}]),
])
def test_text_compositions(text,steps,expected):
    result=data.build(data.parse(prompt('text',steps,text)))
    assert result['status']=='built',result
    assert result['value']==expected
    scope={};exec(result['source'],scope);assert scope['process'](text)==expected


def test_supplied_helper_reads_record_fields_and_is_reused_in_group_entries():
    source='def report(key,items):\n    return {"label":key,"sum":sum(x["qty"] for x in items)}'
    result=reply(prompt('records',["group by x['team']",'map entries using report'],ROWS,source))
    assert result['route']=='chat/code-data-tool-built',result
    assert "[{'label': 'a', 'sum': 5}, {'label': 'b', 'sum': 1}]" in result['response']


def test_coupled_state_scan_returns_independent_snapshots_and_preserves_input():
    source='def update(state,row):\n    state["sum"]=state.get("sum",0)+row["qty"]\n    state["count"]=state.get("count",0)+1\n    return state'
    for operation in ['scan','fold']:
        request=prompt('records',[operation+' using update starting with {}'],ROWS,source)
        result=data.build(data.parse(request));assert result['status']=='built',result
        scope={};exec(result['source'],scope);incoming=copy.deepcopy(ROWS);actual=scope['process'](incoming)
        assert incoming==ROWS
        if operation=='scan':
            assert actual==[{'sum':2,'count':1},{'sum':3,'count':2},{'sum':6,'count':3}]
            assert actual[0] is not actual[1]
            actual[0]['sum']=999;assert actual[1]['sum']==3
        else:assert actual=={'sum':6,'count':3}


def test_helper_mutation_operates_on_copies_not_caller_records():
    source='def tag(row):\n    row["flag"]=True\n    return row'
    built=data.build(data.parse(prompt('records',['map using tag'],ROWS,source)))
    assert built['status']=='built',built
    scope={};exec(built['source'],scope);incoming=copy.deepcopy(ROWS);actual=scope['process'](incoming)
    assert incoming==ROWS and all(row['flag'] for row in actual)


def test_use_followups_reconstruct_human_data_tool_without_global_installation():
    first=prompt('text',['split words','casefold each value','count by x'])
    answer=reply(first);history=[dict(role='user',content=first),dict(role='assistant',content=answer['response'])]
    for text,wanted in [('Use it on "A a B"',"{'a': 2, 'b': 1}"),('Use it on "C C"',"{'c': 2}")]:
        history.append(dict(role='user',content=text));answer=reply(text,messages=history)
        assert answer['route']=='chat/code-data-tool-used' and wanted in answer['response'],answer
        history.append(dict(role='assistant',content=answer['response']))
    assert data.reply('Use it on "A B"') is None


@pytest.mark.parametrize('domain,steps,use,route',[
    ('records',["index by x['team']"],ROWS,'clarify'),
    ('records',["index by x['team'] rejecting duplicates"],ROWS,'execution-error'),
    ('records',["select fields ['absent']"],ROWS,'execution-error'),
    ('records',['sum','map x+1'],ROWS,'clarify'),
    ('records',["group by x['team']","sort by x descending"],ROWS,'clarify'),
    ('text',['strip each value'],'hello','clarify'),
    ('text',['split words','map open(x)'],'hello','clarify'),
    ('records',['map x.__class__'],ROWS,'clarify'),
    ('text',['split words','sort the words but keep last unchanged'],'a b','clarify'),
    ('records',["sum x['qty']"],[{'qty':1.5}],'clarify'),
    ('text',['split words','count'],['a'],'clarify'),
])
def test_unknown_conflicting_and_unsupported_tasks_are_not_claimed_as_success(domain,steps,use,route):
    answer=reply(prompt(domain,steps,use))
    assert answer['route']=='chat/code-data-tool-'+route,answer
    assert '```python' not in answer['response'],answer


def test_contradictory_example_blocks_success():
    answer=reply(prompt('text',['split words','count'])+'\nprocess("a b") == 3')
    assert answer['route']=='chat/code-data-tool-contradiction',answer


def test_unsupported_unreached_helper_capability_is_declined():
    source='def f(x):\n    if x=="secret": return open("never_opened").read()\n    return x'
    answer=reply(prompt('text',['split words','map using f'],'hello',source))
    assert answer['route']=='chat/code-data-tool-clarify',answer


def test_literal_delimiters_are_not_mistaken_for_steps():
    answer=reply(prompt('text',["split on ';'","join with ' then '"],'a;b'))
    assert answer['route']=='chat/code-data-tool-built' and "'a then b'" in answer['response'],answer


def test_existing_integer_and_object_code_paths_remain_separate():
    assert data.reply('Build a Python tool named f.\nSteps:\nsum') is None
    assert data.reply('Review this Python code:\n```python\ndef f(x): return x\n```') is None
