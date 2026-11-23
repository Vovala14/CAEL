"""Fixes after the owner's 11-question check (2026-11-22, test-informed). The cases here are new variants written after
the check, not the check questions themselves."""
from cael_unified import consistency, everyday_reasoning, followups, state_tracker, story_math, time_engine


def u(*turns):
    return [dict(role='user', content=t) for t in turns]


def head(r):
    return r and r['response'].split('**')[1]


def test_linear_equation_with_coefficient():
    assert everyday_reasoning.linear_equation('Solve 5y + 4 = 29, then multiply the result by 3.')['response'].startswith('**y = 5**')
    assert everyday_reasoning.linear_equation('Solve 2(x + 1) = x + 9')['response'].startswith('**x = 7**')


def test_count_story():
    assert head(story_math.respond(u('I have 4 crates with 10 eggs each, and 7 eggs broke. How many eggs are left?'))) == '33 eggs left.'
    assert head(story_math.respond(u("Starting with two 24-can trays, eleven cans got used up. What's the remaining count?"))) == '37 cans left.'


def test_duration_between_clocks():
    r = time_engine.respond(u('If the bus departs at 09:40 and arrives at 11:15, how many minutes is the ride?'))
    assert head(r) == 'The ride took 95 minutes'


def test_counts_in_places():
    r = state_tracker.respond(u('There are 10 books on the shelf and 3 on the desk.', 'I moved 2 books from the shelf to the desk, then gave away 1 from the desk.',
                                'How many books are on the desk now, and how many are on the shelf?'))
    assert head(r) == '4 on the desk and 8 on the shelf.'


def test_hand_over():
    r = state_tracker.respond(u('Lena lent Omar her old bike because his had a flat tyre.', 'Who has the working bike now, and whose bike is broken?'))
    assert head(r) == 'Omar has the working bike'


def test_consistency():
    assert head(consistency.respond(u('Every door on floor 2 is locked. Door 2C is on floor 2 and is wide open. Is that consistent?'))) == "No, it isn't consistent."
    assert head(consistency.respond(u('All lamps in the hall are off. Lamp 3 is in the hall and is off. Is this consistent?'))) == "Yes, that's consistent."


def test_vent_listens_only():
    assert followups.vent(u("I need to vent. Please don't give me advice and don't ask questions."))['route'] == 'chat/followup-vent'
    got = followups.listen_only(u("I need to vent. Don't give me advice.", "My landlord raised the rent and I'm so angry."),
                                dict(route='chat/advice-schema', response='Try this:\n1. Talk to them.\n2. Check your contract.'))
    assert '?' not in got['response'] and 'Talk to them' not in got['response']


def test_groups_with_an_extra_event():
    assert head(story_math.respond(u('Mira has 4 boxes with 6 apples each. Mira eats 3 apples. How many apples does Mira have?'))) == '21 apples left.'


def test_second_check_variants():
    # 2026-11-23, new variants written after the owner's second check
    assert head(state_tracker.respond(u('A depot holds 30 crates in Hall 1 and 12 crates in Hall 2.',
                                        'A crew moves 8 crates from Hall 1 to Hall 2, then a van collects 5 crates from Hall 2.',
                                        'How many crates are in Hall 1 and Hall 2 now?'))) == '22 in Hall 1 and 15 in Hall 2.'
    assert head(story_math.respond(u('Out of five 12-egg cartons, nineteen eggs were used. What is the remaining number of eggs?'))) == '41 eggs left.'
    assert head(state_tracker.respond(u('Mia gave her old phone to Tom because his cracked.', 'Who has a working phone, and whose phone is broken?'))) == 'Tom has the working phone'
    assert head(consistency.respond(u('Every jar on the top shelf is sealed. Jar J-2 is on the top shelf and is unsealed. Is this consistent?'))) == "No, it isn't consistent."
    assert head(time_engine.respond(u('A ferry departs at 10:50 and docks at 13:05. How many minutes is the crossing?'))) == 'The crossing took 135 minutes'
    assert followups.next_message(u('Summarize my next message in one sentence.'))['response'] == 'Okay, send it.'
    assert followups.setting_ack(u('Scratch that, change my delivery address to Oak Road instead.'))['response'] == 'Updated: your delivery address is now Oak Road.'


