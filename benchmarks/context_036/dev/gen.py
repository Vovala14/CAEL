import json, random, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
from pools import *

R = random.Random(36036)
ch = lambda x: R.choice(x)
pk = lambda pool, n: R.sample(pool, n)


def ng(n):
    return [str(n), NW[n]] if n in NW else [str(n)]


def pr(name):
    return ("she", "her", "her") if name in FN else ("he", "him", "his")


def people(nf=0, nm=0):
    return pk(FN, nf) + pk(MN, nm)


def D(f, q, any_, none=None, feats=(), **kw):
    d = dict(f=f, q=q, any=any_, none=none or [], feats=list(feats))
    d.update(kw)
    return d


# ---------------- MEMORY ----------------
def m_loc():
    obj, obj2 = pk(OBJS, 2)
    loc, loc2 = pk(LOCS, 2)
    f = [ch([f"I left my {obj} in the {loc} again.", f"My {obj} ended up in the {loc}.", f"Just so you know, the {obj} is in the {loc} now."]),
         f"And my {obj2} is in the {loc2}."]
    return D(f, ch([f"Where did I put my {obj}?", f"Remind me, where's my {obj}?"]), [[loc]], [loc2])


def m_pet():
    sp = ch(SPECIES)
    pn, pn2 = pk(PETN, 2)
    A = ch(FN + MN)
    if R.random() < 0.5:
        f = [f"The {sp} was named {pn} by my daughter.", f"{A}'s {sp} is called {pn2}."]
        ft = ["passive"]
    else:
        f = [f"We adopted a {sp} last spring and called it {pn}.", f"{A} has a {sp} too, named {pn2}."]
        ft = []
    return D(f, f"What's my {sp} called?", [[pn]], [pn2], ft)


def m_city():
    A, B = people(1, 1)
    c1, c2 = pk(CITIES, 2)
    f = [ch([f"{A} moved to {c1} for work.", f"{A} got a job in {c1}, so that's where she is now."]), f"{B} is based in {c2}."]
    return D(f, ch([f"Where does {A} live?", f"In which city is {A} these days?"]), [[c1]], [c2])


def m_count():
    n, m = R.sample(range(3, 15), 2)
    f = [f"{n} people have said they're coming to dinner on my side.", f"We own {m} folding chairs."]
    return D(f, "How many guests should I cook for?", [ng(n)], [str(m)], ["paraphrase"])


def m_day():
    d, d2 = pk(DAYS, 2)
    f = [f"My dentist appointment is on {d}.", f"The haircut is booked for {d2}."]
    return D(f, ch(["What day is my teeth check-up?", "When do I see the dentist?"]), [[d]], [d2], ["paraphrase"])


def m_cleft():
    A, B = people(1, 1)
    food = ch(FOODS)
    f = [f"It was {A} who told me about the {food} place on the corner.", f"{B} only joined us for dessert."]
    return D(f, "Who recommended that restaurant to me?", [[A]], [B], ["unusual_structure", "paraphrase"])


def m_job():
    A, B = people(1, 1)
    j, j2 = pk(JOBS, 2)
    f = [f"{A} works as a {j}.", f"{B} is a {j2}, I think."]
    return D(f, f"What does {A} do for a living?", [[j]], [j2])


def m_door():
    c, c2 = pk(COLOURS, 2)
    f = [f"The front door got painted {c} last weekend.", f"The shutters are {c2}."]
    return D(f, "What shade is the front door?", [[c]], [c2], ["passive"])


def m_bday():
    A, B = people(1, 1)
    mo, mo2 = pk(MONTHS, 2)
    f = [f"{A}'s birthday falls in {mo}.", f"{B} was born in {mo2}."]
    return D(f, f"Which month should I remember for {A}'s birthday?", [[mo]], [mo2], ["paraphrase"])


def m_list():
    x, y, z = pk(PACK, 3)
    f = [f"For the trip I packed a {x}, a {y} and a {z}."]
    return D(f, "What was the second thing I packed?", [[y]], [], ["unusual_structure"])


def m_neg():
    dr = ch(DRINKS)
    f = [f"I don't drink coffee, only {dr}, and I never touch fizzy stuff."]
    return D(f, "What do I usually drink?", [[dr]], [], ["negation"])


def m_ind():
    A, B = people(0, 2)
    f = [f"My mom says the landlord's name is {A}.", f"The plumber is called {B}, apparently."]
    return D(f, "Who's the landlord, according to my mom?", [[A]], [B], ["indirect"])


