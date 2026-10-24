"""Authored ordering logic, independent model enumeration, and dialogue boundaries."""
import itertools
import pytest
from cael_unified.reasoning_order import ordering, solve_order, chat_scope
from cael_unified.reasoning_logic import Unparsed
from cael_unified.reasoning import Reasoner

BASE='Items: Nori, Luma, Zed. Nori is before Luma.'

@pytest.mark.parametrize('clues,question,expected',[
    ('Nori is not before Luma. Zed is last.','Who is first?','luma'),
    ('Nori is immediately before Luma. Luma is third.','Who is first?','zed'),
    ('Nori is directly after Luma. Luma is first.','Who is second?','nori'),
    ('Nori is not first. Luma is last.','Who is first?','zed'),
    ('Nori is not last. Luma is first.','Who is last?','zed'),
    ('Luma is between Nori and Zed. Nori is before Zed.','Who is second?','luma'),
    ('Luma is next to Nori. Nori is first.','Who is last?','zed'),
    ('Luma is not adjacent to Nori. Nori is first.','Who is second?','zed'),
    ('Luma is not immediately before Nori. Luma is first.','Who is second?','zed'),
    ('Nori is second from the right. Luma is last.','Who is first?','zed'),
    ('Nori is first.','Who is in the middle?','unknown'),
    ('Nori is before Luma. Luma is before Zed.','What is the complete order?','nori, luma, zed'),
    ('Nori is before Luma. Luma is before Nori.','Who is first?','conflicting'),
])
def test_supported_constraints(clues,question,expected):
    assert ordering('Items: Nori, Luma, Zed. '+clues,question)['answer']==expected

@pytest.mark.parametrize('question,answer,quantifier',[
    ('Can Zed be first?','true','possible'),
    ('Could Luma be first?','false','possible'),
    ('Must Nori be first?','false','necessary'),
    ('Must Nori be before Luma?','true','necessary'),
    ('Does Zed have to be last?','false','necessary'),
    ('Is it possible that Zed is first?','true','possible'),
    ('Is it possible for Luma to be first?','false','possible'),
    ('Is Nori the first?','unknown','entailed'),
    ('Is Luma before Nori?','false','entailed'),
    ('Is Nori not before Luma?','false','entailed'),
    ('Is Nori before Luma?','true','entailed'),
])
def test_quantification_and_checkable_witnesses(question,answer,quantifier):
    result=ordering(BASE,question)
    assert result['answer']==answer
    assert result['quantifier']==quantifier
    assert result['valid_orders']==3
    for key in ('witness','counterexample'):
        if result[key]:
            assert set(result[key])=={'nori','luma','zed'}
            assert result[key].index('nori')<result[key].index('luma')
    if answer=='unknown':assert result['witness'] and result['counterexample']

@pytest.mark.parametrize('clue',[
    'Nori is before Luma unless it rains', 'Nori is probably before Luma',
    'Nori is before Luma and Zed is first', 'Nori is first or second',
    'Nori is not only before Luma', 'Nori is before Luma sometimes',
    'Nori might be first', 'Nori is ninth', 'Nori is first and happy',
    'X is before Nori', 'Nori is before Lum',
])
def test_never_drop_unsupported_qualifiers(clue):
    with pytest.raises(Unparsed):ordering('Items: Nori, Luma, Zed. '+clue,'Who is first?')
    answer=Reasoner().respond('Facts: Items: Nori, Luma, Zed. '+clue+'. Who is first?')
    assert answer['route']=='chat/reasoning-unsupported'


