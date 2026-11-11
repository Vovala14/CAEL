"""User-grounded conversations over finite constraints and action models.

Every supported line is compiled in full; history is reconstructed from user
statements only. Assistant prose is never a rule, an executed action or proof.
The controlled English surface is deliberately finite, with a literal data API.
"""
import ast
import copy
import hashlib
import json
import re
from . import finite_constraints as fc
from . import world_reasoning as wr

ID = r'[A-Za-z_][A-Za-z_0-9]{0,39}'
RESET = re.compile(r'(?i)^(?:reset|clear|forget|start a new) (?:the |this )?(?:problem|puzzle|planning task)[.!?]*$')
WHY = re.compile(r'(?i)^(?:why|why is that|explain(?: (?:that|this|the answer|your answer|the plan))?|show (?:the |your )?(?:reasoning|steps|working))[.!?]*$')
HINT = re.compile(r'(?i)^(?:give (?:me )?(?:a |one )?hint|just (?:a |one )?hint|hint)[.!?]*$')
SOCIAL = re.compile(r'(?i)^(?:thanks|thank you|ok|okay|great|got it|that helps|nice)[.!]*$')


def clean(text):
    return text.strip().rstrip('.?!').strip()


def values(text):
    """Explicit values or a small inclusive integer range; never execute text."""
    text = text.strip()
    match = re.fullmatch(r'(-?\d{1,7})\s*\.\.\s*(-?\d{1,7})', text)
    if match:
        a, b = map(int, match.groups())
        if not 0 <= b-a < 32:
            raise fc.Unclear('An inclusive domain range needs 1 to 32 values in increasing order.')
        return list(range(a, b+1))
    # A single literal list also permits commas inside quoted labels.
    if text.startswith('['):
        try:
            result = ast.literal_eval(text)
        except (ValueError, SyntaxError, RecursionError):
            raise fc.Unclear('The domain list is not a complete literal list.')
        if type(result) is not list:
            raise fc.Unclear('Use a literal list of scalar domain values.')
        return result
    parts = text.split(',')
    if not 1 <= len(parts) <= 32:
        raise fc.Unclear('Give a bounded comma-separated domain or literal list.')
    return [atom(p.strip(), {}) for p in parts]


def atom(text, current):
    if text.lower() in ('true', 'false'):
        return text.lower() == 'true'
    if re.fullmatch(r'-?\d{1,7}', text):
        return int(text)
    if re.fullmatch(ID, text):
        return text
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError, RecursionError):
        raise fc.Unclear('Use an explicit bounded literal value, not an omitted condition.')
    if not fc.literal(value):
        raise fc.Unclear('Only bounded integer, Boolean and text values are admitted.')
    return value


def identifiers(text):
    names = [n.strip() for n in text.split(',')]
    if not 1 <= len(names) <= 16 or len(set(names)) != len(names) or any(not re.fullmatch(ID, n) or n in fc.RESERVED for n in names):
        raise fc.Unclear('Declare 1 to 16 distinct variable identifiers.')
    return names


def term(text, domains):
    text = text.strip()
    if text in domains:
        if any(type(v) is str and v == text for d in domains.values() for v in d):
            raise fc.Unclear('A name denotes both a variable and value; quote the literal value explicitly.')
        return text
    value = atom(text, {})
    if type(value) is str and not (text.startswith(('"', "'")) or any(value in d for d in domains.values())):
        raise fc.Unclear('The relation names an undeclared variable or value: ' + text + '.')
    return repr(value)


