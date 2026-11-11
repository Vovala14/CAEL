"""General data-task envelopes own their complete structure before chat cues."""
import json
import re

PREFIX=re.compile(r'(?is)^\s*(?:(?:please )?(?:solve|infer|predict|complete|analyse|analyze|choose|select|take|return|provide)\b[^{}\n]{0,160}:\s*|(?:grid task|next action|observation|environment observation):\s*)?$')
SHORT_HEADER=re.compile(r'(?is)^\s*(?:(?:(?:please )?(?:solve|infer|predict|complete|analyse|analyze|choose|select|take|return|provide)(?: (?:this |the |a )?(?:task|puzzle|world|planning task|state task|grid|grid task|next action|action|observation))?|grid task|next action|observation|environment observation):\s*)?$')


def control_header(text):
    """Consume only declared action-format/control instructions, every clause.

    A sample action JSON is framing, not an action forced on the learner.
    Additional semantic conditions remain unsupported instead of disappearing.
    """
    body=' '.join(text.split())
    clauses=[
      r'(?i)^You control an? (?:unfamiliar |unknown |new )?(?:interactive )?grid environment\.\s*',
      r'(?i)^Infer its goal and choose the next action from the available actions\.\s*',
      r'(?i)^Return (?:ONLY )?a JSON object with fields action and data, for example \{"action":"[A-Za-z0-9_-]+","data":\{\}\}\.\s*',
      r'(?i)^Use the exact listed action name\.\s*',
      r'(?i)^Complex actions require integer x and y coordinates from 0 through 63\.\s*',
      r'(?i)^The meanings of action IDs must be discovered from observations\.\s*',
      r'(?i)^Observation and available actions:\s*']
    changed=True
    while body and changed:
        changed=False
        for pattern in clauses:
            match=re.match(pattern,body)
            if match:body=body[match.end():];changed=True;break
    return not body


def labeled_grid(text):
    """Read complete input/output/query blocks, preserving each matrix axis."""
    body=text.strip()
    # A documented lossless text serialization is data framing, not a rule
    # family, task identifier or answer. Unknown extra prose stays unsupported.
    official_intro=("You are participating in a puzzle solving competition. You are an expert at solving puzzles. "
        "Below is a list of input and output pairs with a pattern. Your goal is to identify the pattern or transformation in the training examples that maps the input to the output, then apply that pattern to the test input to give a final output. "
        "Respond in the format of the training output examples")
    if '--Training Examples--' in body:
        before,body=body.split('--Training Examples--',1)
        if ' '.join(before.split()) != official_intro:return ('unsupported',{'reason':'Additional grid instructions are not supported by this finite reader.'})
        match=re.fullmatch(r'(?s)(.*?)--End of Training Examples--\s*--Test Input--\s*(.*?)\s*--End of Test Input--\s*Your response:\s*',body)
        if not match:return ('unsupported',{'reason':'Incomplete example/query framing.'})
        body=re.sub(r'--Example \d+--\s*','',match[1])+'\nQUERY: '+match[2]
    elif re.match(r'(?i)^examples:\s*',body):
        body=re.sub(r'(?i)^examples:\s*','',body,count=1)
    else:return None
    decoder=json.JSONDecoder();examples=[];position=0
    def matrix_after(label):
        nonlocal position
        m=re.match(r'\s*'+label+r'\s*:\s*',body[position:],re.I)
        if not m:raise ValueError('Missing '+label+' label')
        position+=m.end();value,position=decoder.raw_decode(body,position);return value
    try:
        while re.match(r'\s*INPUT\s*:',body[position:],re.I):
            source=matrix_after('INPUT');target=matrix_after('OUTPUT')
            examples.append(dict(input=source,output=target))
            if len(examples)>12:raise ValueError('Example limit')
        query=matrix_after('QUERY')
        if body[position:].strip():raise ValueError('Unconsumed grid instruction')
    except (ValueError,RecursionError):
        return ('unsupported',dict(reason='Provide every complete input/output demonstration and one query, with no omitted or extra clauses.'))
    return 'grid',dict(examples=examples,query=query)


def read(text):
    if not isinstance(text,str) or not 0<len(text)<=2000000:return None
    # The established 1D specialist owns its complete contract and validation.
    if text.lstrip().startswith('Infer discrete transition:'):return None
    if text.lstrip().startswith('Infer spatial transition:'):
        try:return 'native-grid',json.loads(text.lstrip()[len('Infer spatial transition:'):].strip())
        except (ValueError,RecursionError):return 'unsupported',dict(reason='Provide one complete native grid JSON object, without trailing instructions.')
    labeled=labeled_grid(text)
    if labeled is not None:return labeled
    positions=[m.start() for m in re.finditer(r'\{',text)]
    decoder=json.JSONDecoder()
    for pos in positions[:64]:
        try:value,end=decoder.raw_decode(text,pos)
        except (ValueError,RecursionError):continue
        if type(value) is not dict:continue
        if not ({'examples','query'} <= set(value) or {'frames','available_actions'} <= set(value) or {'initial','goal','actions'} <= set(value)):continue
        # Complete JSON plus a bounded instruction header only. Arbitrary
        # trailing/leading semantic clauses cannot disappear into a parser.
        if text[end:].strip() or not (SHORT_HEADER.fullmatch(text[:pos]) or 'frames' in value and control_header(text[:pos])):
            return ('unsupported',dict(reason='Provide the complete grid/observation JSON with a short task header; additional prose constraints need explicit interpretation.'))
        return ('grid' if 'examples' in value else 'world' if 'initial' in value else 'environment'),value
    return None


def reply(messages):
    found=read(messages[-1]['content'])
    if found is None:return None
    kind,task=found
    if kind=='unsupported':
        return dict(route='chat/structured-clarify',response=task['reason'],sources=[])
    if kind=='grid':
        from .grid_programs import reply as solve
        return solve(task)
    if kind=='native-grid':
        from .stream_grid import reply as solve
        return solve(task)
    if kind=='world':
        from .world_reasoning import reply as plan
        return plan(task)
    from .game_agent import reply as explore
    history=[]
    for m in messages[:-1]:
        if m['role']=='user':
            previous=read(m['content'])
            if previous and previous[0]=='environment':history.append(('user',previous[1]))
            else:history=[]  # another task/reset is a memory boundary
        elif m['role']=='assistant':
            try:value=json.loads(m['content'])
            except (ValueError,RecursionError):continue
            history.append(('assistant',value))
    return explore(task,history)