def m_study():
    s = ch(SUBJECTS)
    c = ch(CITIES)
    f = [ch([f"I studied {s} at uni in {c}.", f"Back in {c} I did a degree in {s}."])]
    return D(f, "What was my degree in?", [[s]], [], ["paraphrase"])


def m_gift():
    A, B = people(2, 0)
    g, g2 = pk(GIFTS, 2)
    f = [f"I got {A} a {g} for her birthday.", f"{B} received a {g2} from me last year."]
    return D(f, f"What did {A} get from me?", [[g]], [g2])


def m_locker():
    n = R.randint(100, 899)
    f = [f"My locker at the gym is number {n}.", "The gym is on the second floor, by the way."]
    return D(f, "Which locker is mine?", [[str(n)]], [], [])


# ---------------- UPDATE ----------------
def u_meet():
    d1, d2 = pk(DAYS, 2)
    f = [f"The team meeting is on {d1} this week.", f"Heads up: the meeting was moved to {d2}."]
    return D(f, "What day is the team meeting now?", [[d2]], [d1], ["passive"])


def u_neg():
    A = ch(FN + MN)
    c1, c2 = pk(CITIES, 2)
    s, o, p = pr(A)
    f = [f"{A} lives in {c1}.", f"{A} isn't in {c1} anymore, {s} relocated to {c2}."]
    return D(f, f"Where is {A} based these days?", [[c2]], [c1], ["negation"])


def u_code():
    n1, n2 = R.sample(range(1000, 9999), 2)
    f = [f"My locker code is {n1}.", f"Correction: the code is {n2}, I mixed up the digits."]
    return D(f, "What's my locker code?", [[str(n2)]], [str(n1)])


def u_jobprev():
    j1, j2 = pk(JOBS, 2)
    f = [f"I work as a {j1}.", f"I switched careers a while ago, I'm a {j2} now."]
    return D(f, "Before the career change, what was my job?", [[j1]], [], [])


def u_price():
    n1 = R.randint(40, 90) * 10
    n2 = n1 - R.randint(2, 6) * 10
    f = [f"The sofa costs {n1} dollars.", f"The shop dropped it to {n2} this week."]
    return D(f, "How much is the sofa at the moment?", [[str(n2)]], [str(n1)])


def u_colour():
    c1, c2 = pk(COLOURS, 2)
    f = [f"We're painting the nursery {c1}.", f"We changed our minds, {c2} it is."]
    return D(f, "What colour is the nursery going to be?", [[c2]], [c1], ["unusual_structure"])


def u_rename():
    sp = ch(SPECIES)
    p1, p2 = pk(PETN, 2)
    f = [f"Our {sp} is called {p1}.", f"We've renamed the {sp}, it's {p2} now."]
    return D(f, f"What's the {sp}'s name nowadays?", [[p2]], [p1])


def u_time():
    t1, t2 = R.sample(range(5, 10), 2)
    f = [f"Dinner is booked for {t1} pm.", f"The reservation has been shifted to {t2} pm."]
    return D(f, "What time is the dinner reservation?", [ng(t2)], [str(t1)], ["passive"])


def u_travel():
    c = ch(CITIES)
    f = [f"I'm taking the train to {c}.", "Scratch that, the rail workers are striking, so I'll drive."]
    return D(f, f"How am I getting to {c}?", [["drive", "driving", "car"]], ["train"], ["negation", "paraphrase"])


def u_street():
    s1, s2 = pk(STREETS, 2)
    f = [f"I live on {s1} Street.", f"We moved last month, so it's {s2} Street for me now."]
    return D(f, "Which street do I live on?", [[s2]], [s1])


def u_cousins():
    n = R.randint(3, 9)
    f = [f"I have {n} cousins.", f"Oh, I forgot the new baby, so that makes {n+1} cousins really."]
    return D(f, "How many cousins do I have?", [ng(n + 1)], [str(n)])


def u_dessert():
    d1, d2 = pk(DESSERTS, 2)
    f = [f"My favourite dessert is {d1}.", f"Honestly it's {d2} these days, I've gone off {d1}."]
    return D(f, "What dessert do I like best now?", [[d2]], [], ["negation"])


def u_venue():
    v1, v2 = pk(VENUES, 2)
    f = [f"The party's at the {v1}.", f"Change of plan, it got moved to the {v2}."]
    return D(f, "Where was the party originally going to be?", [[v1]], [], ["passive"])


def u_chain():
    c1, c2, c3 = pk(CITIES, 3)
    f = [f"I'm flying to {c1} for the conference.", f"Actually the conference is in {c2}.", f"Final answer: it was relocated to {c3}."]
    return D(f, "Which city am I flying to?", [[c3]], [c1, c2], ["passive", "multistep"])


