"""CAEL 0.3.6 context reasoner: retrieval over clause records, update chains, conflicts between sources, compositional
operations, abstention for unsupported questions, and leaving general questions to other routes."""
import unittest

from cael_unified import compact, conversation_memory as cm, spelling


def chat(*lines):
    history = []
    for line in lines:
        history += [dict(role='user', content=line), dict(role='assistant', content='Sure.')]
    return history


def ask(history, question):
    answer = cm.reply(history + [dict(role='user', content=question)])
    return answer['response'] if answer else None


class ReasonerTests(unittest.TestCase):
    def test_paraphrased_recall_and_passive(self):
        h = chat('I did a degree in marine biology back in Bergen.', 'The fence was painted by my uncle Tobias.', 'Nice weather.')
        self.assertIn('marine biology', ask(h, 'What did I study?').lower())
        self.assertIn('Tobias', ask(h, 'Who painted the fence?'))

    def test_update_without_repeating_the_topic(self):
        h = chat('My gym locker code is 4417.', 'Ugh, I keep forgetting things.', 'Correction: the code is 4471, I swapped two digits.')
        self.assertIn('4471', ask(h, "What's my gym locker code?"))

    def test_two_sources_disagree(self):
        h = chat('The leaflet says the pool opens at 7 am.', 'Marta insists it opens at 8 am.')
        reply = ask(h, 'When does the pool open?')
        self.assertIn('7', reply)
        self.assertIn('8', reply)
        self.assertRegex(reply, 'disagree|conflict|which')

    def test_compositional_operations(self):
        self.assertIn('5', ask(chat('I bought 12 eggs.', 'We used 7 of them for the cake.'), 'How many eggs do I still have?'))
        self.assertIn('Saturday', ask(chat('Today is Wednesday.', 'The parcel should come in 3 days.'), 'What weekday will the parcel come?'))
        self.assertIn('Ines', ask(chat('Only Ines and Paul can drive.', 'Paul is busy on Sunday.'), 'Who could drive me on Sunday?'))
        self.assertIn('Ola', ask(chat('Ola lives in Bergen.', 'Kai lives in Oslo.', 'Mo lives in Oslo.', 'Liv lives in Bergen.'),
                                 'Who lives in the same city as Liv?'))
        self.assertIn('37', ask(chat('My cousin Vera is 4 years older than me.', "I'm 33."), 'How old is Vera?'))

    def test_abstains_when_never_said(self):
        h = chat('The jacket cost 60 euros.', 'I also bought some gloves.')
        reply = ask(h, 'How much did the gloves cost?')
        self.assertIn("don't know", reply)
        self.assertNotIn('60', reply)

    def test_general_questions_are_left_alone(self):
        h = chat('My sister Ana lives in Rome.', 'She works as a vet.', 'The concert is on Friday.')
        for question in ('Where do penguins live?', 'What does a vet do?', 'How old was Einstein?', 'Where is Rome?',
                         'How much does a car cost?', 'What is my name?'):
            with self.subTest(question=question):
                self.assertIsNone(ask(h, question))

    def test_long_conversation(self):
        filler = ['Random thought: clouds are odd.', 'I had toast.', 'Traffic was bad.', 'I love autumn.'] * 45
        h = chat(*(['My bike is green.'] + filler + ['I repainted my bike blue.'] + filler[:20]))
        self.assertIn('blue', ask(h, 'What colour is my bike now?'))


class CompactTablesTests(unittest.TestCase):
    def test_counts_and_groups_round_trip(self):
        table = compact.Counts.build({'black hole': 40, 'red car': 3})
        self.assertEqual(table.get('black hole'), 40)
        self.assertEqual(table.get('blue car', 0), 0)
        self.assertIn('red car', table)
        groups = compact.Groups.build([('ct', 0), ('ca', 0), ('at', 0), ('cat', 0), ('ct', 1)], ['cat', 'cut'])
        self.assertEqual(sorted(groups.get('ct')), ['cat', 'cut'])

    def test_spelling_still_corrects(self):
        self.assertEqual(spelling.correct('whats teh captial of frnace')[0], "what's the capital of france")


if __name__ == '__main__':
    unittest.main()
