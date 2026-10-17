import unittest
from unittest.mock import patch

from cael_unified import explain
from cael_unified.facts import FactLookup
from cael_unified.knowledge_html import ArticleText

CHESS = [
    dict(heading='Introduction', paragraphs=['The rules of chess govern the play of the game of chess. Chess is a two-player board game.']),
    dict(heading='Initial setup', paragraphs=['Chess is played on a chessboard of 64 squares in eight rows.'],
         items=['Rooks are placed on the outside corners.', 'Knights are placed immediately inside of the rooks.']),
    dict(heading='Basic moves', paragraphs=['Each type of chess piece has its own method of movement.'],
         items=['The king moves exactly one square adjacent to it.', 'A bishop moves any number of vacant squares diagonally.']),
    dict(heading='Check', paragraphs=['A king is in check when it is under attack by at least one enemy piece.']),
    dict(heading='Recording moves', paragraphs=['Each square of the chessboard is identified with a letter and a number.']),
    dict(heading='History', paragraphs=['The rules of chess have evolved much over the centuries from early games.']),
]


class ExplainTests(unittest.TestCase):
    def test_requests_to_be_taught_are_recognised(self):
        cases = {'Please explain the rules of chess': ('rules', 'chess'), 'how do i play poker': ('rules', 'poker'),
                 'how to make bread': ('method', 'bread'), 'how does a jet engine work?': ('mechanism', 'jet engine'),
                 'I want to learn how to play chess': ('rules', 'chess'), 'teach me to cook pasta': ('method', 'pasta'),
                 'teach me chess': ('learn', 'chess')}
        for text, (focus, subject) in cases.items():
            parsed = explain.parse(text)
            self.assertEqual((parsed['focus'], parsed['subject']), (focus, subject), text)
        for text in ('what is chess?', 'how are you?', 'explain it to me', 'I like chess'):
            self.assertIsNone(explain.parse(text), text)

    def test_explanation_uses_relevant_sections_and_lists(self):
        text = explain.compose('Rules of chess', CHESS, 'rules')
        for wanted in ('Initial setup:', '• Rooks are placed', 'Basic moves:', '• The king moves exactly one square', 'Check:'):
            self.assertIn(wanted, text)
        for unwanted in ('History', 'Recording moves'):
            self.assertNotIn(unwanted, text)

    def test_list_items_are_parsed_separately_from_paragraphs(self):
        parser = ArticleText()
        parser.feed('<h2>Basic moves</h2><p>Each type of chess piece has its own method of movement, described below.</p>'
                    '<ul><li>The king moves exactly one square adjacent to it.</li></ul>')
        section = parser.sections[0]
        self.assertEqual(section['items'], ['The king moves exactly one square adjacent to it.'])
        self.assertEqual(len(section['paragraphs']), 1)

    def test_lookup_answers_explain_requests_with_the_composed_explanation(self):
        lookup = FactLookup()
        with patch.object(lookup, 'explain', return_value={'route': 'chat/web-wikipedia-explained', 'response': 'x'}) as teach:
            self.assertEqual(lookup.respond('Please explain the rules of chess')['route'], 'chat/web-wikipedia-explained')
        self.assertEqual(teach.call_args.args[0]['focus'], 'rules')


if __name__ == '__main__':
    unittest.main()