def expression(text, domains):
    text = clean(text)
    match = re.fullmatch(r'(?i)all (?:different|distinct)(?:\s*:\s*(.+))?', text)
    if match:
        names = identifiers(match[1]) if match[1] else list(domains)
        if not set(names) <= set(domains):
            raise fc.Unclear('All-different names an undeclared variable.')
        return 'all_different(' + ','.join(names) + ')'
    relation = re.fullmatch('(' + ID + r')\s+(?:is |comes |must be )?(immediately before|immediately after|before|after|adjacent to|next to)\s+(' + ID + ')', text, re.I)
    if relation:
        a, op, b = relation.groups()
        if a not in domains or b not in domains:
            raise fc.Unclear('The ordering relation uses an undeclared variable.')
        if op.lower() in ('adjacent to', 'next to'):
            return 'abs(' + a + '-' + b + ')==1'
        return (a + '+1==' + b if op.lower() == 'immediately before' else
                b + '+1==' + a if op.lower() == 'immediately after' else
                a + '<' + b if op.lower() == 'before' else a + '>' + b)
    relation = re.fullmatch('(' + ID + r')\s+(?:is|must be)\s+(not\s+)?(?:in position\s+|equal to\s+)?(.+)', text, re.I)
    if relation:
        a, negated, b = relation.groups()
        if a not in domains:
            raise fc.Unclear('Undeclared variable: ' + a + '.')
        return a + ('!=' if negated else '==') + term(b, domains)
    text = re.sub(r'(?<![<>=!])=(?!=)', '==', text)
    fc.compile_rule(text, set(domains))
    return text


def query(text, domains):
    text = clean(text)
    if WHY.fullmatch(text):
        return dict(kind='why')
    if HINT.fullmatch(text):
        return dict(kind='hint')
    if re.fullmatch(r'(?i)(?:solve(?: it| this| the puzzle)?|find (?:a |one )?(?:solution|assignment)|what is (?:a |one )?solution)', text):
        return dict(kind='solve')
    if re.fullmatch(r'(?i)(?:show|give|what are|list) (?:me )?(?:all |the )?solutions', text):
        return dict(kind='all')
    if re.fullmatch(r'(?i)how many (?:solutions|assignments)(?: are there)?', text):
        return dict(kind='count')
    if re.fullmatch(r'(?i)(?:what|which) (?:values|variables|assignments) are (?:forced|certain|fixed)', text):
        return dict(kind='forced')
    match = re.fullmatch(r'(?i)(?:what (?:is|about)|where is|what (?:can|must)) (' + ID + r')(?: be)?', text)
    if match:
        if match[1] not in domains:
            if re.match(r'(?i)^what (?:about|can|must)\b', text):
                raise fc.Unclear('The question names an undeclared variable.')
            return None
        return dict(kind='value', name=match[1])
    match = re.fullmatch(r'(?i)who is (first|last|in position (-?\d+))', text)
    if match:
        if any(type(v) is not int for d in domains.values() for v in d):
            raise fc.Unclear('A position question requires numeric position domains.')
        position = 1 if match[1].lower() == 'first' else max(v for d in domains.values() for v in d) if match[1].lower() == 'last' else int(match[2])
        return dict(kind='occupant', position=position)
    match = re.fullmatch(r'(?is)(?:is|can) (.+?) (possible|necessary|forced|be true)', text)
    if match:
        rule = expression(match[1], domains)
        fc.compile_rule(rule, set(domains))
        return dict(kind='predicate', expression=rule, necessary=match[2].lower() in ('necessary', 'forced'))
    return None


def record(text, index, kind='rule', compiled=None):
    return dict(message=index, text=text, kind=kind, expression=compiled)


