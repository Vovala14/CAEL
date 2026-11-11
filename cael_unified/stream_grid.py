"""Lossless 2-D IO adapter for the native integer-stream automaton core.

This module does not solve grids. It validates the complete grid task, encodes
dimensions/cells, calls local_automata, and decodes its checked integer output.
"""
import json
from . import local_automata as core


def encode(value):
    if type(value) is not list or not 1<=len(value)<=30 or any(type(r) is not list for r in value):
        raise core.OutsideDomain('Supply a rectangular grid with 1 to 30 rows.')
    width=len(value[0])
    if not 1<=width<=30 or any(len(r)!=width for r in value):raise core.OutsideDomain('Supply 1 to 30 columns in every row.')
    if any(type(v) is not int or not 0<=v<=9 for r in value for v in r):raise core.OutsideDomain('Grid colors must be exact integers 0 through 9.')
    return core.lattice_stream([len(value),width,*(v for r in value for v in r)])


def decode(value):
    stream=core.lattice_stream(value);h,w=stream[:2]
    result=[list(stream[2+y*w:2+(y+1)*w]) for y in range(h)]
    if encode(result)!=stream:raise core.OutsideDomain('Output cannot be decoded within the grid IO contract.')
    return result


def solve(task):
    if type(task) is not dict or set(task)!={'examples','query'}:raise core.OutsideDomain('Use only complete examples and query.')
    if type(task['examples']) is not list:raise core.OutsideDomain('Examples must be a list.')
    examples=[]
    for e in task['examples']:
        if type(e) is not dict or set(e)!={'input','output'}:raise core.OutsideDomain('Every grid demonstration needs exactly input/output.')
        examples.append(dict(input=encode(e['input']),output=encode(e['output'])))
    query=encode(task['query']);result=core.lattice_fit(examples,query)
    prediction=decode(result['prediction'])
    result.update(input_stream=list(query),output_stream=result['prediction'],stream_format='height,width,row-major cells',native=True)
    return dict(prediction=prediction,program=result['program'],demonstrations_checked=result['demonstrations_replayed'],
        status='checked-inductive-hypothesis',engine='native-integer-stream',automaton=result,neural=False,assumptions=result['assumptions'])


def reply(task):
    try:result=solve(task)
    except (core.OutsideDomain,TypeError,KeyError,RecursionError,OverflowError) as exc:
        return dict(route='chat/grid-clarify',response='Please clarify the native stream task: '+str(exc),sources=[],
            grid_reasoning=dict(engine='native-integer-stream',status='unsupported-or-ambiguous',neural=False))
    return dict(route='chat/grid-induction',response=json.dumps(result['prediction']),sources=[],grid_reasoning=result,
        verification=dict(status='all-demonstrations-replayed',check=result['assumptions']))