def u_deadline():
    d1, d2 = pk(DAYS, 2)
    f = [f"The report is due {d1}.", f"The deadline has been extended until {d2}."]
    return D(f, "When do I have to hand in the report?", [[d2]], [d1], ["passive", "paraphrase"])


# ---------------- REFERENCE ----------------
def r_sister():
    A, B = people(1, 1)
    c, c2 = pk(CITIES, 2)
    s = ch(SUBJECTS)
    f = [f"My sister {A} lives in {c}.", f"She teaches {s} at a secondary school.", f"My brother {B} lives in {c2}."]
    return D(f, "Which subject does my sister teach?", [[s]], [], [])


def r_bring():
    M, F = people(1, 1)
    x, y = pk(["apples", "lemons", "olives", "pears", "flowers", "oranges", "cheese"], 2)
    f = [f"I ran into {M} and {F} at the market.", f"He was carrying a bag of {x}; she had {y}."]
    return D(f, f"What was {F} carrying?", [[y]], [x])


def r_latter():
    i1, i2 = pk(["kettle", "toaster", "blender", "lamp", "heater", "monitor"], 2)
    f = [f"I'm choosing between a {i1} and a {i2}. The latter is cheaper."]
    return D(f, "Which of the two costs less?", [[i2]], [], ["paraphrase"])


def r_allergy():
    A = ch(MN)
    al = ch(["peanuts", "shellfish", "pollen", "cats", "wheat", "strawberries"])
    f = [f"I told you about my brother {A}, right? He's allergic to {al}."]
    return D(f, "What is my brother allergic to?", [[al]], [])


def r_place():
    c = ch(CITIES)
    feat = ch(["sauna", "piano", "hammocks", "courtyard", "telescope", "fireplace"])
    f = [f"We stayed at a tiny hostel in {c}.", f"I loved that place, it had a {feat}."]
    return D(f, "What did the hostel we stayed at have?", [[feat]], [])


def r_neigh():
    sn = ch(SURN)
    sp = ch(SPECIES)
    pn = ch(PETN)
    f = [f"The {sn}s next door have a {sp}.", f"They call him {pn}."]
    return D(f, f"What do my neighbours call their {sp}?", [[pn]], [], [])


def r_lent():
    F, M = people(1, 1)
    it = ch(["bike", "tent", "camera", "guitar", "drill", "stroller"])
    f = [ch([f"{F} lent {M} her {it} for the weekend.", f"For the weekend, {M} was lent a {it} by {F}, who said she wouldn't need it."])]
    return D(f, f"Whose {it} is {M} using?", [[F]], [], ["passive"])


def r_inlaw():
    A, B = people(1, 1)
    j = ch(JOBS)
    f = [f"My sister {A} married a man called {B}.", f"He works as a {j}."]
    return D(f, "What does my brother-in-law do?", [[j]], [], ["paraphrase"])


TITLES = [("Lanternfall", "Lanternfall"), ("The Salt Road", "Salt"), ("Quiet Engines", "Engines"), ("Marrow Hill", "Marrow"), ("Paper Tides", "Tides"), ("Kestrel Winter", "Kestrel")]


def r_titles():
    t = pk(TITLES, 3)
    f = [f"I read three books this month: {t[0][0]}, {t[1][0]} and {t[2][0]}.", "The second one was easily the best."]
    return D(f, "Which book did I like most?", [[t[1][1]]], [], ["unusual_structure"])


def r_pup():
    f = ["We got a puppy and a kitten last week.", "He chews everything in sight, she sleeps all day."]
    return D(f, "Which of the two sleeps all day?", [["kitten"]], [], [])


def r_former():
    A, B = people(1, 1)
    f = [f"I rang {A} and {B} about the lift.", "The former said yes, the latter didn't pick up."]
    return D(f, "Which of them agreed to give me a lift?", [[A]], [], ["paraphrase"])


def r_keys():
    d1, d2 = pk(["shed", "garage", "office", "cellar", "studio"], 2)
    f = [f"I carry two keys. One opens the {d1}, the other opens the {d2}."]
    return D(f, "What does the second key open?", [[d2]], [], ["unusual_structure"])


# ---------------- CONFLICT (genuine) ----------------
def c_wedding():
    m1, m2 = pk(MONTHS, 2)
    f = [f"The wedding is in {m1}, so I need a suit by then.", f"I'm so excited for the {m2} wedding!"]
    return D(f, "Which month is the wedding?", [[m1], [m2]], [], [], clarify=True)


