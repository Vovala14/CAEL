"""Route complete mathematical contracts to the existing exact solvers first."""
from fractions import Fraction
import re


def reply(text):
    if len(text) > 500 or '\n' in text or '```' in text:
        return None
    t = text.strip().rstrip(' ?.').lower()
    t = re.sub(r'^(?:please\s+|(?:can|could|would) you\s+(?:please\s+)?)(?=(?:solve|find|calculate|compute)\b)', '', t)
    conditional = re.fullmatch(r'(?:if|given) ([a-z]) is (positive|negative|nonnegative|nonzero),\s*(solve .+?)(?: and explain (?:the )?(?:inequality|condition))?', t)
    if conditional:
        name, condition, equation = conditional.groups()
        solved = reply(equation)
        if solved is None or solved.get('route') != 'helper/equation':
            return None
        first = solved['response'].split('\n', 1)[0]
        if not re.fullmatch(r'[a-z] = -?\d+(?:\.\d+)?(?:/\d+)?(?: or [a-z] = -?\d+(?:\.\d+)?(?:/\d+)?)*', first):
            return dict(route='helper/unsupported', response='I cannot yet check that condition against every solution of this equation.', sources=[])
        values = re.findall(r'([a-z]) = (-?\d+(?:\.\d+)?(?:/\d+)?)', first)
        if any(variable != name for variable, _ in values):
            return None
        comparison = {'positive': ('>', lambda v: v > 0), 'negative': ('<', lambda v: v < 0),
                      'nonnegative': ('>=', lambda v: v >= 0), 'nonzero': ('!=', lambda v: v != 0)}[condition]
        kept = [value for _, value in values if comparison[1](Fraction(value))]
        bound = name+' '+comparison[0]+' 0'
        response = ' or '.join(name+' = '+v for v in kept) if kept else 'No solution satisfies '+bound+'.'
        response += '\nThe '+condition+' condition means '+bound+'; '+('the stated solution(s) satisfy it.' if kept else 'all equation roots violate it.')
        return dict(solved, response=response, details=solved.get('details', '')+'\nChecked the complete sign condition against every numeric root.')
    if '=' in t:
        body = re.sub(r'^(?:solve(?:\s+(?:the\s+)?(?:equations?|system))?(?:\s+for\s+[a-z](?:\s*(?:and|,)\s*[a-z])?)?\s*:?\s*|find\s+[a-z]\s+(?:in\s+)?)', '', t)
        # Mathematical names are single letters. Prose/code/extra requirements
        # cannot be silently discarded by a permissive downstream equation rule.
        if not re.fullmatch(r'[\d\sa-z+*/().,^=;\-]+', body) or any(w != 'and' for w in re.findall(r'[a-z]{2,}', body)):
            return None
        from .helper_math import reply as symbolic
        from .helper_chat import linear
        result = symbolic(t) or linear(t)
        return result
    from .helper_math import reply as exact
    if re.match(r'^(?:(?:what is|find|calculate|compute) (?:the )?)?(?:mean|average|median|range)\s+of\b', t):
        return exact(t)
    # word_frame validates the entire proportional-price contract, including
    # consistent product names and all quantities, before this route can commit.
    if re.search(r'\bcost\b', t):
        from .helper_math import word_frame
        return word_frame(t)
    return None
