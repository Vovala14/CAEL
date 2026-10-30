"""New non-final boundaries and compositional counterexamples."""
import pytest
from cael_unified.checked_tasks import reply

@pytest.mark.parametrize('text',[
    'Quote this sentence: Sort these words alphabetically: sun ash.',
    'Explain why people sort these words alphabetically.',
    'Write Python that prints "Today is 2034-04-19".',
    'Translate "I have three plums" into French.',
    'I have a question about how friendships change.',
    'Sort these words alphabetically: "quoted literal"',
])
def test_quoted_or_unrelated_requests_are_not_executed(text):
    assert reply(text) is None

@pytest.mark.parametrize('text',[
    'Evaluate the truth value of True and missing_flag.',
    'I have two plastic pears and a mango. How many fruits do I have?',
    'I have three crates of oboes. How many instruments do I have?',
    'Items: east box, west box. The east box is first. The west box is first. Who is first?',
    'There are four beads: oak bead, ash bead, elm bead. The oak bead is first. Who is first?',
    'Today is 2036-03-01. What date is it 2 hours earlier?',
    'Today is 2036-03-01. What date is tomorrow?\n(A) 03/02/2036\n(A) 02/29/2036',
])
def test_missing_conflicting_or_unconsumed_constraints_never_guess(text):
    answer=reply(text)
    assert answer and answer['route']=='helper/checked-clarify' and not answer.get('exact')

def test_six_choice_proof_works_without_count_model():
    text=('Objects: amber disk, slate disk, gold disk. The slate disk is first. '
          'The amber disk is left of the gold disk. Which statement must be true?\n'
          '(A) The slate disk is third\n(B) The gold disk is first\n(C) The amber disk is third\n'
          '(D) The slate disk is second\n(E) The gold disk is second\n(F) The amber disk is second')
    answer=reply(text)
    assert answer['choice']==5 and answer['exact']
    assert answer['helper_reasoning']['evidence']['valid_orders']==1

def test_no_arbitrary_tie_resolution():
    text=('Items: mint, sage, thyme. Mint is left of thyme. Which statement must be true?\n'
          '(A) The mint is left of the thyme\n(B) The thyme is right of the mint')
    assert reply(text)['route']=='helper/checked-clarify'

def test_literal_item_query_is_distinct_from_category_membership():
    answer=reply('I have six pears and three apples. How many apples do I have?')
    assert answer['response']=='3' and answer['exact']
    assert answer['helper_reasoning']['evidence']['category']=='apple'
