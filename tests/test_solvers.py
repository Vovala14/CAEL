"""General solvers (solve_math, solve_logic), the passage ranker and the Mr. Meesix task agents. No network."""
import sys
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_unified import meesix, passage_rank, solve_logic, solve_math

MATH = [
    ("My lunch break is 45 minutes. The cafe is 8 minutes away each way. How long do I actually have to eat?", "29 minutes"),
    ("A recipe uses 250 g of flour for 12 cookies. How much flour do I need for 30 cookies?", "625 g"),
    ("My flight leaves at 6:40 pm. I need to be at the airport two hours before, and the drive takes 50 minutes. When should I leave home?", "3:50 pm"),
    ("Plan A costs $12 a month. Plan B is $120 a year. Which is cheaper over a year, and by how much?", "Plan B"),
    ("I bought 3 notebooks at $4 each and a pen for $2.50. How much did I spend?", "$14.50"),
    ("Four friends split a $96 dinner bill evenly, and each adds a $3 tip. How much does each person pay?", "$27"),
    ("I have $50. Tickets are $12 each. How many can I buy and how much is left over?", "4 tickets"),
    ("Two painters can paint a fence in 6 hours. How long would three painters take at the same rate?", "4 hours"),
    ("Anna is 3 years older than Ben. Ben is twice as old as Cara. Cara is 5. How old is Anna?", "13"),
    ("A phone was $600 and now costs $480. What percent was the discount?", "20%"),
    ("I pay $60 a month for the gym and $20 a month for the pool. What's that per year?", "$960"),
    ("A cleaner charges $25 an hour and comes for 3 hours twice a week. What's the weekly cost?", "$150"),
    ("Streaming service X is $9 a month, service Y is $95 a year. Which is cheaper over a year?", "Service Y"),
    ("Eggs come in boxes of 6. I need 40 eggs. How many boxes should I buy?", "7 boxes"),
    ("A bus leaves every 15 minutes starting at 8:00. I arrive at 8:37. How long do I wait?", "8 minutes"),
]
NOT_MATH = ["I'm 30 and want to learn piano. Is it too late?", "I have 2 cats and 3 dogs. What should I name them?",
            "What happened in 1969?", "My rent is $900 a month. Is that a lot?", "I drink 4 cups of coffee a day. Is that too much?",
            "Can you give me 3 ideas for dinner?"]
LOGIC = [
    ("No reptiles are mammals. All snakes are reptiles. Are any snakes mammals?", "**No.**"),
    ("All cats are animals. Some animals are pets. Does it follow that some cats are pets?", "Not necessarily"),
    ("If it rains, the match is cancelled. The match was not cancelled. Did it rain?", "**No.**"),
    ("If it rains, the ground gets wet. The ground is wet. Did it rain?", "Not necessarily"),
    ("Either the key is in the drawer or it's in my bag. It's not in the drawer. Where is it?", "In your bag"),
    ("Ana finished before Bo. Cy finished after Bo but before Di. Who came third?", "**Cy**"),
    ("Only members can enter the lounge. Jo entered the lounge. Is Jo a member?", "**Yes.**"),
    ("None of the red boxes are heavy. This box is heavy. Is it red?", "**No.**"),
    ("The red house is left of the blue house. The green house is right of the blue house. Which house is in the middle?", "blue house"),
    ("If the shop is open, the lights are on. The lights are off. Is the shop open?", "**No.**"),
    ("If all cats are animals and Tom is a cat, is Tom an animal?", "**Yes.**"),
]
NOT_LOGIC = ["If I move to Berlin, should I learn German first?", "Either I take the job or I stay. How do I decide?",
             "No one replied to my email. Should I follow up?", "My brother is taller than me. Why do siblings differ in height?"]


class Engine:
    """Stands in for the full pipeline: records what the agents hand over."""
    def __init__(self):
        self.seen = []

    def respond(self, messages, _agents=True, **kw):
        self.seen.append(messages[-1]['content'])
        return dict(route='chat/stub', response='stub answer')