def parse_constraints(body, index):
    lines = [clean(s) for s in body.splitlines() if s.strip()]
    if not lines or len(lines) > 100:
        raise fc.Unclear('Supply a bounded declaration and every complete rule, one per line.')
    domains, records, pending, names, common = {}, [], [], None, None
    for line in lines:
        match = re.fullmatch(r'(?i)(variables|order|arrange)\s*:\s*(.+)', line)
        domain = re.fullmatch(r'(?i)domain\s+(' + ID + r')\s*:\s*(.+)', line)
        shared = re.fullmatch(r'(?i)(?:values|options)\s*:\s*(.+)', line)
        if match:
            if names is not None or domains:
                raise fc.Unclear('Do not repeat or overlap variable declarations.')
            names = identifiers(match[2])
            if match[1].lower() in ('order', 'arrange'):
                common = list(range(1, len(names)+1))
                pending.append(('All different', index))
            records.append(record(line, index, 'declaration'))
        elif domain:
            if names is not None or domain[1] in domains:
                raise fc.Unclear('Do not repeat or overlap domains; use an explicit domain update later.')
            domains[domain[1]] = values(domain[2])
            records.append(record(line, index, 'declaration'))
        elif shared:
            if common is not None:
                raise fc.Unclear('The common domain was declared twice.')
            common = values(shared[1])
            records.append(record(line, index, 'declaration'))
        else:
            pending.append((re.sub(r'(?i)^rule\s*:\s*', '', line), index))
    if names is not None:
        if common is None:
            raise fc.Unclear('Variables need an explicit Values domain.')
        domains = {n: list(common) for n in names}
    elif common is not None:
        raise fc.Unclear('A shared Values list needs Variables.')
    task = dict(domains=domains, constraints=[])
    fc.prepare(task)
    question = dict(kind='solve')
    question_seen = False
    for line, at in pending:
        q = query(line, domains)
        if q is not None:
            if question_seen:
                raise fc.Unclear('Ask one complete question per turn; none of the questions may be discarded.')
            question = q
            question_seen = True
            continue
        rule = expression(line, domains)
        task['constraints'].append(rule)
        records.append(record(line, at, compiled=rule))
    fc.prepare(task)
    return dict(kind='constraint', task=task, records=records, query=question)


def assignment(text, known=None, comparisons=False):
    result = {}
    # Literal strings with commas should use typed JSON rather than splitting.
    pieces = re.split(r'\s+and\s+|\s*,\s*', text)
    for p in pieces:
        match = re.fullmatch('(' + ID + r')\s*(==|!=|>=|<=|>|<|=)\s*(.+)', p)
        if not match or match[1] in result or known is not None and match[1] not in known:
            raise fc.Unclear('Give each declared variable once with a complete literal assignment or comparison.')
        name, op, text_value = match.groups()
        text_value = text_value.strip()
        value = dict(var=text_value) if comparisons and known is not None and text_value in known else atom(text_value, {})
        if comparisons:
            if op in ('=', '=='):
                result[name] = value
            else:
                result[name] = dict(op={'!=':'ne', '>=':'ge', '<=':'le', '>':'gt', '<':'lt'}[op], value=value)
        elif op not in ('=', '=='):
            raise fc.Unclear('A state observation requires an exact value, not an inequality.')
        else:
            result[name] = value
    if not result:
        raise fc.Unclear('No complete assignments were supplied.')
    return result


def parse_world(body, index):
    initial, goal, actions, bounds, records = None, None, [], {}, []
    for raw in body.splitlines():
        if not raw.strip():
            continue
        line = clean(raw)
        if line.lower().startswith('state:'):
            if initial is not None:
                raise fc.Unclear('State was declared twice.')
            initial = assignment(line.split(':', 1)[1].strip())
        elif line.lower().startswith('goal:'):
            if goal is not None:
                raise fc.Unclear('Goal was declared twice.')
            goal = line.split(':', 1)[1].strip()
        elif re.match(r'(?i)^domain\s+', line):
            match = re.fullmatch(r'(?i)domain (' + ID + r')\s*:\s*(.+)', line)
            if not match or match[1] in bounds:
                raise fc.Unclear('Give each complete action-state domain once.')
            bounds[match[1]] = values(match[2])
        else:
            match = re.fullmatch(r'(?i)action (' + ID + r')\s*:\s*(?:if (.+?)\s*)?->\s*(.+?)(?:;\s*cost\s*=\s*(\d+))?', line)
            if not match:
                raise fc.Unclear('Every planning line must be State, Domain, Goal or Action name: if conditions -> effects; cost=N.')
            actions.append((match.groups(), line))
        records.append(record(line, index, 'declaration'))
    if initial is None or goal is None:
        raise fc.Unclear('A planning task needs the complete State and Goal.')
    task = dict(initial=initial, goal=assignment(goal, initial, comparisons=True), actions=[], bounds=bounds)
    for (name, pre, effects, cost), raw in actions:
        changes = {}
        for item in effects.split(','):
            match = re.fullmatch(r'\s*(' + ID + r')\s*(\+=|-=|=)\s*(.+?)\s*', item)
            toggle = re.fullmatch(r'\s*(' + ID + r')\s+toggles\s*', item, re.I)
            if toggle:
                key, value = toggle[1], dict(toggle=True)
            elif match:
                key, op, operand = match.groups()
                if op in ('+=', '-='):
                    value = atom(operand, {})
                    if type(value) is not int:
                        raise fc.Unclear('A relative change needs a literal integer.')
                    value = dict(add=value if op == '+=' else -value)
                else:
                    value = dict(copy=operand) if operand in initial else dict(set=atom(operand, {}))
            else:
                raise fc.Unclear('An effect clause is unsupported; it cannot be dropped.')
            if key in changes or key not in initial:
                raise fc.Unclear('An effect repeats or references an unknown state variable.')
            changes[key] = value
        task['actions'].append(dict(name=name, pre=assignment(pre, initial, True) if pre else {},
                                    effects=changes, cost=int(cost) if cost else 1))
    return dict(kind='world', task=task, records=records, query=dict(kind='solve'), disabled=[])