def c_party():
    A, B = people(1, 1)
    t1, t2 = R.sample(range(5, 10), 2)
    f = [f"{A} told me the party kicks off at {t1} pm.", f"But {B} swears it starts at {t2} pm."]
    return D(f, "What time does the party start?", [ng(t1), ng(t2)], [], ["indirect"], clarify=True)


def c_car():
    c1, c2 = pk(COLOURS, 2)
    f = [f"I drive a {c1} hatchback.", f"I should wash my {c2} hatchback this weekend."]
    return D(f, "What colour is my hatchback?", [[c1], [c2]], [], [], clarify=True)


def c_city():
    A = ch(FN + MN)
    c1, c2 = pk(CITIES, 2)
    f = [f"{A} lives in {c1}.", f"I'll visit {A} in {c2} next month."]
    return D(f, f"Where does {A} live?", [[c1], [c2]], [], [], clarify=True)


def c_chairs():
    n1, n2 = R.sample(range(6, 20), 2)
    f = [f"We have {n1} chairs around the big table.", f"All {n2} chairs need to go back to the hall."]
    return D(f, "How many chairs do we have?", [ng(n1), ng(n2)], [], [], clarify=True)


def c_museum():
    A = ch(FN + MN)
    t1, t2 = R.sample(range(4, 9), 2)
    f = [f"The website says the museum closes at {t1} pm.", f"{A} says it closes at {t2} pm."]
    return D(f, "When does the museum close?", [ng(t1), ng(t2)], [], ["indirect"], clarify=True)


def c_dog():
    p1, p2 = pk(PETN, 2)
    f = [f"My dog {p1} hates baths.", f"{p2}, my dog, is scared of thunder."]
    return D(f, "What's my dog's name?", [[p1], [p2]], [], [], clarify=True)


def c_price():
    a, b = R.sample(range(20, 70), 2)
    f = [f"The tickets were {a} euros each.", f"I paid {b} euros per ticket in the end."]
    return D(f, "How much was one ticket?", [[str(a)], [str(b)]], [], [], clarify=True)


def c_manual():
    x1, x2 = R.sample(range(8, 40, 2), 2)
    f = [f"The manual says to use {x1} millimetre screws.", f"The video tutorial insists on {x2} millimetre screws."]
    return D(f, "What screw length should I use?", [ng(x1), ng(x2)], [], ["indirect"], clarify=True)


def c_job():
    j1, j2 = pk(JOBS, 2)
    f = [f"I'm a {j1} by trade.", f"As a {j2}, I'm always on my feet."]
    return D(f, "What do I do for work?", [[j1], [j2]], [], [], clarify=True)


# ---------------- CONTROLS ----------------
def k_corr():
    n1, n2 = R.sample(range(10, 99), 2)
    f = [f"My flat number is {n1}.", f"Sorry, I misspoke, it's actually {n2}."]
    return D(f, "What's my flat number?", [[str(n2)]], [str(n1)], [], no_clarify=True)


def k_people():
    A, B = people(1, 1)
    c1, c2 = pk(CITIES, 2)
    f = [f"{A} lives in {c1}.", f"{B} lives in {c2}."]
    return D(f, f"Where does {B} live?", [[c2]], [], [], no_clarify=True)


def k_objects():
    o1, o2 = pk(["bike", "scooter", "helmet", "backpack", "kayak"], 2)
    c1, c2 = pk(COLOURS, 2)
    f = [f"My {o1} is {c1}.", f"My {o2} is {c2}."]
    return D(f, f"What colour is my {o2}?", [[c2]], [], [], no_clarify=True)


def k_repeat():
    d = ch(DAYS)
    f = [f"The recital is on {d}.", f"Looking forward to the recital on {d}!"]
    return D(f, "What day is the recital?", [[d]], [], [], no_clarify=True)


def k_topics():
    A, B = people(1, 1)
    v = ch(VENUES)
    t = R.randint(5, 9)
    f = [f"{A} says the event is at the {v}.", f"{B} says it begins at {t} pm."]
    return D(f, "Where is the event?", [[v]], [], ["indirect"], no_clarify=True)


def k_usedto():
    c1, c2 = pk(CITIES, 2)
    f = [f"I used to live in {c1}.", f"Now I live in {c2}."]
    return D(f, "Where do I live at the moment?", [[c2]], [c1], [], no_clarify=True)


def k_pets():
    p1, p2 = pk(PETN, 2)
    f = [f"I have a dog named {p1} and a cat named {p2}."]
    return D(f, "What's my cat called?", [[p2]], [], ["unusual_structure"], no_clarify=True)


