"""Checks for chat_skills.py (exact skills over the conversation). Run: python test_chat_skills.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_unified import chat_skills as S


def convo(*turns, replies=None):
    m = []
    for i, t in enumerate(turns):
        m.append(dict(role='user', content=t))
        if i < len(turns) - 1:
            m.append(dict(role='assistant', content=(replies or {}).get(i, 'OK.')))
    return m


def said(*turns, **k):
    c = convo(*turns, **k)
    r = S.respond(c) or S.respond(c, late=True)
    return r['response'] if r else None


def check():
    # quantities, transfers, totals; opinions and general questions are left alone
    assert '**5** more' in said("Box A has 12 apples and box B has 7. How many more apples are in box A?")
    r = said("Box A has 12 apples and box B has 7.", "If I move 3 apples from A to B, how many are in each box?")
    assert '**9**' in r and '**10**' in r, r
    assert '**24**' in said("Tom has 15 marbles and Sara has 9 marbles. How many do they have altogether?")
    assert '**11**' in said("Tom has 15 marbles. He gives 4 to Sara. How many does Tom have now?")
    assert '**6** fewer' in said("Jar X has 20 cookies and jar Y has 26. How many fewer cookies are in jar X?")
    assert '**7**' in said("I have 10 euros. I spend 3. How many do I have left?")
    for q in ("How many kids is a good number for a party at that age?", "We have 3 kids. How many more do you think we should have?",
              "What is the capital of France?", "How many legs does a spider have?", "I love pizza."):
        assert said(q) is None, q
    # rates and what-ifs
    assert '**15 days**' in said("I read 18 pages a day. How many days to finish a 270-page book?")
    assert '**9 days**' in said("I read 18 pages a day. How many days to finish a 270-page book?", "What if I read 30 pages a day instead?")
    assert '**8 days**' in said("I walk 4 km a day. How many days to walk 30 km?")
    assert '**3 hours**' in said("A car drives 240 km at 80 km/h. How long does it take?")
    assert '**60 euros**' in said("A shirt costs 40 euros and is 25% off. What do I pay?", "And if I buy two of them?",
                                  replies={0: 'The sale price is **30**.'})
    # clock times
    assert '**11:25**' in said("My train leaves at 08:50 and the trip takes 2 hours 35 minutes. When do I arrive?")
    assert '**11:45**' in said("My train leaves at 08:50 and the trip takes 2 hours 35 minutes. When do I arrive?",
                               "It's delayed by 20 minutes. What's the new arrival time?")
    assert '**9:55 pm**' in said("The film starts at 7:40 pm and lasts 2 hours 15 minutes. When does it end?")
    assert '**16:05**' in said("My flight departs at 14:40 and takes 1 hour 25 minutes. What time do I land?")
    # syllogisms, both directions
    assert '**Spain**' in said("All my cousins live in Spain. Marta is my cousin. Where does Marta live?")
    assert said("All my cousins live in Spain. Marta is my cousin. Where does Marta live?",
                "Does everyone who lives in Spain have to be my cousin?").startswith('No.')
    assert said("Every student in the club plays chess. Leo is a student in the club. Does Leo play chess?").startswith('Yes')
    # schedules with cancellations
    r = said("I have yoga on Tuesday and Thursday, and swimming on Saturday.", "Yoga on Thursday is cancelled this week.",
             "Which days do I have something this week?")
    assert '**Tuesday**' in r and '**Saturday**' in r and 'cancelled' in r, r
    assert "you're free" in said("I have piano on Monday and tennis on Wednesday and Friday.", "Tennis on Friday is cancelled.", "Am I free on Friday?")
    # values the user changed
    assert '**9032**' in said("My locker code is 4417.", "Actually I changed it to 9032 this morning.", "What's my locker code now?")
    assert '**green77**' in said("My wifi password is blue42.", "I changed it to green77.", "What's my wifi password?")
    # notes and rewrites
    r = said("Write a two-line thank-you note to my neighbour for watering my plants.")
    assert 'watering my plants' in r and r.count('\n') == 3, r
    assert 'casual' in said("Write a two-line thank-you note to my neighbour for watering my plants.", "Make it a bit more casual.")
    assert 'Sam' in said("Write a short birthday message for my friend Sam.")
    # persona reason, person recall, feelings, plans, missing ingredient
    assert 'colours' in said("What's your favourite season?", "Why that one?",
                             replies={0: "My favourite season? I'd say autumn. I can't experience it the way you do, but it's the one I most like talking about. What's yours?"})
    r = said("My daughter Mia turns six next Saturday.", "She's obsessed with dinosaurs.", "Any ideas?", "What's my daughter's name and what is she into?")
    assert 'Mia' in r and 'dinosaurs' in r, r
    assert 'stay in touch' in said("My best friend is moving abroad next month and I'm really sad about it.")
    assert 'primary school' in said("My best friend is moving abroad next month and I'm really sad about it.", "We've been friends since primary school.")
    r = said("How do I get rid of the smell of onions on my hands?", "I don't have any lemon at home.",
             replies={0: "Rub your hands with salt and rinse.\n\nWash your hands with vinegar or lemon juice. Lemon juice contains citric acid."})
    assert 'vinegar' in r and 'lemon juice contains' not in r.lower(), r
    assert '10 hours' in said("I'm thinking of adopting a cat. I live in a small studio apartment.", "I also work long hours, usually 9 to 7.")
    print('chat_skills: all checks passed')


import unittest


class ChatSkillsTest(unittest.TestCase):
    def test_all(self):
        check()


if __name__ == '__main__':
    unittest.main()