def test_independent_five_item_model_oracle_and_renaming():
    # This independent enumeration states the constraints directly with integer
    # positions, without calling the parser or its predicate evaluator.
    expected={p for p in itertools.permutations(range(5))
              if p[0]+1==p[1] and abs(p[2]-p[4])!=1
              and min(p[0],p[3])<p[2]<max(p[0],p[3]) and p[4]!=0}
    assert expected
    for names in [('a','b','c','d','e'),('agent_9','agent9','river stone','cedar','elm')]:
        a,b,c,d,e=names
        clues=[f'{a} is immediately before {b}',f'{c} is not next to {e}',
               f'{c} is between {a} and {d}',f'{e} is not first']
        for rows in (clues,clues[::-1]):
            context='Items: '+', '.join(names)+'. '+'. '.join(rows)+'.'
            _,actual=solve_order(context)
            positions={tuple(order.index(n) for n in names) for order in actual}
            assert positions==expected
            for i,name in enumerate(names):
                for slot,word in enumerate(('first','second','third','fourth','fifth')):
                    possible=any(p[i]==slot for p in expected)
                    necessary=all(p[i]==slot for p in expected)
                    assert ordering(context,f'Can {name} be {word}?')['answer']==str(possible).lower()
                    assert ordering(context,f'Must {name} be {word}?')['answer']==str(necessary).lower()


def test_limits_unknown_and_conflict_are_distinct():
    assert ordering('Items: A, B, C, D, E, F, G, H.','Who is first?')['valid_orders']==40320
    for context in ('Items: A, A.','Items: A, B, C, D, E, F, G, H, I.'):
        with pytest.raises(Unparsed):ordering(context,'Who is first?')
    with pytest.raises(Unparsed):ordering('Items: A, B.','Who is in the middle?')
    result=ordering(BASE,'Who is first?')
    assert result['answer']=='unknown' and len(result['examples'])==2
    assert result['examples'][0][0]!=result['examples'][1][0]


def test_no_vacuous_truth_from_inconsistent_order():
    result=ordering(BASE+' Luma is before Nori.','Must Zed be first?')
    assert result['answer']=='conflicting' and result['valid_orders']==0


def test_conversation_add_explain_and_isolation():
    engine=Reasoner(); history=[]
    def ask(text):
        history.append(dict(role='user',content=text))
        answer=engine.respond(text,history)
        history.append(dict(role='assistant',content=answer['response']))
        return answer
    first=ask(BASE+' Must Nori be first?')
    assert first['reasoning']['answer']=='false'
    assert 'not required' in first['response'] and 'Example making it false:' in first['response']
    assert ask('Why?')['reasoning']['answer']=='false'
    assert ask('Who is last?')['reasoning']['answer']=='unknown'
    assert ask('Add: Zed is last.')['route']=='chat/reasoning-context'
    assert ask('Who is first?')['reasoning']['answer']=='nori'
    assert not chat_scope('Who is first?',[dict(role='user',content='Who is first?')])
    assert engine.respond('Who is first?') is None
    ask('Forget the premises')
    assert not chat_scope('Who is first?',history+[dict(role='user',content='Who is first?')])


def test_plain_chat_and_unrelated_topics_are_not_owned():
    for text in ('Hello','What is gravity?','I ordered books yesterday','Fix my grammar: he go home'):
        assert not chat_scope(text,[dict(role='user',content=text)])
    answer=Reasoner().respond(BASE+' Can Zed be first?')
    history=[dict(role='user',content=BASE+' Can Zed be first?'),dict(role='assistant',content=answer['response'])]
    assert not chat_scope('What is gravity?',history+[dict(role='user',content='What is gravity?')])


def test_no_cross_dimension_inference():
    for context,query in [
        ('Items: Nori, Luma. Nori is older than Luma.','Is Nori more expensive than Luma?'),
        ('Items: Nori, Luma. Nori is before Luma.','Who is oldest?'),
        ('Items: Nori, Luma. Nori is above Luma. Nori is older than Luma.','Who is first?'),
    ]:
        with pytest.raises(Unparsed):ordering(context,query)
    assert ordering('Items: Oldest Oak, Elm. Oldest Oak is before Elm.','Who is first?')['answer']=='oldest oak'
    assert ordering('Items: Nori, Luma. Nori is older than Luma.','Who is youngest?')['answer']=='luma'


def test_bare_item_list_can_be_saved_then_queried():
    engine=Reasoner()
    text='Items: Nori, Luma. Nori is before Luma.'
    answer=engine.respond(text)
    assert answer['route']=='chat/reasoning-context'
    history=[dict(role='user',content=text),dict(role='assistant',content=answer['response']),
             dict(role='user',content='Who is first?')]
    assert engine.respond('Who is first?',history)['reasoning']['answer']=='nori'
