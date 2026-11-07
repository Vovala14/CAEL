"""Shared bounded symbols/clauses for native symbolic task compilation."""
from dataclasses import dataclass
from fractions import Fraction
import re

class TaskError(ValueError):
    pass

ATOM=r'[A-Za-z][A-Za-z0-9_-]*(?: [A-Za-z][A-Za-z0-9_-]*){0,7}'
NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:/[+-]?\d+)?'

def clean(s):
    s=s.strip().strip('"\'`').strip().rstrip(' .?!')
    return re.sub(r'\s+',' ',s).casefold()

def symbol(s):
    s=re.sub(r'(?i)^(?:the|an?)\s+','',s.strip())
    if not re.fullmatch(ATOM,s) or re.search(r'(?i)\b(?:unless|except|maybe|perhaps|sometimes|either|or|if|then|and)\b',s):
        raise TaskError('An entity or property has an ambiguous or unsupported modifier.')
    return clean(s)

def alphabet(n):
    out=''
    while True:
        out=chr(97+n%26)+out;n=n//26-1
        if n<0:return out

def clauses(text):
    """Keep decimal points and quoted text intact; every clause remains visible."""
    out=[];start=0;quote=None
    for i,ch in enumerate(text):
        if ch in ('"',"'") and (i==0 or text[i-1]!='\\'):
            # Apostrophes inside words are not quotation delimiters.
            if ch=="'" and i and i+1<len(text) and text[i-1].isalnum() and text[i+1].isalnum():continue
            if quote==ch:quote=None
            elif quote is None:quote=ch
        stop=ch in '\n;' or (ch=='.' and not (i and i+1<len(text) and text[i-1].isdigit() and text[i+1].isdigit()))
        if stop and quote is None:
            if text[start:i].strip():out.append(text[start:i].strip())
            start=i+1
    if text[start:].strip():out.append(text[start:].strip())
    return out

def spans(text,parts):
    result=[];offset=0
    for part in parts:
        i=text.find(part,offset)
        if i<0:raise TaskError('Source coverage could not be established.')
        result.append({'text':part,'span':[i,i+len(part)]});offset=i+len(part)
    return result

def fraction(s):
    s=s.strip()
    if not re.fullmatch(NUMBER,s):raise TaskError('A numeric cell is missing or is not an explicit rational number.')
    try:v=Fraction(s)
    except (ValueError,ZeroDivisionError):raise TaskError('A number or denominator is invalid.')
    if max(v.numerator.bit_length(),v.denominator.bit_length())>512:raise TaskError('The numeric value is outside the checked size limit.')
    return v

def display(v):
    if isinstance(v,Fraction):return str(v.numerator) if v.denominator==1 else str(v)
    return str(v)

def boundary(text):
    if re.search(r'(?i)\b(?:unless|except|assuming|approximately|probably|maybe|possibly|ignore|disregard|pretend)\b|\bround(?:ed|ing)?\s+(?:to|off|up|down|it|the result)\b',text):
        raise TaskError('A condition, exception or approximation needs a supported explicit interpretation; it cannot be omitted.')

def strip_request(text):
    return re.sub(r'(?i)^\s*(?:(?:can|could|would) you\s+)?(?:please\s+)?','',text).strip()

@dataclass
class Result:
    value: object
    family: str
    program: dict
    numeric: bool=False
    exact_text: bool=False
