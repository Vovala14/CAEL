"""General name-renaming and actor-separation controls, with no benchmark text."""
import unittest
from cael_unified.entity_binding import normalize


class EntityBindingTests(unittest.TestCase):
    def test_consistent_renaming_has_identical_internal_addresses(self):
        first=normalize('Mira told Owen a secret. Owen thanked Mira.',['Mira knows.','Owen knows.'])
        second=normalize('Cleo told Ivo a secret. Ivo thanked Cleo.',['Cleo knows.','Ivo knows.'])
        self.assertEqual(first[:2],second[:2])
        self.assertNotEqual(first[2],second[2])

    def test_two_actors_keep_distinct_addresses(self):
        context,endings,_=normalize('Mira spoke while Owen listened.',['Mira spoke.','Owen spoke.'])
        self.assertIn('personalpha',context)
        self.assertIn('personbeta',context)
        self.assertNotEqual(endings[0],endings[1])

    def test_common_sentence_words_are_not_people(self):
        _,_,mapping=normalize('The guide explained it. Both people heard. After that Mira left.')
        self.assertEqual(mapping,{'mira':'personalpha'})

    def test_binding_is_idempotent(self):
        context,endings,_=normalize('Mira met Owen.',['Owen waved.'])
        second=normalize(context,endings)
        self.assertEqual(second[:2],(context,endings))

    def test_lowercase_reference_to_context_name_is_bound(self):
        _,endings,_=normalize('Mira met Owen.',['mira knows.','owen knows.'])
        self.assertEqual(endings,['personalpha knows.','personbeta knows.'])


if __name__=='__main__':
    unittest.main()
