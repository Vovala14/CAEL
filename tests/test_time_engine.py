"""time_engine.py: general clock and calendar reasoning (2026-11-22). Development problems written for this engine."""
import pytest

from cael_unified import time_engine as T


def head(*turns):
    r = T.respond([dict(role='user', content=t) for t in turns])
    return r and r['response'].split('**')[1].rstrip('.')


@pytest.mark.parametrize('turns,want', [
    (('Buses leave the depot at 06:50 and then every 25 minutes. I get to the depot at 07:52 and need 2 minutes to buy a ticket. Which bus is the first I can catch?',), 'The 08:05'),
    (('The ferry departs at 9:15 am and every 40 minutes after that. I will be at the pier at 10:20 am.', 'What is the next ferry I can take?'), 'The 10:35 am'),
    (('The film starts at 19:30. It takes me 25 minutes to drive and 10 minutes to park. Buses into town arrive at 18:40, 18:55 and 19:05. What is the latest bus I can take?',), 'The 18:55'),
    (('My shift ends at 17:00, and the walk to the platform takes 6 minutes. Trains leave at 16:58, 17:04 and 17:20. Which is the earliest train I can catch?',), 'The 17:20'),
    (('I am free from 09:00 to 11:00 UTC. My colleague is free from 12:30 to 14:00 on a clock three hours ahead of UTC.', 'How long can we meet together?'), '90 minutes'),
    (('Ola wrote 09:45 in local time, two hours ahead of UTC. Ben wrote 07:45 UTC. How far apart are the times?',), 'They are the same moment: 0 minutes apart'),
    (('In March 2024 the first Tuesday was March 5. Our club meets on the first and third Tuesdays.', 'What is the date of the later meeting?'), 'Tuesday, March 19, 2024'),
    (('I dropped off my laptop on Friday 3 May 2024. It will be ready by the end of the third working day after drop-off. The shop is open Monday to Friday.', 'Which date?'), 'Wednesday 8 May 2024'),
    (('On 10 July 2015 my two nephews, who are twins, were both six.', 'What will their combined age be on 10 July 2030?'), '42'),
    (('My daughter was four on 2 March 2020. How old was she on 2 March 2026?',), '10'),
])
def test_time(turns, want):
    assert head(*turns) == want


@pytest.mark.parametrize('turns', [
    ('What time is it in Tokyo?',),
    ('I left at 08:00 and arrived at 09:30. Was the train late?',),
])
def test_silent(turns):
    assert T.respond([dict(role='user', content=t) for t in turns]) is None