def new_frame(text, index):
    if not 0 < len(text) <= 40000:
        return None
    if re.match(r'(?i)^(?:constraint puzzle|finite problem|puzzle)\s*:', text):
        return parse_constraints(text.split(':', 1)[1].strip(), index)
    if re.match(r'(?i)^(?:variables|order|arrange|domain ' + ID + r')\s*:', text):
        return parse_constraints(text, index)
    if re.match(r'(?i)^planning (?:task|problem)\s*:', text):
        return parse_world(text.split(':', 1)[1].strip(), index)
    if re.search(r'"(?:initial|domains)"\s*:', text):
        try:
            value = json.loads(text)
        except (ValueError, RecursionError):
            return None  # The established structured reader owns headers.
        if type(value) is dict and 'domains' in value:
            fc.prepare(value)
            return dict(kind='constraint', task=copy.deepcopy(value), records=[record(text, index, 'data')], query=dict(kind='solve'))
        if type(value) is dict and {'initial', 'goal', 'actions'} <= set(value):
            return dict(kind='world', task=copy.deepcopy(value), records=[record(text, index, 'data')], query=dict(kind='solve'), disabled=[])
    return None


def world_query(text):
    t = clean(text)
    if WHY.fullmatch(t):
        return dict(kind='why')
    if HINT.fullmatch(t):
        return dict(kind='hint')
    if re.fullmatch(r'(?i)(?:what (?:is |should I do )?(?:the )?next(?: step| move| action)?|next(?: step| move| action))', t):
        return dict(kind='next')
    if re.fullmatch(r'(?i)(?:what (?:is|about) (?:the )?(?:state|goal)|where are we(?: now)?)', t):
        return dict(kind='state')
    if re.fullmatch(r'(?i)(?:solve(?: it| this)?|replan|what now|find (?:a |the )?(?:plan|solution)|can (?:we|I) (?:still )?(?:reach (?:the )?goal|solve it))', t):
        return dict(kind='solve')
    return None