class SolverTests(unittest.TestCase):
    def test_math(self):
        for text, want in MATH:
            self.assertIn(want.lower(), (solve_math.solve(text) or '').lower(), text)

    def test_math_follow_up(self):
        first = "A recipe uses 250 g of flour for 12 cookies. How much flour do I need for 30 cookies?"
        got = solve_math.respond([dict(role='user', content=first), dict(role='assistant', content='625 g'), dict(role='user', content='And for 18?')])
        self.assertIn('375 g', got['response'])

    def test_math_leaves_chat_alone(self):
        for text in NOT_MATH:
            self.assertIsNone(solve_math.solve(text), text)

    def test_logic(self):
        for text, want in LOGIC:
            self.assertIn(want, solve_logic.solve(text) or '', text)

    def test_logic_leaves_chat_alone(self):
        for text in NOT_LOGIC:
            self.assertIsNone(solve_logic.solve(text), text)

    def test_ranker_prefers_an_answer_to_a_teaser(self):
        pages = [('A', 'web', 'Cast iron', 'Dry the pan and rub it with a thin coat of oil. Bake it at 230 C for an hour so the oil forms a hard layer.', 'https://a.example/x'),
                 ('B', 'web', 'Seasoning', 'Rub a thin coat of oil over the pan and bake it for an hour. The oil hardens into a protective layer.', 'https://b.example/y')]
        teaser = "Here's everything you need to know about how to season a cast iron pan, so read on."
        real = 'Dry the pan and rub it with a thin coat of oil. Bake it at 230 C for an hour so the oil forms a hard layer.'
        ranked = passage_rank.rerank([(0.9, 0.8, teaser, 'C', 'Guide', 'https://c.example/z'), (0.8, 0.8, real, 'A', 'Cast iron', 'https://a.example/x')],
                                     'How do I season a cast iron pan?', pages, lambda u: u.split('/')[2])
        self.assertEqual(ranked[0][2], real)

    def test_meesix_one_agent_per_task_then_gone(self):
        engine = Engine()
        text = ("A shirt costs $40 and is 25% off. What do I pay? Liam is taller than Noah. Noah is taller than Eva. Who is the shortest? "
                "What is a good name for a goldfish?")
        out = meesix.run([dict(role='user', content=text)], engine)
        self.assertEqual((out['route'], out['agents']), ('chat/meesix', 3))
        self.assertIn('$30', out['response']); self.assertIn('Eva', out['response']); self.assertIn('stub answer', out['response'])
        self.assertEqual(engine.seen, ['What is a good name for a goldfish?'])     # only the task no solver takes
        self.assertEqual(meesix.ALIVE, set())                                       # every agent has vanished
        self.assertEqual([p['agent'] for p in out['parts']], ['Meesix-1', 'Meesix-2', 'Meesix-3'])

    def test_meesix_never_more_than_six_at_once(self):
        peak, lock = [0], threading.Lock()
        real = meesix.specialists

        def watched(messages):
            with lock:
                peak[0] = max(peak[0], len(meesix.ALIVE))
            time.sleep(0.05)
            return real(messages)
        meesix.specialists = watched
        try:
            text = ' '.join(f'What is the capital city of country number {i}?' for i in range(1, 11))
            out = meesix.run([dict(role='user', content=text)], Engine())
        finally:
            meesix.specialists = real
        self.assertEqual(out['agents'], 10)
        self.assertGreater(peak[0], 1)
        self.assertLessEqual(peak[0], meesix.LIMIT)
        self.assertEqual(meesix.ALIVE, set())

    def test_meesix_agents_work_at_the_same_time(self):
        class Slow(Engine):
            def respond(self, messages, _agents=True, **kw):
                time.sleep(0.4)                     # a look-up
                return dict(route='chat/stub', response='answer to: ' + messages[-1]['content'])
        text = ' '.join(f'What is the capital city of country number {i}?' for i in range(1, 7))
        started = time.perf_counter()
        out = meesix.run([dict(role='user', content=text)], Slow())
        took = time.perf_counter() - started
        self.assertEqual(out['agents'], 6)
        self.assertLess(took, 1.2)                  # six 0.4 s tasks: about 0.4 s side by side, 2.4 s one after another
        for i in range(1, 7):                       # each answer sits under its own question, in the order asked
            self.assertIn(f'**What is the capital city of country number {i}?**\nanswer to: What is the capital city of country number {i}?',
                          out['response'])
        self.assertEqual(meesix.ALIVE, set())

    def test_web_check_state_is_per_thread(self):
        from cael_unified import web_check
        seen = {}

        def work(name, value):
            web_check.STATE['listy'] = value
            web_check.TRACE.clear(); web_check.TRACE.update(who=name)
            time.sleep(0.05)
            seen[name] = (web_check.STATE.get('listy'), web_check.TRACE.get('who'))
        threads = [threading.Thread(target=work, args=(f't{i}', i % 2 == 0)) for i in range(6)]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.assertEqual(seen, {f't{i}': (i % 2 == 0, f't{i}') for i in range(6)})

    def test_meesix_single_task_messages(self):
        self.assertIsNone(meesix.run([dict(role='user', content='How are you today?')], Engine()))
        whole = 'A tap fills 9 litres a minute. How long to fill 180 litres? And for 270?'
        self.assertEqual(meesix.tasks_of(whole), [whole])


class StackNet:
    """Stands in for the Stack Exchange API: one stored question with two answers."""
    def __init__(self):
        self.urls = []

    def json(self, url, **kw):
        self.urls.append(url)
        if '/answers' in url:
            return dict(items=[dict(question_id=7, answer_id=1, is_accepted=False, score=9, body='<p>Scrub it.</p>'),
                               dict(question_id=7, answer_id=2, is_accepted=True, score=5,
                                    body='<p>Rub a thin coat of oil over the whole pan.</p><pre>code</pre><p>Bake it upside down at 230 C '
                                         'for an hour, then let it cool in the oven. Repeat a few times for a hard, dark layer.</p>')],
                        quota_remaining=250)
        return dict(items=[dict(question_id=7, title='How do I season a cast iron pan?', answer_count=2, link='https://cooking.example/q/7'),
                           dict(question_id=8, title='How do I remind someone of my birthday?', answer_count=1, link='https://x/q/8')],
                    quota_remaining=250)


class StackSourceTests(unittest.TestCase):
    def test_accepted_answer_of_the_matching_question_only(self):
        from cael_unified import stack_source
        import os
        os.environ['CAEL_WEB_SEARCH'] = '1'
        try:
            net = StackNet()
            self.assertEqual(stack_source.sites_for('How do I season a cast iron pan?'), ['cooking'])
            got = stack_source.pages('season cast iron pan', 'How do I season a cast iron pan?', network=net)
        finally:
            os.environ['CAEL_WEB_SEARCH'] = '0'
        self.assertEqual(len(got), 1)                                   # the birthday question is not about this
        name, host, title, body, url = got[0]
        self.assertEqual((name, url), ('Stack Exchange (Seasoned Advice)', 'https://cooking.example/q/7'))
        self.assertIn('Rub a thin coat of oil', body); self.assertNotIn('code', body); self.assertNotIn('Scrub', body)
        self.assertTrue(all('candle' not in u for u in net.urls))

    def test_no_site_no_call(self):
        from cael_unified import stack_source
        self.assertEqual(stack_source.sites_for('Who wrote Hamlet?'), [])


if __name__ == '__main__':
    unittest.main()