# ---------------- PLANNING ----------------
def _plan(extra_msgs=0):
    goal, gk, steps = ch(PLANS)
    f0 = f"I want to {goal}. The plan: first {steps[0][0]}, then {steps[1][0]}, then {steps[2][0]}, and finally {steps[3][0]}."
    return goal, gk, steps, f0


def p_next():
    goal, gk, st, f0 = _plan()
    f = [f0, f"Done: {st[0][0]}."]
    return D(f, ch(["What should I do next?", "What's the next thing on my list?"]), [[st[1][1]]], [], [])


def p_left():
    goal, gk, st, f0 = _plan()
    f = [f0, f"Finished: {st[0][0]}.", f"Also finished: {st[1][0]}."]
    return D(f, "What's still left to do?", [[st[2][1]], [st[3][1]]], [], ["multistep"])


def p_skip():
    goal, gk, st, f0 = _plan()
    f = [f0, f"Done with the first step.", f"I'm skipping the step where I {st[1][0]}, don't need it."]
    return D(f, "So what comes next?", [[st[2][1]]], [], ["negation", "multistep"])


def p_add():
    goal, gk, st, f0 = _plan()
    ex = ch(EXTRAS)
    f = [f0, f"Let's add one more step after the last one: {ex[0]}."]
    return D(f, "What's the very last step now?", [[ex[1]]], [], [])


def p_goal():
    goal, gk, st, f0 = _plan()
    f = [f0, f"Done: {st[0][0]}."]
    return D(f, "Remind me, what is this whole project for?", [[gk]], [], ["paraphrase"])


def p_budget():
    goal, gk, st, f0 = _plan()
    B = R.randint(4, 8) * 100
    a = R.randint(10, 30) * 10
    b = R.randint(10, 30) * 10
    B2 = R.randint(3, 8) * 100
    ok = (a + b) <= B2
    f = [f0, f"My budget for this is {B} euros.", f"Spent {a} on supplies so far.", f"And another {b} on a deposit.", f"The budget got cut to {B2} euros, sadly."]
    return D(f, "Am I still within budget?", [["yes" if ok else "no"]], [], ["multistep", "passive"])


def p_deadline():
    goal, gk, st, f0 = _plan()
    d1, d2 = pk(DAYS, 2)
    f = [f0, f"The deadline is {d1}.", f"The deadline's been pushed back to {d2}."]
    return D(f, "By when do I have to be finished?", [[d2]], [d1], ["passive", "paraphrase"])


def p_reorder():
    goal, gk, st, f0 = _plan()
    f = [f0, f"Actually, swap things around: do the step where I {st[2][0]} before the one where I {st[1][0]}."]
    return D(f, "What's the second step now?", [[st[2][1]]], [], ["multistep"])


def p_budchange():
    goal, gk, st, f0 = _plan()
    B1 = R.randint(3, 6) * 100
    B2 = B1 + R.randint(1, 4) * 100
    f = [f0, f"The budget is {B1} euros.", f"We raised the budget to {B2} euros."]
    return D(f, "What changed about the budget?", [[str(B1)], [str(B2)]], [], ["passive"])


def p_count():
    goal, gk, st, f0 = _plan()
    k = R.randint(1, 3)
    f = [f0] + [f"Done: {st[i][0]}." for i in range(k)]
    return D(f, "How many steps are still outstanding?", [ng(4 - k)], [], ["multistep"])


# ---------------- REASONING ----------------
def q_older():
    A, B = people(1, 1)
    a, b = R.sample(range(21, 60), 2)
    f = [f"{A} is {a} years old.", f"{B} just turned {b}."]
    return D(f, "Which of the two is older?", [[A if a > b else B]], [], ["multistep"])


def q_samecity():
    A, B, C, D4 = people(2, 2)
    c1, c2, c3 = pk(CITIES, 3)
    f = [f"{A} lives in {c1}.", f"{B} lives in {c2}.", f"{C} lives in {c1}.", f"{D4} lives in {c3}."]
    return D(f, f"Who lives in the same city as {A}?", [[C]], [], ["multistep"])


def q_sameday():
    d1, d2 = pk(DAYS, 2)
    th = pk(["bank call", "yoga class", "piano lesson", "car service", "eye test"], 2)
    f = [f"I have the dentist on {d1}.", f"The haircut is on {d2}.", f"I also have a {th[0]} on {d1}.", f"The {th[1]} is on {d2}"]
    f[3] = f[3] + "."
    return D(f, "What else do I have on the day of my dentist visit?", [[th[0].split()[0]]], [], ["multistep"])