def edit(frame, text, index):
    """Return (new persistent state, view state, handled). What-if only edits view."""
    f = copy.deepcopy(frame)
    f.pop('explain', None)
    f.pop('transition', None)
    t = clean(text)
    temporary = False
    hit = re.fullmatch(r'(?is)what if (.+)', t)
    if hit:
        temporary = True
        t = clean(hit[1])
    if f['kind'] == 'constraint':
        task = f['task']
        q = query(t, task['domains'])
        hit = re.fullmatch(r'(?is)(?:add(?: rule)?|also)\s*:\s*(.+)', t)
        replacement = re.fullmatch(r'(?is)replace rule\s*:\s*(.+?)\s*=>\s*(.+)', t)
        remove = re.fullmatch(r'(?is)remove rule\s*:\s*(.+)', t)
        domain = re.fullmatch(r'(?is)domain (' + ID + r')\s*:\s*(.+)', t)
        if hit or temporary and not (q or replacement or remove or domain):
            clause = hit[1] if hit else t
            compiled = expression(clause, task['domains'])
            task['constraints'].append(compiled)
            f['records'].append(record(clause, index, compiled=compiled))
            f['query'] = dict(kind='solve')
        elif replacement or remove:
            old = clean(replacement[1] if replacement else remove[1])
            matching = [i for i, r in enumerate(f['records']) if r['kind'] == 'rule' and clean(r['text']) == old]
            if len(matching) != 1:
                raise fc.Unclear('Name exactly one complete existing rule; no partial or ambiguous replacement was applied.')
            at = matching[0]
            previous = f['records'][at]['expression']
            # Duplicate equivalent rules are distinct pieces of evidence.
            rule_at = sum(r['kind'] == 'rule' for r in f['records'][:at])
            if task['constraints'][rule_at] != previous:
                raise fc.Unclear('Typed rules cannot be edited by a prose-only rule reference; start a new complete task.')
            task['constraints'].pop(rule_at)
            f['records'].pop(at)
            if replacement:
                compiled = expression(replacement[2], task['domains'])
                task['constraints'].insert(rule_at, compiled)
                f['records'].insert(at, record(replacement[2], index, compiled=compiled))
            f['query'] = dict(kind='solve')
        elif domain:
            if domain[1] not in task['domains']:
                raise fc.Unclear('A domain update must name an existing variable.')
            task['domains'][domain[1]] = values(domain[2])
            f['records'].append(record(t, index, 'domain-update'))
            f['query'] = dict(kind='solve')
        elif q:
            if q['kind'] == 'why':
                f['explain'] = True
            else:
                f['query'] = q
        else:
            return frame, frame, False
        fc.prepare(task)
    else:
        q = world_query(t)
        move = re.fullmatch(r'(?is)(?:I did|I used|apply|simulate)\s+(' + ID + ')', t)
        observed = re.fullmatch(r'(?is)(observed|update|state)\s*:\s*(.+)', t)
        domain = re.fullmatch(r'(?is)domain (' + ID + r')\s*:\s*(.+)', t)
        goal = re.fullmatch(r'(?is)goal\s*:\s*(.+)', t)
        disabled = re.fullmatch(r'(?i)action (' + ID + r') is (unavailable|available)', t)
        if move:
            action = next((a for a in f['task']['actions'] if a['name'] == move[1]), None)
            if action is None or move[1] in f.get('disabled', []):
                raise fc.Unclear('That action is unknown or unavailable; state was not advanced.')
            if 'effects' not in action:
                raise fc.Unclear('Applying an action requires declared effects; ambiguous learned effects cannot be assumed.')
            new = wr.execute(f['task']['initial'], action, f['task'].get('bounds', {}))
            if new is None:
                raise fc.Unclear('The supplied action is not applicable in the current model state; no move was assumed.')
            f['task']['initial'] = new
            f['transition'] = dict(action=move[1], simulated=True, after=new)
            f['query'] = dict(kind='solve')
        elif observed:
            changed = assignment(observed[2], f['task']['initial'])
            if observed[1].lower() != 'update' and set(changed) != set(f['task']['initial']):
                raise fc.Unclear('Observed/State needs every state variable; use Update for an explicit partial update.')
            f['task']['initial'].update(changed)
            f['query'] = dict(kind='solve')
        elif domain:
            if domain[1] not in f['task']['initial']:
                raise fc.Unclear('A domain update names an unknown state variable.')
            f['task'].setdefault('bounds', {})[domain[1]] = values(domain[2])
            f['query'] = dict(kind='solve')
        elif goal:
            f['task']['goal'] = assignment(goal[1], f['task']['initial'], True)
            f['query'] = dict(kind='solve')
        elif disabled:
            if not any(a['name'] == disabled[1] for a in f['task']['actions']):
                raise fc.Unclear('The availability update names an unknown action.')
            remaining = set(f.get('disabled', []))
            if disabled[2].lower() == 'unavailable':
                remaining.add(disabled[1])
            else:
                remaining.discard(disabled[1])
            f['disabled'] = sorted(remaining)
            f['query'] = dict(kind='solve')
        elif temporary:
            changed = assignment(t, f['task']['initial'])
            f['task']['initial'].update(changed)
            f['query'] = dict(kind='solve')
        elif q:
            f['query'] = q
        else:
            return frame, frame, False
        f['records'].append(record(text, index, 'question' if q else 'update'))
    f['temporary'] = temporary
    f['updated_at'] = index
    return (frame if temporary else f), f, True


