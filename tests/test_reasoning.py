"""Unseen names, missing premises, contradictions and offline reasoning controls."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from cael_unified.reasoning import Reasoner
from cael_unified.reasoning_logic import LogicCA, Unparsed
from cael_unified.reasoning_world import WorldCA
from cael_unified.reasoning_order import ordering


class ReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Reasoner()

    def test_two_step_deduction_and_proof(self):
        result=self.engine.solve('Luma is a rover. All rovers are machines. All machines are physical.','Is Luma physical?')
        self.assertEqual(result['answer'],'true')
        self.assertEqual(result['depth'],2)
        self.assertEqual(result['support'],[1,2,3])

    def test_multiword_entity_is_kept_intact(self):
        self.assertEqual(self.engine.solve('Alice Smith is a rover. All rovers are machines.','Is Alice Smith a machine?')['answer'],'true')

    def test_missing_premise_is_unknown_not_false(self):
        result=self.engine.solve('Nori is curious. All birds are animals.','Is Nori an animal?')
        self.assertEqual(result['answer'],'unknown')

    def test_converse_is_not_inferred(self):
        result=self.engine.solve('All birds are animals. Nori is an animal.','Is Nori a bird?')
        self.assertEqual(result['answer'],'unknown')

    def test_conjunction_requires_both_premises(self):
        result=self.engine.solve('Everything that is warm and dry is safe. Zed is warm.','Is Zed safe?')
        self.assertEqual(result['answer'],'unknown')
        result=self.engine.solve('Everything that is warm and dry is safe. Zed is warm. Zed is dry.','Is Zed safe?')
        self.assertEqual(result['answer'],'true')

    def test_explicit_negation_and_contradiction(self):
        context='All birds are animals. Nori is a bird. Nori is not an animal.'
        self.assertEqual(self.engine.solve(context,'Is Nori an animal?')['answer'],'conflicting')
        self.assertEqual(self.engine.solve('Nori is not blue.','Is Nori blue?')['answer'],'false')

    def test_cycle_does_not_create_evidence(self):
        result=self.engine.solve('All rovers are machines. All machines are rovers. Nori is curious.','Is Nori a machine?')
        self.assertEqual(result['answer'],'unknown')

    def test_deep_chain_on_unseen_vocabulary(self):
        for hops in (3,7,12):
            context='Zora is a kind0. '+' '.join(f'Every kind{i} is a kind{i+1}.' for i in range(hops))
            # Digits are deliberately outside the surface grammar; use alphabetic names.
            for i in range(hops,-1,-1):
                context=context.replace(f'kind{i}', 'kind'+chr(97+i))
            result=self.engine.solve(context,'Is Zora kind'+chr(97+hops)+'?')
            self.assertEqual(result['answer'],'true')
            self.assertEqual(result['depth'],hops)

    def test_object_tracks_owner_movement_and_drop(self):
        context='Nori moved to the cellar. Nori grabbed the key. Nori moved to the garden. Nori dropped the key. Nori moved to the office.'
        self.assertEqual(self.engine.solve(context,'Where is the key?')['answer'],'garden')

    def test_transfer_changes_owner(self):
        context='Nori moved to the cellar. Luma moved to the cellar. Nori grabbed the key. Nori gave the key to Luma. Luma moved to the office.'
        self.assertEqual(self.engine.solve(context,'Where is the key?')['answer'],'office')
        self.assertEqual(self.engine.solve(context,'Who has the key?')['answer'],'luma')

    def test_multiple_gift_objects_are_not_arbitrarily_selected(self):
        context='Nori gave the key to Luma. Nori gave the book to Luma.'
        self.assertEqual(self.engine.solve(context,'What did Nori give to Luma?')['answer'],'unknown')

    def test_previous_location(self):
        context='Nori moved to the cellar. Nori grabbed the key. Nori moved to the garden. Nori moved to the office.'
        self.assertEqual(self.engine.solve(context,'Where was the key before the office?')['answer'],'garden')

    def test_uncertain_location_and_identical_alternatives(self):
        self.assertEqual(self.engine.solve('Nori is either in the office or the garden.','Is Nori in the office?')['answer'],'maybe')
        # A benchmark annotation says "maybe" for duplicate alternatives, but logic says yes.
        self.assertEqual(self.engine.solve('Nori is either in the office or the office.','Is Nori in the office?')['answer'],'yes')

    def test_size_transitivity(self):
        context='The chest is bigger than the box. The key fits inside the box.'
        self.assertEqual(self.engine.solve(context,'Does the key fit in the chest?')['answer'],'yes')
        self.assertEqual(self.engine.solve(context,'Does the chest fit in the key?')['answer'],'no')

    def test_path_and_disconnected_graph(self):
        context='The office is north of the hall. The garden is east of the office. The cellar is west of the attic.'
        self.assertEqual(self.engine.solve(context,'How do you go from the hall to the garden?')['answer'],'n,e')
        self.assertEqual(self.engine.solve(context,'How do you go from the hall to the cellar?')['answer'],'unknown')

    def test_ordering_ambiguity_and_conflict(self):
        context='Items: Nori, Luma, Zed. Nori is before Luma.'
        self.assertEqual(ordering(context,'Who is first?')['answer'],'unknown')
        self.assertEqual(ordering(context+' Luma is before Nori.','Who is first?')['answer'],'conflicting')

    def test_single_letter_items_are_not_matched_inside_words(self):
        context='Items: A, B, C. B is after A. C is after B.'
        self.assertEqual(ordering(context,'Who is first?')['answer'],'a')

    def test_no_network_and_no_cross_conversation_state(self):
        prompt='Facts: Nori is a rover. All rovers are machines. Is Nori a machine?'
        with patch('cael_unified.network.NETWORK.json',side_effect=AssertionError('Network used')):
            answer=self.engine.respond(prompt)
            self.assertEqual(answer['reasoning']['answer'],'true')
            other=self.engine.respond('Facts: Nori is curious. Is Nori a machine?')
            self.assertEqual(other['reasoning']['answer'],'unknown')

    def test_followup_uses_only_supplied_user_conversation(self):
        prompt='Facts: Nori is a rover. All rovers are machines. Is Nori a machine?'
        messages=[dict(role='user',content=prompt),dict(role='assistant',content='Yes.'),dict(role='user',content='Is Nori curious?')]
        self.assertEqual(self.engine.respond(messages[-1]['content'],messages)['reasoning']['answer'],'unknown')
        self.assertIsNone(self.engine.respond('Is Nori a machine?'))

    def test_unsupported_premise_is_not_silently_dropped(self):
        answer=self.engine.respond('Facts: Nori is a bird. Unless it rains, all birds fly. Is Nori flying?')
        self.assertEqual(answer['route'],'chat/reasoning-unsupported')

    def test_ordinary_facts_weather_chat_are_not_intercepted(self):
        for text in ('What is gravity?','Paris weather','hello','2 + 4','Write a story about a bird'):
            self.assertIsNone(self.engine.respond(text))


if __name__=='__main__':
    unittest.main()
