"""Bounded string-operation pipelines and typed table reductions, from source."""
import csv
from fractions import Fraction
import json
import re
from .interpretation_common import Result,TaskError,boundary,clauses,clean,fraction,spans,strip_request

def strings(text):
    t=strip_request(text)
    if not re.search(r'(?i)\b(?:reverse|backwards|backward|rotate|characters|substring|uppercase|lowercase|swapcase|append|prepend|replace)\b',t):return None
    if re.match(r'(?i)(?:write|create|implement|define|build|explain) (?:a |the )?(?:python |javascript )?(?:function|script|program|code)\b',t):return None
    literals=[]
    def mask(m):
        raw=m[0]
        try:value=json.loads(raw) if raw.startswith('"') else raw[1:-1]
        except ValueError:raise TaskError('A quoted string literal has invalid escaping.')
        literals.append(value);return f'literalq{len(literals)-1}'
    source=re.sub(r'''"(?:[^"\\]|\\.)*"|'[^']*' ''',mask,t,flags=re.X)
    if not literals:return None
    if not re.search(r'(?i)\b(?:reverse|backwards|backward|rotate|characters|substring|uppercase|lowercase|swapcase|append|prepend|replace)\b',source):return None
    if not re.match(r'(?i)^(?:from\b|for\b|given\b|using\b|with\b|text\s*:|string\s*:|input\s*:|reverse\b|rotate\b|keep\b|retain\b|select\b|take\b|read\b|write\b|move\b|transfer\b|drop\b|remove\b|delete\b|convert\b|change\b|make\b|uppercase\b|lowercase\b|swapcase\b|append\b|prepend\b|replace\b|number\b|index\b)',source):return None
    if len(literals[0])>2048 or len(literals)>8:raise TaskError('Use at most eight quoted literals and an input string within 2,048 characters.')
    boundary(source)
    source=re.sub(r'(?i)^(?:for|given|using|with)(?: the)? (?:text|string|sequence|characters)\s*(?:is|:)?\s*literalq0\s*[,.:]?\s*','',source)
    source=re.sub(r'(?i)^(?:text|string|input)\s*:\s*literalq0\s*[,.:]?\s*','',source)
    source=re.sub(r'(?i)\b(?:the )?(?:string|text) (literalq\d+)\b',r'\1',source)
    pieces=[]
    for p in clauses(source):pieces.extend(re.split(r'(?i)\s*,?\s*\b(?:then|after that|next)\b\s*',p))
    pieces=[p.strip(' ,.:?') for p in pieces if p.strip(' ,.:?')]
    value=literals[0];ops=[];used={0};base=1
    arg=r'(?:literalq0|(?:the |its )?(?:entire |resulting |current |original )?(?:string|text|characters|letters|result|sequence)|it)'
    reverse_words=set('reverse read write take the its all entire resulting current original string text characters letters result sequence it literalq0 in of reverse order backwards backward from last one to first what which is results produces do you obtain choose final'.split())
    for part in pieces:
        p=part.casefold()
        m=re.fullmatch(rf'(?:number|index) (?:the )?characters (?:of |in )?{arg} (?:starting|beginning) (?:at|from) ([01])',p)
        if m:base=int(m[1]);continue
        m=re.fullmatch(r'(?:use|using) ([01])[- ]based (?:positions|indexing|indices)',p)
        if m:base=int(m[1]);continue
        # Query-only clauses carry no additional transformation.
        if re.fullmatch(r'(?:what|which)(?: is| do you get| do you obtain)?(?: the)?(?: final| resulting)? (?:string|text|sequence|result)(?: results| remains| do you get| do you obtain)?',p) or p in ('choose the final string','select the resulting string','what remains','which sequence results'):continue
        op=None
        m=re.fullmatch(rf'rotate\s+{arg}?\s*(left|right)\s*(?:by )?(\d+)\s*(?:characters?|positions?|places?)?',p)
        if m:op=('rotate',m[1],int(m[2]))
        if op is None:
            m=re.fullmatch(r'(?:move|transfer) (?:the )?(first|last) (\d+) characters (?:of literalq0 )?to (?:its |the )?(end|front|beginning)(?: without (?:reordering|changing their order))?',p)
            if m and ((m[1]=='first' and m[3]=='end') or (m[1]=='last' and m[3] in ('front','beginning'))):op=('rotate','left' if m[1]=='first' else 'right',int(m[2]))
        if op is None:
            m=re.fullmatch(rf'(?:keep|retain|select|take)(?: only)? (?:the )?(even|odd)[- ](?:numbered|positioned) characters(?: (?:of|from|in) {arg})?(?:,? (?:without changing|preserving) their order)?',p)
            if m:op=('parity',0 if m[1]=='even' else 1,base)
        if op is None:
            m=re.fullmatch(rf'(?:from {arg},? )?(?:keep|retain|select|take)(?: only)? (?:the )?characters (?:at|in) positions? ([\d, ]+)(?:,? and so on)?(?: \(([01])[- ]based\))?',p)
            if m:
                positions=[int(x) for x in re.findall(r'\d+',m[1])];indexbase=int(m[2]) if m[2] else base
                if 'and so on' in p:
                    if len(positions)<2 or len(set(b-a for a,b in zip(positions,positions[1:])))!=1 or positions[1]<=positions[0]:raise TaskError('The repeated position pattern is not uniquely specified.')
                    op=('positions_progression',positions[0]-indexbase,positions[1]-positions[0])
                else:op=('positions',[i-indexbase for i in positions])
        if op is None:
            m=re.fullmatch(rf'(?:remove|drop|delete) (?:the )?(first|last) (\d+) characters(?: (?:of|from) {arg})?',p)
            if m:op=('drop',m[1],int(m[2]))
        if op is None:
            m=re.fullmatch(rf'(?:convert|change|make) {arg} (?:to |all )?(upper(?:case)?|lower(?:case)?)(?: letters)?',p) or re.fullmatch(rf'(uppercase|lowercase|swapcase) {arg}',p)
            if m:op=('case','upper' if m[1].startswith('upper') else 'lower' if m[1].startswith('lower') else 'swapcase')
        if op is None:
            m=re.fullmatch(r'(append|prepend) literalq(\d+)(?: to (?:the )?(?:result|string|text|it))?',p)
            if m:op=(m[1],int(m[2]));used.add(int(m[2]))
        if op is None:
            m=re.fullmatch(r'replace (?:every |each |all )?(?:occurrence of )?literalq(\d+) (?:with|by) literalq(\d+)(?: in (?:the )?(?:result|string|text|it))?',p)
            if m:op=('replace',int(m[1]),int(m[2]));used.update((int(m[1]),int(m[2])))
        if op is None:
            words=set(re.findall(r'[a-z0-9]+',p))
            if (re.search(r'\b(?:reverse|backwards|backward)\b',p) or ('last' in words and 'first' in words and words&{'read','write','take'})) and words<=reverse_words:op=('reverse',)
        if op is None:raise TaskError('A string operation or indexing instruction is unsupported: '+part[:100])
        before=value
        if op[0]=='reverse':value=''.join(reversed(value))
        elif op[0]=='rotate':
            k=op[2]%len(value) if value else 0
            if op[1]=='right':k=(-k)%len(value) if value else 0
            value=value[k:]+value[:k]
        elif op[0]=='parity':value=''.join(ch for i,ch in enumerate(value) if (i+op[2])%2==op[1])
        elif op[0]=='positions':
            if any(i<0 or i>=len(value) for i in op[1]):raise TaskError('An explicit requested character position is out of bounds.')
            value=''.join(value[i] for i in op[1])
        elif op[0]=='positions_progression':
            if op[1]<0:raise TaskError('A requested position precedes the declared index origin.')
            value=''.join(value[i] for i in range(op[1],len(value),op[2]))
        elif op[0]=='drop':value=value[op[2]:] if op[1]=='first' else value[:max(0,len(value)-op[2])]
        elif op[0]=='case':value=getattr(value,op[1])()
        elif op[0]=='append':value+=literals[op[1]]
        elif op[0]=='prepend':value=literals[op[1]]+value
        else:
            if not literals[op[1]]:raise TaskError('Replacing an empty substring needs an explicit insertion convention.')
            value=value.replace(literals[op[1]],literals[op[2]])
        if len(value)>16384 or len(ops)>=12:raise TaskError('The string program exceeds its checked size bound.')
        ops.append({'source':part,'operation':op,'before':before,'after':value})
    if not ops:return None
    if used!=set(range(len(literals))):raise TaskError('A quoted value was not consumed by the complete string specification.')
    return Result(value,'strings',{'source_span':[0,len(text)],'literals':literals,'operations':ops,'index_origin':base},exact_text=True)

