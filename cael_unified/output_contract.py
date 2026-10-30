"""Compose a standalone presentation instruction with an unchanged task body."""
import re


def style(line):
    text = line.strip().rstrip('.!').strip()
    text = re.sub(r'(?i)^please\s+', '', text)
    if re.fullmatch(r'(?i)(?:reply|respond|answer|return|give)(?: with| me)? (?:only|just) (?:with )?(?:(?:the|a) )?(?:number|numeric result|result|answer)(?: only)?', text) or re.fullmatch(r'(?i)(?:reply|respond|answer|return|give)(?: with| me)? (?:(?:the|a) )?(?:number|numeric result|result|answer) only', text):
        return 'number'
    if re.fullmatch(r'(?i)(?:reply|respond|answer|return|give)(?: with| me)? (?:only|just) (?:the )?(?:choice )?letter(?: only)?', text) or re.fullmatch(r'(?i)(?:reply|respond|answer|return|give)(?: with| me)? (?:the )?(?:choice )?letter only', text):
        return 'letter'
    if re.fullmatch(r'(?i)(?:answer|reply|respond) briefly|keep (?:it|the answer|your answer|your reply) (?:short|brief)|no explanation', text):
        return 'brief'
    marked = re.fullmatch(r'(?i)(?:finish|end)(?: your (?:reply|response|answer))? with (?:the label )?answer\s*:\s*(.+)', text)
    if marked:
        hint = marked[1].strip()
        if re.fullmatch(r'(?i)<(?:answer|number|result)>', hint) or re.fullmatch(r'[A-H](?:\s*,\s*[A-H])+(?:\s*,?\s*or\s*[A-H])?', hint):
            return 'marker'
    return None


def read(text):
    if not isinstance(text, str) or len(text) > 12000 or any(q in text for q in ('```', '"""', "'''")):
        return None
    lines = text.strip().splitlines()
    if len(lines) > 1:
        first, last = style(lines[0]), style(lines[-1])
        if first or last:
            if first and last and first != last:
                return dict(kind='conflict', body=text)
            body = '\n'.join(lines[1:] if first else lines[:-1]).strip()
            if not body or re.search(r'(?i)\b(?:quote|quoted|says|said|phrase|sentence|example)\b[^\n]*:\s*$', body):
                return None
            return dict(kind=first or last, body=body)
    # Same-line instructions must form a separate final sentence. Earlier task
    # clauses, numbers, options, exclusions and quoted literals stay untouched.
    match = re.fullmatch(r'(?s)(.+[?.!])\s+([^\n]{1,130})', text.strip())
    if match and style(match[2]):
        return dict(kind=style(match[2]), body=match[1].strip())
    return None


def value(answer):
    first = str(answer.get('response', '')).split('\n', 1)[0].strip(' *`')
    choice = answer.get('choice')
    if type(choice) is int and 0 <= choice < 26:
        return chr(65+choice), 'letter'
    if answer.get('route', '').startswith(('chat/choice-', 'chat/reasoning-choice', 'helper/choice')):
        match = re.match(r'^([A-H])[.)\s]', first)
        if match:
            return match[1], 'letter'
    if answer.get('exact') or answer.get('route', '').startswith('helper/'):
        reasoning=answer.get('helper_reasoning',{})
        if answer.get('exact') and reasoning.get('exact') and re.fullmatch(r'-?\d+(?:\.\d+)?(?:/\d+)?',str(reasoning.get('value',''))):
            return str(reasoning['value']), 'number'
        candidate = first.rsplit(' = ', 1)[-1].replace('**', '').strip(' .*`')
        if re.fullmatch(r'-?\d+(?:\.\d+)?(?:/\d+)?', candidate):
            return candidate, 'number'
        if answer.get('route') in ('helper/conversion', 'helper/quantity-conversion'):
            converted = re.fullmatch(r'(-?\d+(?:\.\d+)?(?:/\d+)?)\s+([a-zA-Z]+)', candidate)
            if converted:
                from .helper import unit_key
                if unit_key(converted[2]):
                    return converted[1], 'number'
    return None, None


def apply(answer, contract):
    result = dict(answer)
    scalar, kind = value(answer)
    original = str(answer.get('response', ''))
    if contract['kind'] in ('number', 'letter'):
        if scalar is not None and kind == contract['kind']:
            result['response'] = scalar
        else:
            result['format_unavailable'] = 'No reliable '+contract['kind']+' was supplied by the selected solver; preserve its honest answer.'
    elif contract['kind'] == 'marker':
        final = scalar if scalar is not None else original.split('\n', 1)[0].strip(' *`')
        result['response'] = original.rstrip()+'\n\nAnswer: '+final
    elif contract['kind'] == 'brief':
        result['response'] = original.split('\n\n', 1)[0]
    result.update(output_contract=contract['kind'], understood_as=contract['body'])
    return result
