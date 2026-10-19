"""Exact constant-rate adapter for complete, explicitly typed authored frames.

No rate, starting balance or constancy is inferred. No learned/neural inference,
provider calls, evaluation answers, code execution or persistent user state.
"""
from fractions import Fraction
import re

from .helper import UNITS, unit_key as measure_key
from .helper_quantities import fmt, unit_key as count_key
from .helper_groups import label, WHY

N = r'-?\d{1,8}(?:\.\d{1,4})?'
A = r"[A-Za-z][A-Za-z'\-]{0,30}"
SUBJECT = r'(?:(?:the|a|an)\s+' + A + r'(?:\s+' + A + r')?|' + A + r')'
VERBS = {'travels': 'travel', 'moves': 'move', 'runs': 'run', 'prints': 'print',
         'produces': 'produce', 'pumps': 'pump', 'delivers': 'deliver',
         'flows': 'flow', 'processes': 'process', 'fills': 'fill'}
VERB = '(?:' + '|'.join(VERBS) + '|' + '|'.join(VERBS.values()) + ')'
COUNTS = {'page', 'label', 'widget', 'part', 'bottle', 'apple', 'marble', 'box'}
ABBREVIATIONS = {'mm', 'cm', 'm', 'km', 'ft', 'mg', 'g', 'kg', 'ml'}
ALIASES = {'s': 'second', 'sec': 'second', 'min': 'minute', 'hr': 'hour',
           'l': 'liter', 'milliliter': 'ml', 'millilitre': 'ml',
           'metre': 'meter', 'kilometre': 'kilometer', 'centimetre': 'centimeter',
           'millimetre': 'millimeter'}
RATE_CUE = re.compile(r'(?i)\bat\s+(?:an?\s+)?(?:(?:constant|average|variable|changing)\s+)?(?:rate|speed)\s+of\b')
QUESTION = re.compile(r'(?i)\bhow (?:many|much|long|far)\b')
FRAME = re.compile(r'(?P<subject>' + SUBJECT + r')\s+(?P<verb>' + VERB + r')\s+at\s+a\s+constant\s+(?P<kind>rate|speed)\s+of\s+(?P<rate>' + N + r')\s+(?P<unit>[A-Za-z]+)\s*(?:per\s+|/\s*)(?P<base>[A-Za-z]+)(?:\s+for\s+(?P<duration>' + N + r')\s+(?P<duration_unit>[A-Za-z]+))?', re.I)
AMOUNT_Q = re.compile(r'how (?:many|much)\s+(?P<unit>[A-Za-z]+)\s+(?:does|do)\s+(?P<subject>' + SUBJECT + r')\s+(?P<verb>' + VERB + r')(?:\s+in total)?', re.I)
TIME_Q = re.compile(r'how many\s+(?P<unit>[A-Za-z]+)\s+(?:does|do)\s+(?P<subject>' + SUBJECT + r')\s+(?:need|take)\s+to\s+(?P<verb>' + VERB + r')\s+(?P<amount>' + N + r')\s+(?P<amount_unit>[A-Za-z]+)', re.I)


class Unclear(ValueError):
    pass


def clarify(message):
    return dict(route='helper/rates-clarify', response=message, sources=[],
                details='No numeric answer was guessed. Explicit constant-rate grammar only; no network request.')


def actor(text):
    value = re.sub(r'(?i)^(?:a|an|the)\s+', '', text).lower()
    if value in ('he', 'she', 'they', 'it', 'you', 'someone', 'somebody', 'nobody'):
        raise Unclear('Use the same explicit name or machine in the rate and question.')
    return value


def action(verb):
    return VERBS.get(verb.lower(), verb.lower())


def unit(text):
    token = text.lower()
    alias = ALIASES.get(token) or (ALIASES.get(token[:-1]) if token.endswith('s') else None)
    key = measure_key(text) or alias
    if key:
        dimension, factor = UNITS[key]
        return dict(key=key, dimension=dimension, factor=factor, count=False)
    key = count_key(text)
    if key in COUNTS:
        return dict(key=key, dimension='count:' + key, factor=Fraction(1), count=True)
    raise Unclear('Use a supported measurement unit or explicit page, label, widget, part, bottle, apple, marble or box count.')


def display(data, value):
    key = data['key']
    if key in ABBREVIATIONS:
        return key
    return label({'feet': 'foot', 'inches': 'inch'}.get(key, key), value)


def number(text):
    value = Fraction(text)
    if value < 0:
        raise Unclear('Use non-negative rates, durations and requested amounts.')
    return value


def candidate(text):
    return (len(text) <= 1000 and bool(re.search(r'\d', text))
            and bool(RATE_CUE.search(text)) and bool(QUESTION.search(text))
            and not re.search(r'(?i)\b(?:python|javascript|function|script|code|program)\b|```', text))