ALIASES=[{'quantity','qty','units','unit count','amount'}, {'price','unit price','cost','unit cost'},
         {'group','category','class','type'}, {'name','item','product','entry','identifier','id'}]

def tables(text):
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(lines)<3:return None
    header=lines[0]
    delimiter='|' if '|' in header else '\t' if '\t' in header else ',' if ',' in header else None
    if delimiter is None:return None
    header=re.sub(r'(?i)^(?:table|records|data)\s*:\s*','',header)
    def cells(line):
        line=line.strip().strip('|') if delimiter=='|' else line
        return [x.strip() for x in next(csv.reader([line],delimiter=delimiter))]
    headers=cells(header);keys=[re.sub(r'[_-]+',' ',clean(x)) for x in headers]
    if not 2<=len(keys)<=16 or len(set(keys))!=len(keys) or any(not re.fullmatch(r'[a-z][a-z0-9 ]{0,60}',k) for k in keys):return None
    records=[];qlines=[];data_lines=[]
    for line in lines[1:]:
        row=cells(line)
        if len(row)==len(keys) and all(re.fullmatch(r':?-+:?',x) for x in row):data_lines.append(line);continue
        if delimiter in line and not qlines:
            if len(row)!=len(keys):raise TaskError('A table record has a different number of cells from its header.')
            if any(x=='' for x in row):raise TaskError('A table contains an empty cell; its meaning must be specified.')
            records.append(row);data_lines.append(line)
        else:qlines.append(line)
    if not records or not qlines:return None
    if len(records)>200:raise TaskError('Use at most 200 explicit table records.')
    query=' '.join(qlines).strip();boundary(query)
    if re.search(r'(?i)\b(?:or|either|unless|except)\b',query):raise TaskError('This table query has an unsupported condition or combination.')
    aliases={}
    for i,k in enumerate(keys):
        aliases.setdefault(k,set()).add(i)
        for group in ALIASES:
            if k in group:
                for term in group:aliases.setdefault(term,set()).add(i)
    def field(label):
        label=re.sub(r'[_-]+',' ',clean(label))
        if label in keys:return keys.index(label)
        found=aliases.get(label,set())
        if len(found)!=1:raise TaskError('A queried table column is missing or has an ambiguous alias: '+label)
        return next(iter(found))
    # "product of X and Y" is an operation, not an inferred name-column alias.
    if 'product' not in keys:aliases.pop('product',None)
    all_fields='|'.join(re.escape(k).replace(r'\ ',r'[ _-]+') for k in sorted(aliases,key=len,reverse=True))
    filters=[]
    # Conditions use only actual declared fields/aliases. No inferred row labels.
    condition=rf'(?P<field>{all_fields})\s*(?P<op>is not|is|equals|equal to|!=|>=|<=|=|>|<)?\s+(?P<value>"[^"]*"|\x27[^\x27]*\x27|[A-Za-z0-9_+./-]+)'
    region=re.search(rf'(?i)\b(?:for|with|where|whose|having|that have|have|has)\s+(?:the )?(?:records?\s+(?:where|with)\s+)?{condition}',query)
    masked=query
    if region:
        idx=field(region['field']);op=(region['op'] or '=').casefold();val=region['value'].strip('"\'') if region['value'].startswith(('"',"'")) else region['value'].rstrip('.?')
        filters.append((idx,op,val));masked=query[:region.start()]+' FILTER '+query[region.end():]
        # Additional conjunction conditions must be completely covered too.
        after_filter=region.start()+len(' FILTER ')
        while True:
            m=re.match(rf'(?i)\s*and\s+{condition}',masked[after_filter:])
            if not m:break
            val=m['value'].strip('"\'') if m['value'].startswith(('"',"'")) else m['value'].rstrip('.?')
            filters.append((field(m['field']),(m['op'] or '=').casefold(),val))
            masked=masked[:after_filter]+' FILTER '+masked[after_filter+m.end():]
            after_filter+=len(' FILTER ')
    if re.search(r'(?i)\b(?:where|whose|having)\b',masked):raise TaskError('A table filter could not be fully parsed.')
    selected=[]
    for ri,row in enumerate(records):
        keep=True
        for col,op,value in filters:
            actual=row[col]
            if op in ('>','<','>=','<='):
                a,b=fraction(actual),fraction(value);accept={'>':a>b,'<':a<b,'>=':a>=b,'<=':a<=b}[op]
            else:
                try:a,b=fraction(actual),fraction(value)
                except TaskError:a,b=actual,value
                accept=(a!=b) if op in ('is not','!=') else (a==b)
            keep &= accept
        if keep:selected.append(ri)
    # Replace column references with typed variables before lexical coverage.
    referenced=[]
    def replace(m):
        i=field(m[0]);referenced.append(i);return ' FIELD '
    residual=re.sub(rf'(?i)(?<![\w])(?:{all_fields})(?![\w])',replace,masked)
    words=set(re.findall(r'[A-Za-z]+',residual.casefold()))
    vocabulary=set('''filter field what which is are the a an of for with where whose having in per how many number count rows row records record entries entry selected matching all each every their corresponding values value total sum add added adding aggregate combined quantity amounts multiply multiplied by times product products take calculate compute find determine give return choose select obtain get do you result answer these those this that and then to on its together table data please'''.split())
    vocabulary.update(('minimum','maximum','min','max','average','mean','smallest','largest'))
    if not words<=vocabulary or re.search(r'[^A-Za-z\s\d,.:?*+/_()=-]',residual):raise TaskError('The complete table query contains an uncompiled operation or qualifier.')
    q=residual.casefold();fields=list(dict.fromkeys(referenced))
    if re.search(r'\b(?:count|how many|number of (?:rows|records|entries))\b',q):
        if fields:raise TaskError('Specify whether to count records or aggregate a column.')
        value=Fraction(len(selected));operation='count'
    else:
        reduce='mean' if re.search(r'\b(?:mean|average)\b',q) else 'min' if re.search(r'\b(?:minimum|min|smallest)\b',q) else 'max' if re.search(r'\b(?:maximum|max|largest)\b',q) else 'sum' if re.search(r'\b(?:sum|total|add|adding|aggregate|combined)\b',q) else None
        if reduce is None or not fields:raise TaskError('Specify a supported reducer and its numeric column.')
        product=bool(re.search(r'\b(?:multiply|multiplied|times|product|products)\b|\*',q))
        if len(fields)!= (2 if product else 1):raise TaskError('The numeric column expression is missing or ambiguous.')
        values=[]
        for ri in selected:
            v=fraction(records[ri][fields[0]])
            if product:v*=fraction(records[ri][fields[1]])
            values.append(v)
        if reduce!='sum' and not values:raise TaskError('The selected table is empty, so this reducer is undefined.')
        value=sum(values,Fraction(0)) if reduce=='sum' else sum(values,Fraction(0))/len(values) if reduce=='mean' else min(values) if reduce=='min' else max(values)
        operation=reduce+('_product' if product else '')
    return Result(value,'tables',{'coverage':spans(text,lines),'headers':headers,'records':records,'filters':filters,
        'selected_record_indices':selected,'operation':operation,'numeric_columns':fields,'value':str(value)},True)
