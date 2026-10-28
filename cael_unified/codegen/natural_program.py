"""Translate finite natural data workflows into existing checked plan compilers.

Every clause must parse in full. No arbitrary code execution, LM, stored task
answer, or dropping unknown modifiers. Generated source is reconstructed from
the semantic operation list, then checked in the existing bounded Python VM.
"""
import re

from . import task_tools, data_tools
from .python_vm import Unsupported
from .tool_contract import attach

PREFIX = 'Composed Python workflow '
HEAD = re.compile(r'(?is)^\s*(?:please\s+)?(?:write|create|build|make|implement|generate)\s+(?:a\s+)?python\s+(?:function|helper|tool)'
                  r'(?:\s+(?:named|called)\s+([A-Za-z_]\w*))?\s+(?:that|to|which)\s+(.+?)\s*$')
FOLLOW = re.compile(r'(?is)^\s*(?:use|run|apply) (?:it|the tool|the function) (?:on|with)\s+(.+?)\s*$')
SHOW = re.compile(r'(?i)^\s*(?:show|explain) (?:the |your )?(?:tool|source|code)\s*[.!?]*$')
FIELD = r'[A-Za-z][A-Za-z0-9_]{0,39}'
INT = r'-?\d{1,8}'
# Defer only a complete ordinary contract to the existing specialized composer.
# Extra clauses/constraints must stay here and be rejected rather than lost.
SPECIALIZED_SPLIT = re.compile(
    r'(?i)^splits? (?:an? |the )?(?:list|array|sequence) into (?:chunks|batches)'
    r'(?: (?:of(?: size)?|with size) [1-9]\d{0,4})?'
    r'(?: including (?:the )?(?:last|final) (?:shorter|partial|incomplete) (?:chunk|batch))?[.!]?$')


class Unclear(ValueError):
    pass


def current_request(text, messages=None):
    if not (FOLLOW.fullmatch(text) or SHOW.fullmatch(text)):
        return None
    history = messages or []
    if len(history)<3 or history[-2].get('role')!='assistant' or not history[-2].get('content','').startswith(PREFIX):
        return None
    for i in range(len(history)-3, max(-1, len(history)-15), -2):
        if history[i].get('role')!='user':
            break
        old = history[i]['content']
        if HEAD.fullmatch(old.split('\nInput:',1)[0]):
            return old
        if i<1 or not history[i-1].get('content','').startswith(PREFIX):
            break
    return None


def interested(text, messages=None):
    header = re.split(r'(?im)^\s*input\s*:', text, maxsplit=1)[0]
    match = HEAD.fullmatch(header.strip())
    # A standalone supported split belongs to the existing algorithm composer.
    # Inline data and compound workflows retain their full-parse safeguards.
    if match and header == text and SPECIALIZED_SPLIT.fullmatch(match[2]):
        return False
    # Preserve specialized ordinary algorithms; this adapter owns explicit
    # collection workflows, not all requests for a Python function.
    return bool(current_request(text, messages) or match and re.match(
        r'(?i)^(?:keep\w*|filter\w*|split\w*|trim\w*|strip\w*|remove\w* empty|drop\w* empty|'
        r'double\w*|triple\w*|square\w*|cube\w*|multiply|add\w*|subtract\w*|group\w*|count\w* records)\b', match[2]))


def split_steps(text):
    """Split prose delimiters outside quoted literals; never split their commas."""
    from ..orchestrator import protected_spans, unprotected
    spans = protected_spans(text)
    parts, start = [], 0
    for match in re.finditer(r'\s*(?:;|,?\s+(?:and\s+)?then\s+|,\s*(?:and\s+)?|\s+and\s+(?=(?:sum|count|sort|join|return|keep|filter|map|double|triple|square|cube|trim|strip|remove|drop)\b))\s*', text, re.I):
        if unprotected(text, match, spans):
            value = text[start:match.start()].strip(' .')
            if value:
                parts.append(value)
            start = match.end()
    tail = text[start:].strip(' .')
    if tail:
        parts.append(tail)
    if not 1<=len(parts)<=8:
        raise Unclear('Use one to eight ordered collection operations.')
    return parts