def test_round3_variants():
    # 2026-11-23, new variants written after Gemini's round 3 (test-informed)
    assert head(state_tracker.respond(u('A pantry starts with 30 soup cans on the top shelf and 12 bean cans on the bottom shelf.',
                                        'Dad moves 9 soup cans to the bottom shelf, then a neighbour borrows 4 cans from the top shelf.',
                                        'How many cans are on the top shelf and the bottom shelf now?'))) == '17 on the top shelf and 21 on the bottom shelf.'
    assert head(state_tracker.respond(u('My work email is sam@acme.co.uk.', 'Change that please, make it sam.k@acme.com from now on.',
                                        'What is my work email?'))) == 'sam.k@acme.com.'
    assert followups.next_message(u('State the main problem in my next message in five words or fewer.',
                                    'The compressor in our shop freezer died last night, so all the ice cream melted.'))['response'] == 'Shop freezer compressor died.'
    assert followups.setting_ack(u('Update that, use jo@new.org as my billing email instead.'))['response'] == 'Updated: your billing email is now jo@new.org.'
    assert head(story_math.respond(u('A florist gets 6 buckets of 20 red roses each and crushes 17 roses while arranging. How many undamaged roses remain?'))) == '103 roses left.'
    assert head(state_tracker.respond(u('Ben passed Lia his scarf because hers got soaked in the rain.', 'Who has the dry scarf right now, and whose scarf is wet?'))) == 'Lia has the dry scarf'
    assert head(consistency.respond(u('Every vial in Fridge 2 is capped. Vial V-7 is in Fridge 2 and is currently uncapped. Is this consistent?'))) == "No, it isn't consistent."


from cael_unified import answer_guard


def test_guard_declines_replies_that_do_not_fit():
    m = u('Reply with exactly one JSON object with keys a and b.')
    assert answer_guard.check(m, dict(route='chat/problem-ask', response='That sounds annoying, but it is usually fixable.'))['route'] == 'chat/guard-unsure'
    m = u('Write a two-sentence text to a customer saying the order is late.')
    assert answer_guard.check(m, dict(route='chat/advice-schema', response='Measure by weight and preheat the oven.'))['route'] == 'chat/guard-unsure'
    m = u('Is there a valid seating plan for the three of them?')
    assert answer_guard.check(m, dict(route='chat/local-realtime', response="I can't access live data."))['route'] == 'chat/guard-unsure'
    m = u('In Python, what does `rows = [[0]] * 3` give after `rows[0].append(1)`?')
    assert answer_guard.check(m, dict(route='chat/python-topic-match', response="Use '\n'.join(items) and print(item).")) ['route'] == 'chat/guard-unsure'


def test_guard_keeps_replies_that_fit():
    good = dict(route='chat/advice', response="A dense loaf usually means it didn't rise enough: use lukewarm water and let the dough double.")
    assert answer_guard.check(u('My bread keeps coming out dense. What am I doing wrong?'), good) is good
    good = dict(route='chat/core-open', response='Fruit fly trap: put apple cider vinegar in a glass with a paper cone.')
    assert answer_guard.check(u('How can I get rid of fruit flies in my kitchen?'), good) is good
    good = dict(route='chat/support', response="That sounds like a lot to carry at once.")
    assert answer_guard.check(u('I feel stressed about my exams next week.'), good) is good


def test_time_shift_directions():
    assert head(time_engine.respond(u('Move my meeting with Sam back two hours. It is at 14:00. What new time should I put in the invite?'))).startswith('16:00')
    assert head(time_engine.respond(u('Move my meeting back two hours. It is at 14:00. What time?', 'I meant earlier. What time should I enter?'))) == '12:00.'
    assert head(time_engine.respond(u('Move the call forward an hour; it is at 3:30 pm. What is the new time?'))) == '2:30 pm'
