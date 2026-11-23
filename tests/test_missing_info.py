"""missing_info.py: questions the stated facts can't answer (2026-11-22). Development problems."""
import pytest

from cael_unified import missing_info as X


def kind(text):
    r = X.respond([dict(role='user', content=text)])
    return r and r['route'].rsplit('-', 1)[-1] if r else None


@pytest.mark.parametrize('text,route', [
    ('My brother is 3 years older than me. How old is he?', 'chat/missing-info-comparisons-only'),
    ('A coin will be tossed tomorrow. What result can I write down now for certain?', 'chat/missing-info-not-decided'),
    ('The note was unsigned. Who wrote it?', 'chat/missing-info-hidden'),
    ('I drew a triangle. Which of its four corners is biggest?', 'chat/missing-info-shape-count'),
])
def test_flags(text, route):
    r = X.respond([dict(role='user', content=text)])
    assert r and r['route'] == route


@pytest.mark.parametrize('text', [
    'Sam is 12. Ann is 3 years older than Sam. How old is Ann?',
    'My train takes 40 minutes, which is 10 minutes longer than the bus. How long does the bus take?',
    'I drew a square. What are its four corners called?',
    'How old is the Eiffel Tower?',
])
def test_silent(text):
    assert X.respond([dict(role='user', content=text)]) is None