def q_total():
    n, m = R.sample(range(2, 9), 2)
    a, b = pk(["dogs", "cats", "rabbits", "hens", "goldfish", "ducks"], 2)
    f = [f"We have {n} {a}.", f"Plus {m} {b} out back."]
    return D(f, "How many animals do we have altogether?", [ng(n + m)], [], ["multistep"])


def q_weekday():
    i = R.randrange(7)
    n = R.randint(2, 9)
    f = [f"Today is {DAYS[i]}.", f"The parcel will arrive in {n} days."]
    return D(f, "What weekday will the parcel get here?", [[DAYS[(i + n) % 7]]], [], ["multistep"])


def q_before():
    i = R.randrange(7)
    if R.random() < 0.5:
        f = [f"My exam is on {DAYS[i]}."]
        return D(f, "Which day is the day before my exam?", [[DAYS[(i - 1) % 7]]], [], ["multistep", "paraphrase"])
    f = [f"The market runs on {DAYS[i]}."]
    return D(f, "What day comes right after the market day?", [[DAYS[(i + 1) % 7]]], [], ["multistep", "paraphrase"])


def q_tall():
    A, B, C = pk(FN + MN, 3)
    if R.random() < 0.5:
        f = [f"{A} is taller than {B}.", f"{B} is taller than {C}."]
        return D(f, "Who is the shortest of the three?", [[C]], [], ["multistep"])
    f = [f"{B} is shorter than {A}.", f"{C} is shorter than {B}."]
    return D(f, "Who is the tallest of the three?", [[A]], [], ["multistep", "unusual_structure"])


def q_rule():
    A, B = people(1, 1)
    a, b = R.choice([(16, 21), (15, 19), (17, 24)])
    f = ["The climbing club only admits people aged 18 or over.", f"My cousin {A} is {a}.", f"My cousin {B} is {b}."]
    return D(f, "Which of my cousins can join the club?", [[B]], [], ["multistep", "paraphrase"])


def q_drive():
    A, B, C = people(1, 2)
    f = [f"Only {A} and {B} have a driving licence, {C} doesn't.", f"{B} is away on Friday."]
    return D(f, "Who could drive me on Friday?", [[A]], [], ["multistep", "negation"])


def q_pool():
    close = R.randint(6, 9)
    if R.random() < 0.5:
        arr = close + 1
        f = [f"The pool closes at {close} pm.", f"We'll get there around {arr} pm."]
        return D(f, "Will the pool still be open when we arrive?", [["no"], ng(close)], [], ["multistep"])
    arr = close - 2
    f = [f"The pool closes at {close} pm.", f"We'll get there around {arr} pm."]
    return D(f, "Will the pool still be open when we arrive?", [["yes"], ng(close)], [], ["multistep"])


def q_sum():
    a, b = R.randint(5, 25), R.randint(4, 15)
    x, y = pk(["book", "jacket", "lamp", "mug", "backpack", "cable"], 2)
    f = [f"I paid {a} euros for the {x}.", f"The {y} was {b} euros."]
    return D(f, "How much did I spend on the two things together?", [ng(a + b)], [], ["multistep"])


def q_left():
    n = R.randint(10, 20)
    m = R.randint(3, 8)
    f = [f"I had {n} stamps.", f"I gave {m} of them to my niece."]
    return D(f, "How many stamps do I still have?", [ng(n - m)], [], ["multistep", "passive"])


def q_fine():
    r = R.randint(2, 4)
    d = R.randint(3, 6)
    f = [f"The library charges {r} euros for each day a book is overdue.", f"I brought mine back {d} days late."]
    return D(f, "What fine do I owe?", [ng(r * d)], [], ["multistep"])


def q_age():
    k = R.randint(2, 6)
    me = R.randint(22, 35)
    A = ch(FN)
    f = [f"My sister {A} is {k} years older than me.", f"I'm {me}."]
    return D(f, f"How old is {A}?", [ng(me + k)], [], ["multistep", "indirect"])


def q_end():
    s = R.randint(3, 7)
    h = R.randint(2, 4)
    f = [f"The film starts at {s} pm.", f"It runs for {h} hours."]
    return D(f, "At what time does the film finish?", [ng(s + h)], [], ["multistep"])


def q_last():
    A, B, C = pk(FN + MN, 3)
    f = [f"{A} arrived before {B}.", f"{C} showed up after {B}."]
    return D(f, "Who got there last?", [[C]], [], ["multistep"])


