"""Bounded typed equal-groups/sharing helper; exact integer/rational arithmetic.

Only complete authored grammar frames execute. No learned answer, eval, network,
or persistent user state. Whole-item versus fractional sharing is explicit.
"""
from fractions import Fraction
import re

from .helper import UNITS, unit_key as measure_key
from .helper_quantities import unit_key, fmt

N = r'-?\d{1,8}(?:\.\d{1,4})?'
A = r"[A-Za-z][A-Za-z'\-]{0,30}"
U = r'[A-Za-z]+(?:\s+[A-Za-z]+)?'
LEAD = r'(?:(?P<owner>' + A + r')\s+(?:has|have|had|owns|owned)|there\s+(?:is|are|were))\s+'
WHY = re.compile(r'(?i)^(?:why|explain(?: that| this| your answer| the answer)?|show(?: me)? (?:the )?(?:steps|working)|how did you (?:get|calculate|work out) that)[?.!]*$')
CHOICE = re.compile(r'(?i)^(?:whole(?: items| ones| shares)?|no cutting|without cutting|allow fractions|fractional shares|fractions)(?: please)?[.!]*$')
BAD_UNIT = re.compile(r'(?i)\b(?:more|less|fewer|than|each|per|every|not|no|to|from|and|or|now|left|remaining|with|of|among|between|total|altogether|equally)\b')
MONEY = {'dollar', 'euro', 'pound', 'yen', 'rupee', 'cent', 'penny', 'nickel', 'dime', 'quarter'}


class Unclear(ValueError):
    pass


def item_unit(text):
    whole = bool(re.match(r'(?i)^whole\s+', text))
    text = re.sub(r'(?i)^whole\s+', '', text).strip()
    if not re.fullmatch(U, text) or BAD_UNIT.search(text):
        raise Unclear('Specify one item type and one group type, using the same units in the question.')
    key = unit_key(text)
    if key in MONEY:
        raise Unclear('Use an explicit arithmetic expression for money or prices; this helper counts stated contents.')
    return key, whole


def label(key, value):
    words = key.split()
    noun = words[-1]
    if value != 1:
        irregular = {'person': 'people', 'child': 'children', 'mouse': 'mice', 'foot': 'feet'}
        if noun in irregular:
            noun = irregular[noun]
        elif noun in ('fish', 'sheep', 'deer'):
            pass
        elif re.search(r'[^aeiou]y$', noun):
            noun = noun[:-1] + 'ies'
        elif noun.endswith(('s', 'x', 'z', 'ch', 'sh')):
            noun += 'es'
        else:
            noun += 's'
    return ' '.join(words[:-1] + [noun])


def quantity(raw, groups=False):
    value = Fraction(raw)
    if value < 0 or (groups and value.denominator != 1):
        raise Unclear('Group and recipient counts must be non-negative whole numbers; amounts cannot be negative.')
    return value


def owner_key(owner):
    if owner and owner.lower() in ('he', 'she', 'it', 'they', 'you', 'someone', 'somebody', 'each', 'every'):
        raise Unclear('Use a name or “I” for the stated groups, or use “There are …”.')
    return owner.lower() if owner else None


def clarify(message, choice=False):
    return dict(route='helper/groups-clarify', response=message, sources=[],
                details='No numeric answer was guessed. Exact groups/sharing grammar only; no internet request.',
                helper_reasoning=dict(clarification='whole_or_fractional' if choice else None))


def answer(response, value, unit, kind, steps, explain, **metadata):
    if explain:
        response += '\n\nSteps:\n' + '\n'.join(f'{i + 1}. {step}' for i, step in enumerate(steps))
    return dict(route='helper/groups', response=response, sources=[], exact=True,
                details='Authored typed groups/sharing parser with exact integer/rational arithmetic. Only the listed groups or shared batch are counted. No network or neural model.\n' + '\n'.join(steps),
                helper_reasoning=dict(value=fmt(value), unit=unit, kind=kind, steps=steps, exact=True, **metadata))


def question_unit(question):
    match = re.match(r'(?i)^how (?:many|much)\s+((?:whole\s+)?' + U + r')\s+(?=(?:does|do|are|is)\b)', question)
    if not match:
        raise Unclear('Ask one “How many [items] …?” question about the listed groups or equal shares.')
    key, whole = item_unit(match[1])
    return match, key, whole


def group_problem(context):
    packed = re.fullmatch(LEAD + r'(?P<count>' + N + r')\s+(?P<group>' + U + r')\s+(?:with|of|containing)\s+(?P<per>' + N + r')\s+(?P<item>(?:whole\s+)?' + U + r')\s+each', context, re.I)
    each_of = re.fullmatch(r'each of\s+(?P<count>' + N + r')\s+(?P<group>' + U + r')\s+(?:has|contains|holds)\s+(?P<per>' + N + r')\s+(?P<item>(?:whole\s+)?' + U + r')', context, re.I)
    if packed or each_of:
        data = (packed or each_of).groupdict()
        data.setdefault('owner', None)
        return data
    clauses = [part.strip() for part in re.split(r'(?<!\d)\.|\.(?!\d)|[;\n]+', context) if part.strip()]
    if len(clauses) == 2:
        for first, second in (clauses, clauses[::-1]):
            stock = re.fullmatch(LEAD + r'(?P<count>' + N + r')\s+(?P<group>' + U + r')', first, re.I)
            content = re.fullmatch(r'each\s+(' + U + r')\s+(?:has|contains|holds)\s+(' + N + r')\s+((?:whole\s+)?' + U + r')', second, re.I)
            if stock and content:
                if unit_key(stock['group']) != unit_key(content[1]):
                    raise Unclear('The stated group type and the “each” group type do not match.')
                return dict(stock.groupdict(), per=content[2], item=content[3])
    return None