def shown(value):
    return json.dumps(value, ensure_ascii=False)


def render_constraints(frame):
    task = frame['task']
    result = fc.solve(task)
    q = frame['query']
    solutions = result['solutions']
    prefix = 'For this temporary what-if only: ' if frame.get('temporary') else ''
    if not result['complete']:
        text = ('The search reached ' + result['status'] + '. I checked ' + str(len(solutions))
                + ' satisfying assignments, but cannot claim a total, a forced answer or impossibility.')
        if solutions and q['kind'] in ('solve', 'all'):
            text += '\nOne checked assignment: ' + shown(solutions[0])
    elif not solutions:
        text = 'The complete finite model has no satisfying assignment. The supplied domains and rules conflict.'
    elif q['kind'] == 'value':
        name = q['name']
        vals = result['possible_values'][name]
        text = name + ' = ' + shown(vals[0]) + ' is forced.' if len(vals) == 1 else name + ' can be ' + shown(vals) + '; no single value is forced.'
    elif q['kind'] == 'occupant':
        occupants = [sorted(n for n,v in s.items() if fc.equal(v,q['position'])) for s in solutions]
        people = sorted({n for group in occupants for n in group})
        text = ('Position ' + str(q['position']) + ': ' + shown(people) + '.')
        if len(people) != 1 or any(group != people for group in occupants):
            text += ' A unique occupant is not determined.'
            if [] in occupants:
                text += ' Some satisfying assignments leave that position empty.'
        result['position_occupants'] = occupants
    elif q['kind'] == 'forced':
        text = 'Forced assignments: ' + shown(result['forced']) + '.' if result['forced'] else 'No individual variable has a forced value; the rules allow multiple assignments.'
    elif q['kind'] == 'predicate':
        tree, _ = fc.compile_rule(q['expression'], set(task['domains']))
        outcomes = [fc.interpret(tree, s) for s in solutions]
        if any(type(v) is not bool for v in outcomes):
            raise fc.Unclear('The question must be a Boolean condition.')
        truth = all(outcomes) if q['necessary'] else any(outcomes)
        text = ('Yes' if truth else 'No') + ': ' + q['expression'] + (' is necessary.' if q['necessary'] else ' is possible.') if truth else 'No: ' + q['expression'] + (' is not necessary.' if q['necessary'] else ' is impossible in the complete finite model.')
        target = False if q['necessary'] and not truth else True if truth else False
        witness = solutions[outcomes.index(target)]
        text += '\n' + ('Counterexample: ' if q['necessary'] and not truth else 'Checked witness: ') + shown(witness)
        result['query_truth'] = truth
        result['query_witness'] = witness
    elif q['kind'] == 'count':
        text = 'There are ' + str(len(solutions)) + ' satisfying assignments in the complete finite model.'
    elif q['kind'] == 'hint':
        forced = result['forced']
        if forced:
            name = next(iter(forced))
            text = 'One hint: ' + name + ' must be ' + shown(forced[name]) + '. That value is shared by every satisfying assignment.'
        else:
            name = next(n for n, vals in result['possible_values'].items() if len(vals) > 1)
            text = 'One hint: ' + name + ' is not forced. At least two complete assignments give it different values; avoid committing before another rule resolves it.'
    else:
        text = str(len(solutions)) + ' satisfying assignment' + ('.' if len(solutions) == 1 else 's.')
        text += '\n' + ('The checked assignment: ' if len(solutions) == 1 else 'One checked assignment: ') + shown(solutions[0])
        if q['kind'] == 'all' and len(solutions) > 1:
            text += '\n' + shown(solutions[:8])
            if len(solutions) > 8:
                text += '\nOnly the first 8 assignments are displayed; the total above includes all.'
    if frame.get('explain'):
        text += '\n\nI interpreted every supplied rule, searched the declared finite domains and replayed every returned witness. Rules used:\n'
        text += '\n'.join('- ' + r for r in task['constraints']) or '- No extra constraints were supplied.'
        text += '\nThis verifies the declared model; it does not establish facts outside your supplied rules.'
    return dict(route='chat/constraint-dialogue', response=prefix + text, sources=[], constraint_reasoning=result)