def q_elim():
    f = ["My key is in one of three places: the top drawer, the middle drawer or the bottom drawer.", "It's not in the top one.", "And I already checked the middle one, nothing there."]
    return D(f, "So where must the key be?", [["bottom"]], [], ["multistep", "negation"])


def q_cities():
    names = pk(FN + MN, 5)
    c1, c2 = pk(CITIES, 2)
    cs = [c1, c2, c1, c2, c1]
    f = [f"{names[i]} lives in {cs[i]}." for i in range(5)]
    return D(f, f"How many of those five people live in {c1}?", [ng(3)], [], ["multistep"])


def q_colour():
    A, B, C = people(2, 1)
    c1, c2 = pk(COLOURS, 2)
    f = [f"{A}'s scarf is {c1}.", f"{B}'s hat is {c2}.", f"{C}'s gloves are {c1}."]
    return D(f, f"Whose item matches the colour of {A}'s scarf?", [[C]], [], ["multistep"])


# ---------------- UNSUPPORTED ----------------
def s_job():
    A, B = people(1, 1)
    j = ch(JOBS)
    f = [f"{A} is a {j}.", f"{B} works from home most days."]
    return D(f, f"What does {B} do for a living?", [], [j], [], abstain=True)


def s_petname():
    A = ch(FN)
    sp = ch(SPECIES)
    pn = ch(PETN)
    f = [f"My friend {A} has a {sp} named {pn}.", f"I have a {sp} too, a very fluffy one."]
    return D(f, f"What did I name my {sp}?", [], [pn], [], abstain=True)


def s_colour():
    c1 = ch(COLOURS)
    o1, o2 = pk(["bike", "scooter", "car", "kayak"], 2)
    f = [f"My {o1} is {c1}.", f"I also own a {o2}."]
    return D(f, f"What colour is my {o2}?", [], [c1], [], abstain=True)


def s_time():
    t1 = R.randint(5, 9)
    f = [f"The yoga class is at {t1} pm.", "I also signed up for a pottery class."]
    return D(f, "What time is the pottery class?", [], [str(t1)], [], abstain=True)


def s_bday():
    A, B = people(1, 1)
    mo = ch(MONTHS)
    f = [f"{A}'s birthday is in {mo}.", f"{B} just started a new job."]
    return D(f, f"When is {B}'s birthday?", [], [mo], [], abstain=True)


def s_city():
    A, B = people(1, 1)
    c = ch(CITIES)
    f = [f"{A} lives in {c}.", f"{B} is my cousin."]
    return D(f, f"Where does {B} live?", [], [c], [], abstain=True)


def s_price():
    n = R.randint(30, 90)
    f = [f"The jacket cost {n} euros.", "I also bought a pair of boots."]
    return D(f, "How much did the boots cost?", [], [str(n)], [], abstain=True)


def s_study():
    A, B = people(1, 1)
    s = ch(SUBJECTS)
    f = [f"{A} studied {s} at university.", f"{B} is my flatmate."]
    return D(f, f"What did {B} study?", [], [s], [], abstain=True)


def s_day():
    d = ch(DAYS)
    f = [f"Book club is on {d}.", "We also have a hiking group."]
    return D(f, "Which day does the hiking group meet?", [], [d], [], abstain=True)


def s_sib():
    n = R.randint(3, 9)
    f = [f"I have {n} cousins."]
    return D(f, "How many brothers and sisters do I have?", [], [str(n)], [], abstain=True)


def s_brother():
    A = ch(FN)
    f = [f"My sister {A} is a nurse."]
    return D(f, "What's my brother's name?", [], [A], ["negation"], abstain=True)


def s_airline():
    c = ch(CITIES)
    A = ch(FN)
    a = ch(AIR)
    f = [f"I'm flying to {c} next week.", f"{A} is flying with {a}."]
    return D(f, "Which airline am I flying with?", [], [a], [], abstain=True)


def s_food():
    A, B = people(1, 1)
    fo = ch(FOODS)
    f = [f"{A}'s favourite food is {fo}.", f"{B} is coming over on Saturday."]
    return D(f, f"What's {B}'s favourite food?", [], [fo], [], abstain=True)


def s_where():
    loc = ch(LOCS)
    f = [f"I left my keys in the {loc}.", "I also brought my umbrella to work."]
    return D(f, "Where is my umbrella now?", [], [loc], [], abstain=True)


def s_age():
    A, B = people(1, 1)
    n = R.randint(25, 60)
    f = [f"{A} is {n} years old.", f"{B} is the quiet one in our group."]
    return D(f, f"How old is {B}?", [], [str(n)], ["paraphrase"], abstain=True)


