"""Independent quantities/invariants/negative controls for the finite graph."""
from fractions import Fraction
from itertools import permutations
import pytest

from cael_unified import quantity_graph as q


def value(text):
    answer=q.reply(text)
    assert answer and answer['route']=='helper/quantity-graph',answer
    proof=answer['quantity_graph']
    assert proof['whole_clauses_consumed'] and proof['initial_states_not_assumed_zero']
    assert proof['arithmetic_check']['status']=='verified'
    nodes={n['id']:n for n in proof['dependencies']}
    for n in nodes.values():
        assert text[slice(*n['span'])]==n['source']
        assert set(n['dependencies']) <= nodes.keys()
    assert len(proof['parsed_facts'])==len(q.segments(text))-1
    return Fraction(proof['value'])


@pytest.mark.parametrize('a,b,transfer',[(a,b,c) for a in (5,14,29) for b in (0,7,16) for c in (0,2,4)])
def test_transfer_conserves_total_and_changes_recipient(a,b,transfer):
    text=f'R7 has {a} washers. B4 has {b} washers. R7 gives {transfer} washers to B4. '
    assert value(text+'How many washers do R7 and B4 have in total?')==a+b
    assert value(text+'How many washers does B4 have?')==b+transfer


@pytest.mark.parametrize('base,extra,factor',[(a,b,c) for a in (3,11,24) for b in (1,5) for c in ('1/2','3')])
def test_initial_relations_order_independent(base,extra,factor):
    facts=[f'Fira has {base} purple disks.',f'Xeno has {extra} more purple disks than Fira.',f'Bevi has {factor} times as many purple disks as Xeno.']
    for ordering in permutations(facts):
        assert value(' '.join(ordering)+' How many purple disks does Bevi have?')==(base+extra)*Fraction(factor)


@pytest.mark.parametrize('outer,inner,count',[(a,b,c) for a in (2,7) for b in (3,8) for c in (4,9)])
def test_group_composition_has_typed_dependencies(outer,inner,count):
    text=f'Each bin contains {outer} boxes. Each box contains {inner} clips. Seno has {count} bins. How many clips does Seno have?'
    assert value(text)==outer*inner*count


@pytest.mark.parametrize('a,b,c,d',[(2,3,4,5),(7,2,9,3),(1,8,3,2),(4,7,6,5)])
def test_prices_belong_to_transactions_and_cash(a,b,c,d):
    text=f'Ola has 200 dollars. Ola buys {a} ribbons at {b} dollars each. Ola buys {c} ribbons at {d} dollars each. '
    assert value(text+'How much did Ola spend?')==a*b+c*d
    assert value(text+'How many dollars does Ola have left?')==200-a*b-c*d
    assert value(text+'How many ribbons did Ola buy?')==a+c


@pytest.mark.parametrize('a,b',[(1,125),(3,45),(7,250)])
def test_physical_units_are_not_extra_inventory_categories(a,b):
    assert value(f'Irina has {a} kilograms. Irina receives {b} grams. How many grams does Irina have?')==a*1000+b
    assert value(f'Irina has {a} liters. Irina uses {b} milliliters. How many milliliters does Irina have?')==a*1000-b


def test_subset_total_is_not_added_to_parts_and_updates_with_them():
    assert value('Jera has 9 buttons. Jera has 4 red buttons. How many buttons does Jera have?')==9
    assert value('Jera has 9 buttons. Jera has 4 red buttons. Jera loses 2 red buttons. How many buttons does Jera have?')==7
    assert value('Jera has 9 buttons. Jera has 4 red buttons. How many items does Jera have?')==9
    answer=q.reply('Jera has 9 buttons. Jera has 4 red buttons. Jera loses 2 buttons. How many red buttons does Jera have?')
    assert answer['route'].endswith('-clarify')


@pytest.mark.parametrize('text',[
    'Rina has 3 pins. How many pins do Rina and Rina have?',
    'Rina has 3 pins. How many pins do Rina or Noa have?',
    'Rina has 3 pins. Rina loses 9 pins. How many pins does Rina have?',
    'Rina has 3 pins. Rina has 9 red pins. How many pins does Rina have?',
    'Rina has 3 pins. Rina gains an unspecified bonus. How many pins does Rina have?',
    'Rina has 3 pins. Rina loses 1 pin except on holidays. How many pins does Rina have?',
    'Each bin contains -2 boxes. Rina has 3 bins. How many boxes does Rina have?',
    'Each clip costs -2 dollars. Rina buys 3 clips. How much did Rina spend?',
    'Rina buys 3 clips at -2 dollars each. How much did Rina spend?',
    'Each clip costs 2 dollars. Each clip costs 3 dollars. Rina buys 4 clips. How much did Rina spend?',
    'Each bin contains 2 bins. Rina has 3 bins. How many bins does Rina have?',
    'Rina has twice as many pins as Noa. Noa has twice as many pins as Rina. How many pins does Rina have?',
    'Rina buys 3 pins. Rina has 9 pins. How many pins does Rina have?',
    'Rina has 3 dollars. Rina buys 2 pins. How many dollars does Rina have?',
    'Rina has 3 dollars. Rina buys 2 pins at 4 euros each. How much money does Rina have?',
])
def test_unresolved_contradictory_unsupported_constraints_do_not_get_a_subtotal(text):
    answer=q.reply(text)
    assert answer and answer['route']=='helper/quantity-graph-clarify',answer
    assert not answer.get('exact') and 'quantity_graph' not in answer


@pytest.mark.parametrize('text',[
    'How many moons does Mars have?',
    'Write a picture prompt about red cars.',
    'I have 3 bad days. Why do I feel sad?',
    '```python\nx = "Rina has 3 pins. How many pins does Rina have?"\n```',
    'Translate "Rina has 3 pins. How many pins does Rina have?"',
])
def test_ordinary_facts_emotion_code_and_quoted_tasks_not_owned(text):
    assert q.reply(text) is None


def test_explicit_incompatible_currencies_are_not_added():
    assert value('Eri has 7 dollars. Eri receives 3 euros. How many dollars does Eri have?')==7
    answer=q.reply('Eri has 7 dollars. Eri receives 3 euros. How much money does Eri have?')
    assert answer['route'].endswith('-clarify')


def test_initial_relations_do_not_change_retroactively_after_events():
    text='Nola has 6 tokens. Fira has twice as many tokens as Nola. Nola receives 3 tokens. '
    assert value(text+'How many tokens does Fira have?')==12
    assert value(text+'How many tokens does Nola have?')==9


def test_more_than_four_choices_matches_checked_graph_not_a_four_label_controller():
    context='Each box holds 7 feathers. Uri has 4 boxes. How many feathers does Uri have?'
    answer=q.choice_reply(context,['18','20','24','26','27','28','29'])
    assert answer['choice']==5 and answer['response']=='F. 28'
    assert q.choice_reply(context,['27','29'])['route'].endswith('-clarify')


def test_proof_sources_and_values_do_not_leak_between_requests():
    assert value('Anya has 9 shells. How many shells does Anya have?')==9
    answer=q.reply('Ren has 2 pins. How many shells does Anya have?')
    assert answer['route'].endswith('-clarify')