def render_world(frame):
    task = copy.deepcopy(frame['task'])
    if wr.execute(task['initial'], dict(effects={}), task.get('bounds', {})) is None:
        raise fc.Unclear('The supplied/model state lies outside a declared domain; no transition was assumed.')
    disabled = set(frame.get('disabled', []))
    task['actions'] = [a for a in task['actions'] if a['name'] not in disabled]
    # Retain full validation even when availability disables every action.
    original = wr.solve(frame['task']) if not task['actions'] else None
    if not task['actions']:
        if wr.condition(task['goal'], task['initial']):
            result = dict(original, status='plan', plan=[], final=task['initial'], steps=[], replay_checked=True)
        else:
            result = dict(original, status='unavailable', plan=[], final=None, steps=[], replay_checked=False)
    else:
        # Traces for a disabled action remain evidence but are not an extra
        # available action. The complete original model is checked first.
        if disabled and 'traces' in task:
            wr.solve(frame['task'])
            task['traces'] = [r for r in task['traces'] if r['action'] not in disabled]
            if not task['traces']:
                task.pop('traces')
        result = wr.solve(task)
    q = frame['query']['kind']
    prefix = 'For this temporary what-if only: ' if frame.get('temporary') else ''
    if q == 'state':
        text = 'Current supplied/model state: ' + shown(task['initial']) + '.\nGoal: ' + shown(task['goal']) + '.'
    elif result['status'] != 'plan':
        text = 'No checked plan was found (' + result['status'] + '). This concerns the supplied model and limits; it is not proof that the real game is impossible.'
    elif not result['plan']:
        text = 'The goal already holds in the supplied/model state. No action is needed.'
    elif q in ('hint', 'next'):
        step = result['steps'][0]
        text = ('One hint' if q == 'hint' else 'Next step') + ': ' + step['action'] + '.\nIn the supplied model it changes ' + shown(step['before']) + ' to ' + shown(step['after']) + '.'
    else:
        text = 'Checked plan: ' + ' -> '.join(result['plan']) + '.\nExpected final state in the supplied model: ' + shown(result['final']) + '.'
        if q == 'why':
            text += '\n\nEvery action was replayed against its preconditions, simultaneous effects and bounds:\n'
            text += '\n'.join(str(i+1) + '. ' + s['action'] + ': ' + shown(s['before']) + ' -> ' + shown(s['after']) for i, s in enumerate(result['steps']))
    if frame.get('transition'):
        text = 'After applying ' + frame['transition']['action'] + ' in the supplied model (simulated, not an external action):\n' + text
    text += '\n' + result['assumptions']
    result['available_action_names'] = [a['name'] for a in task['actions']]
    result['availability_sha256'] = hashlib.sha256(json.dumps(dict(task=frame['task'],disabled=sorted(disabled)),sort_keys=True).encode()).hexdigest()
    return dict(route='chat/planning-dialogue', response=prefix + text, sources=[], world_reasoning=result)


