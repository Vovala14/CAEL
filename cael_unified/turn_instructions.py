"""Finite instruction grammar ahead of the unchanged count-model fallback.

These instructions refer to visible tasks; they never invent a task or discard
literal clauses from one. Scores in the inherited count model are unchanged.
"""
import re

def words(text):
    return re.findall(r"[a-z]+",text.casefold().replace('’',"'").replace("don't",'do not'))

def read(text):
    if isinstance(text,str) and len(text)<700 and re.match(r'(?i)^(?:please\s+)?(?:show|give)(?: me)?\s+(?:(?:an?|one)\s+)?(?:(?:small|worked|concrete|short|simple|specific)\s+)*(?:example|case|illustration)\b',text):return 'example'
    if not isinstance(text,str) or len(text)>300 or '```' in text or re.search(r'["“\d{}=]',text):return None
    tokens=set(words(text))
    if not tokens:return None
    formatting={'only','alone','just','nothing','without','but','no'}
    targets={'result','answer','value','number','digits','integer','year'}
    # A new concrete question is not an old-answer projection.
    if tokens&formatting and tokens&targets and re.match(r"(?i)^(?:please\s+)?(?:return|give|show|output|print|i (?:would |just )?(?:like|want|need)|nothing|only|just)\b",text):
        allowed=set('please return give show output print i would like want need just only alone nothing but the a an this that it your our answer result value number digits integer year no without any prose explanation words commentary in reply response could can you me do not include to see'.split())
        if tokens<=allowed:return 'number'
    checking={'check','recheck','verify','test','audit','recalculate','recompute','double'}
    if tokens&checking and not re.search(r"(?i)\b(?:do not|don.t|never)\s+(?:check|test|verify|recheck|audit|recalculate|recompute)\b",text):
        allowed=set('please can could would you i me the a an this that it your our answer response calculation arithmetic result work working code program function implementation examples supplied original all both again actually really independently independent check recheck verify test audit recalculate recompute double whether if made make any error errors mistake mistakes for against of to in previous preceding visible there are is have has did done correctness'.split())
        if tokens<=allowed:return 'recheck'
    return None

def is_code_update(text):
    return len(text)<700 and bool(re.match(r'(?i)^(?:please\s+)?(?:also\b|instead\b|make (?:it|that|the (?:function|code|program))\b|add\b|it (?:must|should)\b)',text))