def solve(text, mode=None, explain=False):
    if len(text) > 1000 or re.search(r'(?i)\b(?:python|javascript|function|script|code|program)\b|```', text):
        return None
    if not re.search(r'\d', text) or not re.search(r'(?i)\b(?:each|equally|among|between)\b', text):
        return None
    grouped_frame = re.search(r'(?i)\b' + N + r'\s+' + U + r'\s+(?:with|of|containing)\s+' + N + r'\b|\beach of\s+' + N + r'\b|\beach\s+' + U + r'\s+(?:has|contains|holds)\s+' + N + r'\b', text)
    sharing_frame = re.search(r'(?i)\b(?:shares?|shared|splits?|split|divides?|divided)\s+' + N + r'\b.*\b(?:among|between|into)\s+' + N + r'\b', text)
    if not grouped_frame and not sharing_frame:
        return None
    questions = list(re.finditer(r'(?i)\bhow (?:many|much)\b', text))
    if not questions:
        return None
    if len(questions) != 1:
        return clarify('Ask one quantity question at a time about the stated groups or equal shares.')
    context = text[:questions[0].start()].strip(' .;\n:')
    context = re.sub(r'(?i)^(?:facts|given|scenario|context)\s*:\s*', '', context)
    context = re.sub(r'(?i)(?:question|query)\s*:\s*$', '', context).strip(' .;\n')
    question = text[questions[0].start():].strip(' .?\n')
    try:
        if re.search(r"(?i)\b(?:not|never|no|unless|if|either|or|maybe|might|could|about|approximately|at least|at most|didn['’]t|doesn['’]t|don['’]t)\b", context):
            raise Unclear('State exact, unconditional quantities and equal groups before asking for a definite result.')
        packed = group_problem(context)
        if packed:
            owner = owner_key(packed['owner'])
            groups = quantity(packed['count'], groups=True)
            per = quantity(packed['per'])
            group, group_whole = item_unit(packed['group'])
            item, item_whole = item_unit(packed['item'])
            if group == item:
                raise Unclear('Use distinct group and contents units, such as boxes and apples.')
            if item_whole and per.denominator != 1:
                raise Unclear('The stated whole-item quantity is fractional. Check the contents of each group.')
            match, asked, asked_whole = question_unit(question)
            tail = question[match.end():]
            tail = re.sub(r'(?i)\s+(?:in total|altogether|in all)$', '', tail)
            generic = re.fullmatch(r'(?i)(?:are|is) there', tail)
            owned = re.fullmatch(r'(?i)(?:does|do)\s+(' + A + r')\s+have', tail)
            if not generic and not owned:
                raise Unclear('Ask how many items are in all the listed groups; subsets and later events need explicit separate wording.')
            if owned and (not owner or owned[1].lower() != owner):
                raise Unclear('The person in the question does not match the stated groups.')
            if asked not in (item, group):
                raise Unclear('The question asks for an item type that was not stated.')
            if asked_whole and asked == item and per.denominator != 1:
                raise Unclear('State whether fractional contents can be combined into whole items before counting whole pieces.')
            value = groups * per if asked == item else groups
            steps = [f'Stated groups: {fmt(groups)} {label(group, groups)}.',
                     f'Contents per group: {fmt(per)} {label(item, per)}/{group}.',
                     f'{fmt(groups)} {label(group, groups)} * {fmt(per)} {label(item, per)}/{group} = {fmt(groups * per)} {label(item, groups * per)}.']
            response = f'{fmt(value)} {label(asked, value)} in the listed {fmt(groups)} {label(group, groups)}.' if asked == item else f'{fmt(groups)} {label(group, groups)} {"is" if groups == 1 else "are"} listed.'
            return answer(response, value, asked, 'group_total' if asked == item else 'group_count', steps, explain,
                          group_unit=group, groups=fmt(groups), per_group=fmt(per), scope='listed groups')

        shared = re.fullmatch(r'(?:(?P<owner>' + A + r')\s+)?(?:shares?|shared|splits?|split|divides?|divided)\s+(?P<amount>' + N + r')\s+(?P<item>(?:whole\s+)?' + U + r')\s+equally\s+(?:among|between|into)\s+(?P<count>' + N + r')\s+(?P<recipient>' + U + r')', context, re.I)
        if not shared:
            raise Unclear('Use one complete equal-groups or sharing problem without additional events, or write an arithmetic expression.')
        owner_key(shared['owner'])
        amount = quantity(shared['amount'])
        count = quantity(shared['count'], groups=True)
        if not count:
            raise Unclear('Equal sharing needs at least one recipient; division by zero is undefined.')
        item, whole = item_unit(shared['item'])
        recipient, recipient_whole = item_unit(shared['recipient'])
        if recipient_whole or recipient == item:
            raise Unclear('Use a distinct recipient/group type and item type.')
        match, asked, requested_whole = question_unit(question)
        if asked != item:
            raise Unclear('The question must ask for the same item type as the shared amount.')
        tail = question[match.end():]
        each = re.fullmatch(r'(?i)(?:does|do) each\s+(' + U + r')\s+(?:get|receive)', tail)
        leftover = bool(re.fullmatch(r'(?i)(?:are|is) (?:left over|leftover|remaining)', tail))
        if not each and not leftover:
            raise Unclear('Ask what each stated recipient gets, or what is left over from the shared batch; the giver’s total inventory is not established.')
        if each and unit_key(each[1]) != recipient:
            raise Unclear('The recipient type in the question does not match the stated equal shares.')
        mode = 'whole' if whole or requested_whole else mode
        share = amount / count
        measured = measure_key(item)
        measured = bool(measured and UNITS[measured][0] in ('length', 'mass', 'volume', 'time'))
        if not mode and share.denominator != 1 and not measured:
            return clarify(f'Should I keep whole {label(item, 2)} with leftovers, or allow fractional shares?', choice=True)
        if mode == 'whole' and amount.denominator != 1:
            raise Unclear('The total number of whole items must be a non-negative integer.')
        remainder = amount - (amount // count) * count if mode == 'whole' else Fraction(0)
        if mode == 'whole':
            share = Fraction(amount // count)
        steps = [f'{fmt(amount)} {label(item, amount)} / {fmt(count)} {label(recipient, count)} = {fmt(share)} {label(item, share)}/{recipient}' + (f', remainder {fmt(remainder)} {label(item, remainder)}.' if mode == 'whole' else '.')]
        if mode == 'whole':
            steps.append(f'Check: {fmt(count)} * {fmt(share)} + {fmt(remainder)} = {fmt(amount)} {label(item, amount)}.')
        value = remainder if leftover else share
        response = f'{fmt(remainder)} {label(item, remainder)} {"is" if remainder == 1 else "are"} left over from the listed batch.' if leftover else f'Each {recipient} gets {fmt(share)} {label(item, share)}.'
        if mode == 'whole' and not leftover:
            response = response[:-1] + f'; {fmt(remainder)} {label(item, remainder)} {"is" if remainder == 1 else "are"} left over.'
        return answer(response, value, item, 'remainder' if leftover else 'equal_share', steps, explain,
                      total=fmt(amount), recipients=fmt(count), recipient_unit=recipient, remainder=fmt(remainder),
                      sharing_mode=mode or ('measured' if measured else 'equal'), scope='listed shared batch')
    except (Unclear, ValueError, ZeroDivisionError) as error:
        return clarify(str(error))


def prepared(text):
    from .helper_chat import clean_request
    text = clean_request(text)
    explicit = bool(re.match(r'(?i)^(?:explain|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+', text))
    if explicit:
        text = re.sub(r'(?i)^(?:explain|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+', '', text)
    return text, explicit


def verified_state(messages):
    state = None
    for i in range(max(0, len(messages) - 19), len(messages) - 1):
        entry = messages[i]
        if entry.get('role') != 'user' or i + 1 >= len(messages) - 1 or messages[i + 1].get('role') != 'assistant':
            continue
        if len(entry['content']) > 1200:
            state = None
            continue
        text, explained = prepared(entry['content'])
        if WHY.fullmatch(text) and state:
            expected = solve(state['request'], state['mode'], explain=True)
        elif CHOICE.fullmatch(text) and state and state['result'].get('helper_reasoning', {}).get('clarification') == 'whole_or_fractional':
            state['mode'] = 'fractional' if re.search(r'(?i)fractions|fractional', text) else 'whole'
            expected = solve(state['request'], state['mode'], explained)
        else:
            expected = solve(text, explain=explained)
            state = dict(request=text, mode=None) if expected else None
        if not expected or expected['response'] != messages[i + 1]['content']:
            state = None
        elif state:
            state['result'] = expected
    return state


def reply(text, messages=None, explain=False):
    if WHY.fullmatch(text) or CHOICE.fullmatch(text):
        state = verified_state(messages) if messages else None
        if state and WHY.fullmatch(text):
            return solve(state['request'], state['mode'], explain=True)
        if CHOICE.fullmatch(text):
            if not state or state['result'].get('helper_reasoning', {}).get('clarification') != 'whole_or_fractional':
                return clarify('Please restate the equal-sharing problem before choosing whole items or fractional shares.')
            mode = 'fractional' if re.search(r'(?i)fractions|fractional', text) else 'whole'
            return solve(state['request'], mode, explain)
        return None
    return solve(text, explain=explain)