def reply(messages):
    """No process/global task store: independent requests cannot inherit a task."""
    if (not isinstance(messages, list) or not messages or len(messages) > 256
            or messages[-1].get('role') != 'user' or sum(len(m['content']) for m in messages) > 400000):
        return None
    current, view, handled = None, None, False
    last = len(messages)-1
    for index, message in enumerate(messages):
        if message['role'] != 'user':
            continue
        text = message['content'].strip()
        if len(text) > 40000:
            owned = re.match(r'(?i)^(?:constraint puzzle|finite problem|puzzle|planning (?:task|problem)|variables|order|arrange|domain '+ID+r')\s*:', text)
            current = dict(kind='invalid',reason='The complete problem exceeds the 40000-character task bound.') if owned else None
            if index == last and owned:
                return dict(route='chat/problem-clarify',response='The complete problem exceeds the 40000-character task bound. Split the problem explicitly; I have not solved a shortened version.',sources=[])
            continue
        try:
            if RESET.fullmatch(text):
                current = None
                if index == last:
                    return dict(route='chat/problem-context', response='Problem context cleared. A new problem needs its own facts, domains or action rules.', sources=[])
                continue
            # A standalone domain line updates the active problem. It must not
            # erase its other variables/rules by starting a new one-variable task.
            domain_update = current is not None and current.get('kind') != 'invalid' and re.fullmatch(r'(?is)domain '+ID+r'\s*:[^\n]+', text)
            fresh = None if domain_update else new_frame(text, index)
            if fresh is not None:
                # A pure typed action model keeps its established initial
                # renderer. Subsequent grounded follow-ups use the same model.
                current = fresh
                view, handled = fresh, True
                if index == last and fresh['kind'] == 'world' and text.startswith('{'):
                    if wr.execute(fresh['task']['initial'], dict(effects={}), fresh['task'].get('bounds', {})) is None:
                        raise fc.Unclear('The supplied initial state lies outside its declared bounds.')
                    return None
            elif current is not None:
                if current['kind'] == 'invalid':
                    raise fc.Unclear('An earlier problem turn was rejected: ' + current['reason'] + ' Reset the problem or supply a complete corrected task before continuing.')
                current, view, handled = edit(current, text, index)
                if not handled:
                    if SOCIAL.fullmatch(text):
                        if index == last:
                            return None
                        continue
                    # A direct topic change ends the task. A referential task
                    # edit/query is refused rather than answered from a subset.
                    refers = re.match(r'(?i)^(?:add|also|replace|remove|domain|goal|observed|update|state|what if|what about|why|hint|I did|apply|simulate)\b', text)
                    if refers:
                        raise fc.Unclear('That follow-up is outside the complete task grammar; no rule, action or extra condition was discarded.')
                    current = None
                    if index == last:
                        return None
            elif index == last:
                if re.match(r'(?i)^(?:what if|replace rule|remove rule|I did|apply|simulate)\b', text) or WHY.fullmatch(text) and len(messages) == 1:
                    return dict(route='chat/problem-clarify', response='I need the problem and its rules in this conversation before I can apply that follow-up. Supply the goal and facts or the current state and actions.', sources=[])
                return None
            if current is not None and index < last:
                # Validate declared models/edits before trusting them as history.
                if current['kind'] == 'constraint':
                    fc.prepare(current['task'])
                else:
                    if wr.execute(current['task']['initial'], dict(effects={}), current['task'].get('bounds', {})) is None:
                        raise fc.Unclear('A historical state lies outside its declared bounds.')
                    wr.solve(current['task'])
            if index == last and handled and view is not None:
                answer = render_constraints(view) if view['kind'] == 'constraint' else render_world(view)
                answer['problem_context'] = dict(kind=view['kind'], user_evidence=view['records'],
                    question=view['query'], temporary=bool(view.get('temporary')), assistant_text_as_evidence=False,
                    context_sha256=hashlib.sha256(json.dumps(dict(task=view['task'],disabled=view.get('disabled',[]),query=view['query']), sort_keys=True).encode()).hexdigest())
                return answer
        except (fc.Unclear, wr.Unclear, KeyError, TypeError, RecursionError, OverflowError) as exc:
            if index == last:
                return dict(route='chat/problem-clarify', response='Please clarify this problem: ' + str(exc), sources=[],
                            problem_context=dict(complete=False, rejected_message=index, assistant_text_as_evidence=False))
            # Rejected edits do not silently change the last valid frame.
            # A later query must explicitly replace/reset the bad turn.
            if not (current is not None and re.match(r'(?i)^what if\b', text)):
                current = dict(kind='invalid', reason=str(exc))
            view = None
            continue
    return None
