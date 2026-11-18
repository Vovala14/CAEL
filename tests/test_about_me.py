"""about_me: true answers about CAEL and the clock, and no capture of ordinary requests."""
import datetime as dt

from cael_unified import about_me


def ask(text):
    return about_me.respond([dict(role='user', content=text)])


def test_self_questions():
    for q, kind in [('Do you have access to the internet?', 'internet'), ('Can you browse the web?', 'internet'), ('Are you online?', 'internet'),
                    ('What time is it?', 'time'), ("What's the date today?", 'date'), ('What time is it in Tokyo?', 'city-time'),
                    ('Do you remember what I told you yesterday?', 'memory'), ('Are you an AI?', 'what'), ('Who made you?', 'who'),
                    ('Who are you?', 'who'), ('Can you see images?', 'see')]:
        assert ask(q)['route'] == 'chat/about-' + kind, q
    assert 'not a neural network' in ask('Are you ChatGPT?')['response']


def test_ordinary_requests_are_not_captured():
    for q in ['Can you search for the best pizza in Rome?', 'What time does the bank open?', 'Who are you voting for in the election?',
              'What time is it when the 9:40 train arrives after 2 hours?', 'Do you know a good recipe for internet cafe snacks?',
              'Are you able to help me write an email?']:
        assert ask(q) is None, q


def test_city_offsets_and_summer_time():
    winter = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)
    summer = dt.datetime(2026, 7, 15, 12, 0, tzinfo=dt.timezone.utc)
    assert about_me.city_time('new york', winter)[1] == -5 and about_me.city_time('new york', summer)[1] == -4
    assert about_me.city_time('london', summer)[1] == 1 and about_me.city_time('sydney', winter)[1] == 11
    assert about_me.city_time('delhi', summer)[1] == 5.5 and about_me.city_time('tokyo', summer)[1] == 9
