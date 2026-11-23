"""scoped_facts.py: changing information with scope, corrections and withdrawals (2026-11-22). Development problems."""
import pytest

from cael_unified import scoped_facts as X


def head(*turns):
    r = X.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('The rota lists Amy as the host. An update replaces Amy with Raj for the evening shift only.', 'Who hosts the evening shift?'), 'Raj'),
    (('The rota lists Amy as the host. An update replaces Amy with Raj for the evening shift only.', 'Who hosts the morning shift?'), 'Amy'),
    (('The flyer says to use the North Gate. Later a guard texts: use the East Gate today.',
      'Another text from the guard: that message was for the delivery vans, not your school group. Which gate should our school group use?'), 'North Gate'),
    (('The gym timetable says it opens at six. A newer sign says nine, but only for Sundays.', 'Today is Sunday. When does it open today?'), 'nine'),
    (('The gym timetable says it opens at six. A newer sign says nine, but only for Sundays.', 'Today is a Monday. When does it open today?'), 'six'),
])
def test_scoped(turns, want):
    assert head(*turns) == want


def test_silent():
    assert X.respond([dict(role='user', content='Who wrote Hamlet?')]) is None
    assert X.respond([dict(role='user', content='The shop opens at nine. When does it open?')]) is None
