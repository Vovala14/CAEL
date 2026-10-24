"""Unknown intermediate facts and incomplete witness sets must stay unresolved."""
import pytest
from cael_unified.reasoning import Reasoner
from cael_unified.reasoning_compose import solve
from cael_unified.reasoning_logic import Unparsed

@pytest.mark.parametrize('context,question,answer',[
 ('Nori grabbed the key.','Who is in the garden?','unknown'),
 ('Nori went to the garden. Luma grabbed the key.','Who is in the garden?','unknown'),
 ('Nori went to the garden. Luma went to the office.','Who is in the garden?','Nori'),
 ('Nori went to the office. Luma went to the office.','Who is in the garden?','nobody'),
 ('Nori went to the garden. Luma went to the garden.','Who is in the garden?','Nori and Luma'),
 ('Nori went to the garden.','Where is the person who has the key?','unknown'),
 ('Nori grabbed the key.','Where is the person who has the key?','unknown'),
 ('Nori went to the garden. Nori grabbed the key.','Where is the person who has the key?','garden'),
 ('Nori went to the garden. Nori grabbed the key. Luma grabbed the ball.',
  'What is the person in the garden carrying?','unknown'),
 ('Nori went to the garden. Nori grabbed the key. Luma went to the office.',
  'What is the person in the garden carrying?','key'),
])
def test_composed_unknown_is_not_absence_or_parse_failure(context,question,answer):
    result=Reasoner().respond('Facts: '+context+' '+question)
    assert result['route']=='chat/reasoning-state'
    assert result['reasoning']['answer']==answer
    assert result['reasoning']['chain']
    assert result['reasoning']['internet_used'] is False
    if answer=='nobody':assert result['response'].startswith('None of the tracked people')


def test_partial_membership_is_labeled_incomplete():
    engine=Reasoner()
    text='Facts: Nori went to the garden. Luma grabbed the key. Who is in the garden?'
    result=engine.respond(text)
    assert result['reasoning']['known_matches']==['Nori']
    assert result['reasoning']['unresolved_people']==['Luma']
    assert 'Nori is in the garden.' in result['response']
    assert 'do not determine' in result['response']
    history=[dict(role='user',content=text),dict(role='assistant',content=result['response']),
             dict(role='user',content='Why?')]
    assert engine.respond('Why?',history)['reasoning']['answer']=='unknown'


def test_unsupported_story_is_not_silently_filtered():
    result=Reasoner().respond('Facts: Nori went to the garden. Luma teleported somewhere. Who is in the garden?')
    assert result['route']=='chat/reasoning-unsupported'


def test_contradictory_subanswer_is_not_a_witness():
    def conflicting(context,question):return dict(answer='conflicting',support=[1],family='state')
    result=solve(conflicting,'Nori went to the garden.','Where is the person who has the key?')
    assert result['answer']=='conflicting' and result['unresolved_step']=='Who has the key?'


def test_failed_subparse_is_not_absence():
    def unsupported(context,question):raise Unparsed('unsupported story')
    with pytest.raises(Unparsed):solve(unsupported,'Nori went to the garden.','Who is in the garden?')
