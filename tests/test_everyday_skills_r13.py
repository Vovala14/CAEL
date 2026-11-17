"""Everyday skills added after round 12: saving rates, discounts, clock time for two players, cost per year, existential
logic questions, updates passed on by someone, recall of age / room / what was wrong, thank-you notes, and the
Planner's search plan for a told problem. Inputs here are written for the tests, not taken from any final set."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('CAEL_WEB_SEARCH', '0')

from cael_unified import calc_agent, solve_logic, recall_agent, writer_agent, empath, team, context_reasoner, chat_memory


def chat(*turns, replies=None):
    out = []
    for i, t in enumerate(turns):
        out.append(dict(role='user', content=t))
        if i < len(turns) - 1:
            out.append(dict(role='assistant', content=(replies or {}).get(i, 'Okay.')))
    return out


def test_saving_rate_over_a_year_and_weeks_to_a_target():
    m = chat("My daughter gets $8 a week and puts 25% of it in her piggy bank. How much does she save in a year?")
    r = calc_agent.respond(m)
    assert r and '**$104**' in r['response']
    m = chat("My daughter gets $8 a week and puts 25% of it in her piggy bank. How much does she save in a year?",
             "She wants a bike that costs $50. How many weeks will it take her to save for it?", replies={0: r['response']})
    r2 = calc_agent.respond(m)
    assert r2 and '**25 weeks**' in r2['response']


def test_discount_on_the_previous_total():
    m = chat("Piano lessons cost $30 each and I want 2 a week for 5 weeks. What will that cost?",
             "With a 20% discount, what's the total?", replies={0: '**$300**.'})
    r = calc_agent.respond(m)
    assert r and '**$240**' in r['response']


def test_each_player_clock_and_a_break_after():
    m = chat("A game starts at 2:15 pm and each player has 30 minutes on the clock. What's the latest it can finish?")
    r = calc_agent.respond(m)
    assert r and '**3:15 pm**' in r['response']
    m = chat("A game starts at 2:15 pm and each player has 30 minutes on the clock. What's the latest it can finish?",
             "If there's a 10-minute break, when is the latest it can finish?", replies={0: r['response']})
    r2 = calc_agent.respond(m)
    assert r2 and '**3:25 pm**' in r2['response']


def test_cost_per_year_and_a_changed_lifetime():
    first = "A wool coat costs $200 and lasts about 10 years. A cheap coat costs $60 and lasts about 2 years. Which is cheaper per year?"
    r = calc_agent.respond(chat(first))
    assert r and 'wool coat is cheaper per year' in r['response'].lower()
    r2 = calc_agent.respond(chat(first, "And if the wool coat only lasts 5 years?", replies={0: r['response']}))
    assert r2 and 'cheap coat is cheaper per year' in r2['response'].lower()


def test_is_there_question_follows_from_all_and_none():
    text = "All the cups on the shelf are glass. None of the glass cups are safe in the microwave. Is there a cup on the shelf that is safe in the microwave?"
    assert solve_logic.solve(text).startswith('**No.**')


def test_update_passed_on_by_someone_replaces_the_old_time():
    m = chat("The parents' evening is on Monday at 5 pm.", "The school just texted to say it's now on Wednesday at 7 pm.", "When is the parents' evening?")
    r = context_reasoner.answer(m)
    assert r and 'Wednesday at 7 pm' in r['response'] and 'conflicting' not in r['response']


def test_recall_age_room_and_what_was_wrong():
    m = chat("Our three-year-old, Sam, keeps waking at night.", "What helps?", "How old did I say Sam is?")
    assert 'three years old' in recall_agent.respond(m)['response']
    m = chat("The radiator in our kitchen is really noisy.", "What can I do?", "Which room did I say has the noisy radiator?")
    assert '**kitchen**' in recall_agent.respond(m)['response']
    m = chat("My garden shears are really stiff.", "Can I oil them?", "What did I say was wrong with my shears?")
    assert 'really stiff' in recall_agent.respond(m)['response']


def test_advice_question_is_not_answered_as_recall():
    m = chat("My boots are really muddy. I've never cleaned suede before.", "Is a brush any good?", "How often should I clean them?")
    assert chat_memory.pronoun_recall(m) is None
    assert context_reasoner.answer(m) is None


def test_thank_you_note_and_a_warmer_version():
    req = "Can you write a short thank-you note to my son's coach for helping him get ready for his first match?"
    r = writer_agent.respond(chat(req))
    assert r and 'Thank you so much for helping our son get ready for his first match' in r['response'] and '-you note' not in r['response']
    r2 = writer_agent.respond(chat(req, "Can you make it a bit warmer?", replies={0: r['response']}))
    assert r2 and 'warmer version' in r2['response'] and 'he comes home' in r2['response']


def test_let_down_is_not_feeling_down():
    r = empath.respond(chat("We didn't get the nursery place we wanted.", "I feel like I've let her down."))
    assert r and "isn't something you did to her" in r['response']


def test_search_plan_names_the_thing_and_the_problem():
    b = team.Board(chat("The door in our hallway is really squeaky.", "What can I do about it cheaply?"))
    team.plan(b)
    assert b.search['need'] == ['door'] and 'squeaky' in b.search['want']
    b = team.Board(chat("My partner snores so loudly that I can't sleep.", "What can I do?"))
    team.plan(b)
    assert b.search['need'] == ['snores']


def test_percent_cut_saving_and_what_is_left():
    q = "Our electricity bill is $90 a month. If we cut it by 20%, how much would we save in a year?"
    r = calc_agent.respond(chat(q))
    assert r and '**$216**' in r['response']
    r2 = calc_agent.respond(chat(q, "And how much would we be paying each month then?", replies={0: r['response']}))
    assert r2 and '**$72**' in r2['response']


def test_split_only_the_part_named():
    q = "A guitar costs $120 and lessons are $25 each. How much for the guitar and 4 lessons?"
    r = calc_agent.respond(chat(q, "If I split the lessons with my brother, how much do I pay in total?", replies={0: '**$220**.'}))
    assert r and '**$170**' in r['response']


def test_recurring_cost_named_between_amount_and_period():
    q = "One printer costs $60 and needs a $20 cartridge every year. Another costs $110 and comes with ink for 5 years. Which is cheaper over 5 years?"
    r = calc_agent.respond(chat(q))
    assert r and 'second is cheaper' in r['response'].lower() and '$160' in r['response']


def test_reference_letter_and_formal_version():
    req = "Can you write a short reference for our cleaner, Maria, who has worked for us for three years?"
    r = writer_agent.respond(chat(req))
    assert r and 'Maria, who has worked for us for three years' in r['response']
    r2 = writer_agent.respond(chat(req, "Can you make it more formal?", replies={0: r['response']}))
    assert r2 and 'To whom it may concern' in r2['response'] and 'Yours faithfully' in r2['response']


def test_nerves_get_reassurance_and_tips():
    assert 'normal' in empath.respond(chat("I have an interview on Monday and I'm dreading it."))['response']
    r = empath.respond(chat("I have an interview on Monday and I'm dreading it.", "My hands shake when I'm nervous."))
    assert 'breathe out slowly' in r['response']


def test_replies_about_another_thing_are_not_applicable():
    from cael_unified.applicability import conflict
    assert conflict('Our smoke alarm keeps beeping even with a new battery.', 'Lower the screen brightness and turn off Bluetooth.')
    assert conflict('My rabbit seems bored. Could he be lonely?', 'Try a museum or a picnic.')
    assert conflict('My friend is vegan and coming for lunch.', 'A chicken tray bake is easy.')
    assert conflict('My phone battery drains fast.', 'Lower the screen brightness.') is None


def test_advisor_for_vegetarian_guest_and_smoke_alarm():
    from cael_unified import advice_library
    r = advice_library.respond(chat("My sister is vegetarian and coming for dinner.", "What main course could I make?"))
    assert r and 'lasagne' in r['response'] and 'chicken' not in r['response'].lower()
    r = advice_library.respond(chat("The smoke alarm in the hall keeps beeping.", "I put a new battery in and it still beeps. What else could it be?"))
    assert r and 'resetting' in r['response']


def test_search_plan_finds_the_thing_behind_an_adjective():
    b = team.Board(chat("Our garden gate has been squeaking for months.", "Can I fix it myself?"))
    team.plan(b)
    assert b.search['need'] == ['gate']
