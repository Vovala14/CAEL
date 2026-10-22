from unittest.mock import patch
import pytest
from cael_unified.codegen import chat,explain


@pytest.mark.parametrize('prompt',[
    'Explain this Python code', 'Explain the python snippet',
    'What does this Python code print?', 'What does my Python function return?',
    'Explain this code',
])
def test_language_qualifier_reaches_existing_interpreter(prompt):
    answer=chat.reply(prompt+':\n```python\nx = 3\nprint(x * 2)\n```')
    assert answer['route']=='chat/code-explained'
    assert '```text\n6\n```' in answer['response']


@pytest.mark.parametrize('prompt',[
    'Explain this JavaScript code', 'Explain this medical code',
    'Tell me a story about a Python programmer',
])
def test_unrelated_requests_do_not_match_new_phrase(prompt):
    assert not explain.CODE_ASK.search(prompt)


def test_pasted_source_does_not_gain_file_access():
    with patch('builtins.open',side_effect=AssertionError('Pasted code must not open files')):
        result=explain.reply('Explain this Python code:\n```python\nopen("synthetic-secret.txt").read()\n```',
                             lambda response,route:dict(response=response,route=route))
    assert result['route']=='explained'