def solve(text, explain=False):
    if not candidate(text):
        return None
    try:
        questions = list(QUESTION.finditer(text))
        if len(questions) != 1:
            raise Unclear('Ask one quantity question about a single explicit constant rate.')
        context = text[:questions[0].start()].strip(' .;\n:')
        context = re.sub(r'(?i)^(?:facts|given|scenario|context)\s*:\s*', '', context)
        question = text[questions[0].start():].strip(' .?\n')
        match = FRAME.fullmatch(context)
        if not match:
            raise Unclear('State one explicit constant rate or speed, its units per time unit, and one duration or target amount. Extra events, stops and changing rates are outside this helper.')
        rate = number(match['rate'])
        amount_unit, base = unit(match['unit']), unit(match['base'])
        if base['dimension'] != 'time' or amount_unit['dimension'] == 'time':
            raise Unclear('The rate must give an amount per time unit, such as liters per minute or kilometers per hour.')
        if match['kind'].lower() == 'speed' and amount_unit['dimension'] != 'length':
            raise Unclear('A speed needs a distance unit per time unit.')
        owner = actor(match['subject'])
        query = TIME_Q.fullmatch(question) or AMOUNT_Q.fullmatch(question)
        if not query or actor(query['subject']) != owner or action(query['verb']) != action(match['verb']):
            raise Unclear('Ask about the same explicit subject and action as the stated rate; a starting balance or different action cannot be inferred.')
        target = unit(query['unit'])
        steps = [f'Stated constant rate: {fmt(rate)} {display(amount_unit, rate)} per {display(base, 1)}.']
        if 'amount' in query.groupdict():
            if match['duration'] is not None or target['dimension'] != 'time':
                raise Unclear('For a time question, give one target amount and request a time unit, without an additional duration.')
            amount = number(query['amount'])
            source = unit(query['amount_unit'])
            if source['dimension'] != amount_unit['dimension']:
                raise Unclear('The target amount must have the same dimension or item type as the rate.')
            if not rate:
                raise Unclear('A zero rate does not determine a completion time; division by zero is undefined.')
            if source['count'] and amount.denominator != 1:
                raise Unclear('State a whole completed-item target; a fraction of a finished item is ambiguous.')
            normalized = amount * source['factor'] / amount_unit['factor']
            elapsed = normalized / rate
            value = elapsed * base['factor'] / target['factor']
            steps.extend([f'Target conversion: {fmt(amount)} {display(source, amount)} = {fmt(normalized)} {display(amount_unit, normalized)}.',
                          f'Time = {fmt(normalized)} {display(amount_unit, normalized)} / ({fmt(rate)} {display(amount_unit, rate)}/{display(base, 1)}) = {fmt(elapsed)} {display(base, elapsed)}.',
                          f'Time conversion: {fmt(elapsed)} {display(base, elapsed)} = {fmt(value)} {display(target, value)}.'])
            kind = 'duration'
        else:
            if match['duration'] is None:
                raise Unclear('State the duration at that constant rate before asking for the delivered or travelled amount.')
            if target['dimension'] != amount_unit['dimension']:
                raise Unclear('The requested amount must have the same dimension or item type as the stated rate.')
            duration = number(match['duration'])
            duration_unit = unit(match['duration_unit'])
            if duration_unit['dimension'] != 'time':
                raise Unclear('The duration must be a time quantity, such as seconds, minutes or hours.')
            elapsed = duration * duration_unit['factor'] / base['factor']
            produced = rate * elapsed
            value = produced * amount_unit['factor'] / target['factor']
            if target['count'] and value.denominator != 1:
                raise Unclear('That rate and duration imply a fractional item. Specify how completion or partial items are counted; I will not round a finished-item count.')
            steps.extend([f'Duration conversion: {fmt(duration)} {display(duration_unit, duration)} = {fmt(elapsed)} {display(base, elapsed)}.',
                          f'Amount = {fmt(rate)} {display(amount_unit, rate)}/{display(base, 1)} * {fmt(elapsed)} {display(base, elapsed)} = {fmt(produced)} {display(amount_unit, produced)}.',
                          f'Amount conversion: {fmt(produced)} {display(amount_unit, produced)} = {fmt(value)} {display(target, value)}.'])
            kind = 'amount'
        response = f'{fmt(value)} {display(target, value)} at the stated constant {match["kind"].lower()}.'
        if explain:
            response += '\n\nSteps:\n' + '\n'.join(f'{i + 1}. {step}' for i, step in enumerate(steps))
        return dict(route='helper/rates', response=response, sources=[], exact=True,
                    details='Authored exact typed constant-rate parser. Only the stated interval or target is calculated; no starting balance is assumed. No network or neural model.\n' + '\n'.join(steps),
                    helper_reasoning=dict(value=fmt(value), unit=target['key'], kind=kind, steps=steps, exact=True))
    except (Unclear, ValueError, ZeroDivisionError) as error:
        return clarify(str(error))


def prepared(text):
    from .helper_chat import clean_request
    text = clean_request(text)
    explicit = bool(re.match(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+', text))
    if explicit:
        text = re.sub(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+', '', text)
    return text, explicit


def reply(text, messages=None, explain=False):
    if not WHY.fullmatch(text):
        return solve(text, explain)
    state, relevant = None, False
    for i in range(max(0, len(messages or []) - 19), len(messages or []) - 1):
        entry = messages[i]
        if entry.get('role') != 'user':
            continue
        request, explicit = prepared(entry['content'])
        if WHY.fullmatch(request):
            expected = solve(state, True) if state else None
        else:
            relevant = candidate(request)
            expected = solve(request, explicit)
            state = request if expected and expected['route'] == 'helper/rates' else None
        if (not expected or i + 1 >= len(messages) - 1 or messages[i + 1].get('role') != 'assistant'
                or messages[i + 1]['content'] != expected['response']):
            state = None
    if state:
        return solve(state, True)
    if relevant:
        return clarify('Please restate the complete rate problem; I cannot verify a rate calculation in this conversation to explain.')
    return None
