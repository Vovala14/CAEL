"""New authored relational boundaries/invariants; no old final task examples."""
from fractions import Fraction
import pytest
from cael_unified import semantic_quantities as s


def checked(text):
    result=s.reply(text)
    assert result and result.get('exact'),result
    proof=result['semantic_quantities']
    assert proof['whole_clauses_consumed'] and proof['starting_balances_not_assumed_zero']
    assert proof['arithmetic_check']['status']=='verified'
    nodes={n['id']:n for n in proof['nodes']}
    for node in nodes.values():
        assert text[slice(*node['span'])]==node['source']
        assert set(node['dependencies'])<=nodes.keys()
    assert len(proof['clauses'])==len(s.segments(text))-1
    return Fraction(proof['value'])


@pytest.mark.parametrize('rate,duration,expected',[('0.5',6,3),('1/4',12,3),('2.5',4,10)])
def test_fractional_rates_can_produce_complete_integer_items(rate,duration,expected):
    assert checked(f'The extruder makes {rate} clips per minute. It runs for {duration} minutes. How many clips does it make?')==expected


@pytest.mark.parametrize('seconds,answer',[(30,7),(90,21),(150,35)])
def test_rate_unit_reexpression_is_dimensionally_invariant(seconds,answer):
    assert checked(f'Asha produces 14 clips per minute. She works for {seconds} seconds. How many clips does Asha produce?')==answer


@pytest.mark.parametrize('count,unit_cost,starting',[(3,8,50),(5,7,80),(8,6,100)])
def test_purchase_changes_both_known_inventory_and_cash(count,unit_cost,starting):
    body=f'Ruva has {starting} dollars. Ruva has 2 clips. She buys {count} clips at {unit_cost} dollars each. '
    assert checked(body+'How many dollars does Ruva have left?')==starting-count*unit_cost
    assert checked(body+'How many clips does Ruva have now?')==2+count


def test_loss_and_revenue_are_distinct_and_loss_is_not_negative_inventory():
    body='Each pin costs 11 euros to make. Each pin sells for 8 euros. Jera sells 5 pins. '
    assert checked(body+'How much revenue does Jera earn?')==40
    assert checked(body+'How much profit does Jera earn?')==-15


def test_explicit_actor_is_usable_even_with_another_declared_rate():
    body='Pira prints 3 labels per minute. Cora prints 5 labels per minute. Pira works for 4 minutes. '
    assert checked(body+'How many labels does Pira print?')==12


def test_sequential_original_and_current_price_bases_are_distinct():
    body='A panel costs 160 dollars. Its price increases by 25 percent. '
    assert checked(body+'Its price decreases by 20 percent. What is its final price in dollars?')==160
    assert checked(body+'Its price decreases by 20 percent of its original price. What is its final price in dollars?')==168


@pytest.mark.parametrize('extra',[
    'She works only if the switch is on.',
    'She does not work for all of that time.',
    'She has an unstated efficiency loss.',
    'She works for 3 additional minutes.',
])
def test_extra_unknown_conditions_are_never_discarded(extra):
    text='Niva prints 4 labels per minute. She works for 5 minutes. '+extra+' How many labels does Niva print?'
    result=s.reply(text)
    assert result and result['route'].endswith('-clarify') and not result.get('exact')


@pytest.mark.parametrize('text',[
    'Niva prints 4 labels per minute. Niva prints 6 labels per minute. She works for 5 minutes. How many labels does Niva print?',
    'Niva prints 0 labels per minute. How many minutes does Niva need to print 8 labels?',
    'Niva has 14 clips. She loses -10 percent of her clips. How many clips does Niva have left?',
    'A tag costs 15 dollars. Its price increases by 20 percent. What is its final price in euros?',
    'Niva has 14 liters. She loses 50 percent of her liters. Niva has 30 liters. How many liters does Niva have?',
    'Niva has 14 liters. She loses 50 percent of her liters. How many dollars does Niva have?',
    'Niva has 40 dollars. She buys 3 clips at 4 euros each. How many dollars does Niva have left?',
    'Niva travels 4 kilograms per minute. She travels for 2 minutes. How many kilograms does Niva travel?',
])
def test_missing_zero_conflicting_units_and_action_dimensions_clarify(text):
    result=s.reply(text)
    assert result and result['route'].endswith('-clarify'),result
    assert not result.get('exact')


def test_sales_must_not_leave_a_stale_initial_cash_balance():
    text='Kira has 20 dollars. Kira has 20 clips. Each clip sells for 7 dollars. She sells 10 clips. She loses 10 percent of her clips. How many dollars does Kira have left?'
    result=s.reply(text)
    # This deliberately asks about cash after sales, not about the fractional
    # stock event's arithmetic. Unsupported cash scope must not assert20.
    assert not result.get('exact') or Fraction(result['semantic_quantities']['value'])==90


def test_legacy_rate_frames_and_quoted_code_keep_their_existing_owner():
    text='The pump pumps at a constant rate of 4 liters per minute for 7 minutes. How many liters does the pump pump?'
    assert s.reply(text) is None
    assert s.reply('"A press makes 4 tags per minute. It runs for 6 minutes. How many tags does it make?"') is None
    assert s.reply('def f():\n    """A press makes 4 tags per minute. How many tags does it make?"""') is None


def test_actual_unified_dispatch_style_and_independent_requests(tmp_path):
    from pathlib import Path
    from cael_unified.assistant import Assistant
    runtime=Path(__file__).resolve().parents[1]
    assistant=Assistant(runtime/'models/cael-0.3.7.cael',tmp_path/'out')
    text='Answer only with the number.\nA drill makes 24 disks per hour. It runs for 15 minutes. How many disks does it make?'
    first=assistant.respond([dict(role='user',content=text)],n=1,seed=312)
    assert first['response']=='6' and first.get('semantic_quantities')
    second=assistant.respond([dict(role='user',content='A drill makes 24 disks per hour. How many disks does it make?')],n=1,seed=312)
    assert second['route'].endswith('-clarify') and not second.get('exact')
