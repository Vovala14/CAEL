"""Small self-test after round 20 (no Qwen): new conversations of the kinds round 20 lost.

1. A problem told without a question: any thread quoted must be about the user's own thing (its title names it), never a
   neighbour of it (a drywall thread for a builder who vanished, a toddler's night waking for a nine-year-old left out).
2. A share of an amount and recipe scaling, over two turns.
Written after the fixes, on subjects not used to make them."""
import os
import re
import tempfile
from pathlib import Path

import pytest

from cael_unified import Assistant


def run(turns):
    tmp = Path(tempfile.mkdtemp(prefix='selfcheck_'))
    os.environ.update(CAEL_LTM=str(tmp / 'ltm.json'), CAEL_MEMORY_FILE=str(tmp / 'memory.json'))
    model = Assistant(output_root=tmp / 'outputs')
    history, out = [], []
    for t in turns:
        history.append(dict(role='user', content=t))
        r = model.respond(history, n=1, seed=137, mode='chat')
        history.append(dict(role='assistant', content=r['response']))
        out.append(r)
    return out


TOLD = [
    ("Our plumber fitted a new boiler last month and now he won't come back to fix the leak.", r'plumb|boiler|leak'),
    ("My daughter is twelve and none of her friends invited her to the sleepover.", r'daughter|friend|sleepover|party|invit|child|kid'),
    ("Our son takes ages to get dressed every morning and we keep missing the bus.", r'son|child|kid|dress|morning|bus'),
    ("My radiator in the hall is cold at the top.", r'radiator'),
    ("Our garden gate has dropped and scrapes on the path.", r'gate'),
    ("My jeans have a hole in the knee.", r'jeans|denim|hole|knee'),
    ("Our tortoise hasn't eaten anything since he woke up from hibernation.", r'tortoise|turtle|hibernat'),
    ("The grout in our shower has gone pink.", r'grout|shower|pink|mold|mould'),
]


@pytest.mark.parametrize('text,thing', TOLD)
def test_unasked_help_quotes_only_threads_about_the_thing(text, thing):
    r = run([text])[0]
    reply = r['response']
    assert reply.strip()
    for title in re.findall(r'Source: (.+?) \((?:Stack Exchange|Wikipedia|OpenAssistant|Dolly)', reply) + re.findall(r'; also "(.+?)" \(', reply):
        assert re.search('(?i)' + thing, title), f'quoted a thread not about the thing: {title!r}'


@pytest.mark.parametrize('turns,answers', [
    (["The car repair was quoted at $1,600 and the garage wants 25% as a deposit. How much is the deposit?",
      "If they refund 50% of that, how much do I get back?"], ['$400', '$200']),
    (["Our holiday cost $2,000 and the agency kept 15% when we cancelled. How much should we get back?",
      "If they finally return 95% of the full price, how much is that?"], ['$1,700', '$1,900']),
    (["A cookie recipe uses 200 g of flour for 16 cookies. How many grams of flour for 40 cookies?",
      "And how much sugar if the recipe uses 80 g for 16 cookies?"], ['500 g', '200 g']),
    (["A soup recipe uses 600 ml of stock for 4 bowls. How much stock for 10 bowls?"], ['1,500 ml']),
])
def test_shares_and_recipe_scaling(turns, answers):
    out = run(turns)
    for r, want in zip(out, answers):
        assert want in r['response'], (want, r['response'][:200])