def s_hotel():
    c1, c2 = pk(CITIES, 2)
    h = ch(HOTELS)
    f = [f"I stayed at the {h} hotel in {c1}.", f"Next month I'm going to {c2}."]
    return D(f, f"Which hotel will I stay at in {c2}?", [], [h], [], abstain=True)


GROUPS = {
    "memory": ([m_loc, m_pet, m_city, m_count, m_day, m_cleft, m_job, m_door, m_bday, m_list, m_neg, m_ind, m_study, m_gift, m_locker], 50),
    "update": ([u_meet, u_neg, u_code, u_jobprev, u_price, u_colour, u_rename, u_time, u_travel, u_street, u_cousins, u_dessert, u_venue, u_chain, u_deadline], 50),
    "reference": ([r_sister, r_bring, r_latter, r_allergy, r_place, r_neigh, r_lent, r_inlaw, r_titles, r_pup, r_former, r_keys], 40),
    "planning": ([p_next, p_left, p_skip, p_add, p_goal, p_budget, p_deadline, p_reorder, p_budchange, p_count], 50),
    "reasoning": ([q_older, q_samecity, q_sameday, q_total, q_weekday, q_before, q_tall, q_rule, q_drive, q_pool, q_sum, q_left, q_fine, q_age, q_end, q_last, q_elim, q_cities, q_colour], 80),
    "unsupported": ([s_job, s_petname, s_colour, s_time, s_bday, s_city, s_price, s_study, s_day, s_sib, s_brother, s_airline, s_food, s_where, s_age, s_hotel], 80),
}
CONFLICT_G = [c_wedding, c_party, c_car, c_city, c_chairs, c_museum, c_dog, c_price, c_manual, c_job]
CONFLICT_K = [k_corr, k_people, k_objects, k_repeat, k_topics, k_usedto, k_pets]


def cycle_templates(tl, n):
    out = []
    while len(out) < n:
        t = list(tl)
        R.shuffle(t)
        out += t
    return out[:n]


def fill_turns(facts, long):
    m = len(facts)
    if long:
        k = R.randint(52, 98)
    else:
        k = R.randint(max(m + 2, 4), 24)
    pos = []
    if long:
        lo_end = k // 4
        hi_start = int(k * 0.66)
        pos = [R.randrange(0, lo_end)]
        if m > 2:
            mids = sorted(R.sample(range(lo_end + 2, hi_start - 1), m - 2))
            pos += mids
        if m > 1:
            pos.append(R.randrange(hi_start, k))
    else:
        for i in range(m):
            lo, hi = i * k // m, (i + 1) * k // m
            pos.append(R.randrange(lo, max(hi, lo + 1)))
    pos = sorted(set(pos))
    assert len(pos) == m, (pos, m, long)
    fill = R.sample(FILLER, k - m)
    msgs = []
    fi = 0
    it = iter(facts)
    for t in range(k):
        if t in pos:
            u = next(it)
        else:
            pf = ch(PREFIX)
            base = fill[fi]
            if pf and not (base.startswith("I ") or base.startswith("I'")):
                base = base[0].lower() + base[1:]
            u = pf + base
            u = u[0].upper() + u[1:]
            fi += 1
        msgs.append({"role": "user", "content": u})
        msgs.append({"role": "assistant", "content": ch(AR)})
    return msgs


def finish(cat, i, d, long):
    hist = fill_turns(d["f"], long)
    feats = list(d["feats"])
    if long:
        feats.append("long")
    crit = {"any": d["any"], "none": d["none"], "clarify": bool(d.get("clarify")), "no_clarify": bool(d.get("no_clarify")), "abstain": bool(d.get("abstain"))}
    return {"id": f"dev-{cat}-{i+1:03d}", "category": cat, "features": feats, "history": hist, "question": d["q"], "criteria": crit}


def main():
    out = []
    longidx = lambda i: (i % 10) in (0, 3, 6)
    for cat, (tl, n) in GROUPS.items():
        for i, t in enumerate(cycle_templates(tl, n)):
            out.append(finish(cat, i, t(), longidx(i)))
    # conflict
    ts = cycle_templates(CONFLICT_G, 30) + cycle_templates(CONFLICT_K, 20)
    R.shuffle(ts)
    for i, t in enumerate(ts):
        out.append(finish("conflict", i, t(), longidx(i)))
    # fix ordering: group conflict between update and reference not required
    with open("questions.jsonl", "w", encoding="utf-8") as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")


main()