def normalize_clause(clause):
    value = clause.strip().rstrip('.')
    # Only the command's leading verb is normalized; field names and literal
    # strings retain case and spelling.
    verbs = {'keeps':'keep','filters':'filter','splits':'split','trims':'trim',
             'strips':'strip','removes':'remove','drops':'drop','doubles':'double',
             'triples':'triple','squares':'square','cubes':'cube','sums':'sum',
             'counts':'count','sorts':'sort','joins':'join','returns':'return',
             'lowercases':'lowercase','casefolds':'casefold',
             'groups':'group','adds':'add','subtracts':'subtract','multiplies':'multiply'}
    first = re.match(r'\w+', value)
    if first:
        word = first[0].lower()
        value = verbs.get(word, word)+value[first.end():]
    return value


def operation(clause, domain):
    t = normalize_clause(clause)
    low = t.lower()
    if domain == 'numbers':
        filters = {
            'positive':'keep positive values', 'negative':'keep negative values',
            'nonnegative':'keep nonnegative values', 'nonzero':'keep nonzero values',
            'even':'keep even values', 'odd':'keep odd values',
        }
        match = re.fullmatch(r'(?i)(?:keep|filter)(?: only)? (positive|negative|nonnegative|nonzero|even|odd) (?:numbers|integers|values)(?: only)?', t)
        if match:
            return filters[match[1].lower()]
        match = re.fullmatch(r'(?i)(double|triple|square|cube) (?:each|every|the) (?:value|number|integer)', t)
        if match:
            return {'double':'map x*2','triple':'map x*3','square':'map x*x','cube':'map x*x*x'}[match[1].lower()]
        match = re.fullmatch(r'(?i)(?:multiply (?:each|every) (?:value|number) by|add) ('+INT+r')(?: to (?:each|every) (?:value|number))?', t)
        if match:
            if low.startswith('add') and not re.search(r'(?i) to (?:each|every) (?:value|number)$', t):
                raise Unclear('Specify what the addition applies to, for example add 3 to each value.')
            return 'map x'+('+' if low.startswith('add') else '*')+match[1]
        match = re.fullmatch(r'(?i)subtract ('+INT+r') from (?:each|every) (?:value|number)', t)
        if match:
            return 'map x-('+match[1]+')'
        if low in {'sum them','sum them all','sum the values','sum the numbers','sum','return the sum'}:
            return 'sum'
        if low in {'count','count them','count the values','return the count'}:
            return 'count'
        if low in {'sort ascending','sort descending','remove duplicates','return values','return the values'}:
            return low
        raise Unclear('I cannot preserve this entire operation: '+clause+'. Specify an explicit supported step; no code was emitted.')
    if domain == 'text':
        if low in {'split text into lines','split the text into lines','split into lines','split lines'}:
            return 'split lines'
        if low in {'split text into words','split the text into words','split into words','split words'}:
            return 'split words'
        if low in {'trim each value','strip each value','trim each line','strip each line','trim each string'}:
            return 'strip each value'
        if low in {'remove empty strings','drop empty strings','remove empty lines','keep nonempty strings'}:
            return 'keep nonempty values'
        if low in {'lowercase each value','lowercase each word','casefold each value','casefold each word'}:
            return 'casefold each value' if low.startswith('casefold') else 'lowercase each value'
        if low in {'count each word','count each value','count occurrences of each word'}:
            return 'count by x'
        if re.fullmatch(r'(?i)(?:join with|split on)\s+.+', t):
            # The existing literal parser validates the separator.
            return t
        if low in {'count','count the values','return the count'}:
            return 'count'
        raise Unclear('I cannot preserve this entire text operation: '+clause+'. No code was emitted.')
    match = re.fullmatch(r'(?i)(?:keep|filter) records where ('+FIELD+r') is (true|false)', t)
    if match:
        return 'keep where x['+repr(match[1])+'] == '+match[2].title()
    match = re.fullmatch(r'(?i)(?:keep|filter) records where ('+FIELD+r') (?:is )?(greater than|less than|equals?) ('+INT+r')', t)
    if match:
        comparator = {'greater than':'>','less than':'<','equal':'==','equals':'=='}[match[2].lower()]
        return 'keep where x['+repr(match[1])+'] '+comparator+' '+match[3]
    match = re.fullmatch(r'(?i)sum ('+FIELD+r') by ('+FIELD+r')', t)
    if match:
        return 'sum x['+repr(match[1])+'] by x['+repr(match[2])+']'
    match = re.fullmatch(r'(?i)(group|count) (?:records )?by ('+FIELD+r')', t)
    if match:
        return match[1].lower()+' by x['+repr(match[2])+']'
    match = re.fullmatch(r'(?i)sort(?: records)? by ('+FIELD+r') (ascending|descending)', t)
    if match:
        return 'sort by x['+repr(match[1])+'] '+match[2].lower()
    if low in {'count','count them','count the records','return the count'}:
        return 'count'
    if low in {'return records','return the records'}:
        return 'return records'
    raise Unclear('I cannot preserve this entire record operation: '+clause+'. No code was emitted.')


def prepare(text, override=None):
    if len(text)>10000 or '```' in text:
        raise Unclear('Use a short prose collection workflow and optional literal Input: line.')
    markers = list(re.finditer(r'(?im)^\s*input\s*:\s*', text))
    if len(markers)>1:
        raise Unclear('Provide at most one Input: line.')
    header = text[:markers[0].start()].strip() if markers else text.strip()
    match = HEAD.fullmatch(header)
    if not match:
        raise Unclear('Start with Write a Python function named name that followed by the operations.')
    name, prose = match.groups()
    if re.search(r'(?i)\b(?:recursive|recursion|async|in[- ]place|without|do not|numpy|pandas|files?|network|except|unless)\b', prose):
        raise Unclear('I cannot verify those implementation constraints or exceptions with this workflow compiler. No code was emitted.')
    raw = override if override is not None else text[markers[0].end():].strip() if markers else None
    value = data_tools.literal(raw) if raw is not None else data_tools.MISSING
    parts = split_steps(prose)
    first = parts[0].lower()
    domain = 'records' if re.search(r'\brecords\b', first) else 'text' if re.search(r'\btext|lines|words|strings\b', first) else 'numbers'
    clauses = [operation(part, domain) for part in parts]
    heading = 'integer lists' if domain=='numbers' else domain
    request = 'Build a Python tool named '+(name or 'process_values')+' for '+heading+'.\nSteps:\n'+'\n'.join(clauses)
    if value is not data_tools.MISSING:
        request += '\nUse it on '+repr(value)
    compiler = task_tools if domain=='numbers' else data_tools
    plan = compiler.parse(request)
    if plan is None:
        raise Unclear('This workflow could not be represented by the selected compiler.')
    return plan, compiler.build(plan), parts, domain


def reply(text, messages=None):
    if not interested(text, messages):
        return None
    previous = current_request(text, messages)
    applied = FOLLOW.fullmatch(text) if previous else None
    details = ('Authored natural-language clauses compiled in order into the existing symbolic Python plan compiler. '
               'Every clause must be supported in full. Generated code checked against the plan in the bounded AST VM; '
               'checks do not prove interpretation of arbitrary prose. No native user-code execution, external model, '
               'file/network access or persistent tool installation.')
    out = lambda response, suffix: dict(response=response, route='chat/code-natural-'+suffix, sources=[], details=details)
    try:
        plan, result, parts, domain = prepare(previous or text, applied[1] if applied else None)
    except (ValueError, TypeError, SyntaxError, RecursionError) as error:
        return out(str(error), 'clarify')
    except Unsupported:
        return out('That workflow exceeded the supported compiler/interpreter budget. No successful function is claimed.', 'unsupported')
    if result['status']!='built':
        return out(result['message'], result['status'])
    has_input = applied is not None or bool(re.search(r'(?im)^\s*input\s*:', previous or text))
    response = PREFIX+'`'+plan['name']+'`.\nPlan: '+' → '.join(parts)+'.\n\n```python\n'+result['source']+'```'
    if has_input:
        response += '\nResult on the supplied input:\n```text\n'+repr(result['value'])+'\n```'
    response += '\nChecked compilation against the ordered plan. You can use it on another literal input in this conversation.'
    return attach(out(response,'built'), plan['name'], result['source'], domain,
                  dict(probes=result['probes'], examples=len(plan['cases'])), has_input, result['value'])
