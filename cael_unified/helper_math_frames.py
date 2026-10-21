"""Explicit arithmetic relationships, with exact values and stated assumptions.

An authored symbolic helper; no learned weights, target answers, eval or web.
"""
from fractions import Fraction
import itertools
import math
import re

N = r'-?\d{1,9}(?:\.\d{1,6})?'


def solve(text):
    t = text.lower().strip().rstrip(' ?.').replace(',', '')
    t = re.sub(r'\bpercent\b', '%', t)
    t = re.sub(r'^please\s+', '', t)
    # Result, derivation, assumptions. The caller renders exact numbers.
    percent = re.fullmatch(r'(' + N + r')\s+is\s+what\s+(?:%|percentage)\s+of\s+(' + N + r')', t)
    if percent and Fraction(percent[2]):
        return Fraction(percent[1])*100/Fraction(percent[2]), 'part / whole * 100', 'Result is a percentage.'
    percent = re.fullmatch(r'(?:what\s+)?(?:%|percentage)\s+of\s+(' + N + r')\s+is\s+(' + N + r')', t)
    if percent and Fraction(percent[1]):
        return Fraction(percent[2])*100/Fraction(percent[1]), 'part / whole * 100', 'Result is a percentage.'
    unknown = re.fullmatch(r'(' + N + r')\s+is\s+(' + N + r')\s*%\s+of\s+(?:what|which)\s+(?:number|amount)', t)
    if unknown and Fraction(unknown[2]):
        return Fraction(unknown[1])*100/Fraction(unknown[2]), 'whole = part * 100 / percent', ''
    words = {'half': Fraction(1,2), 'a half':Fraction(1,2), 'one half':Fraction(1,2),
             'a third':Fraction(1,3), 'one third':Fraction(1,3), 'two thirds':Fraction(2,3),
             'a quarter':Fraction(1,4), 'one quarter':Fraction(1,4), 'three quarters':Fraction(3,4)}
    part = re.fullmatch(r'(?:what is |calculate )?('+'|'.join(words)+r')\s+of\s+(' + N + r')', t)
    if part:
        return words[part[1]]*Fraction(part[2]), f'{words[part[1]]} * {part[2]}', ''
    arithmetic = re.fullmatch(r'(?:what is |find |calculate |compute )?(?:the )?(sum|difference|product|quotient)\s+(?:of|between)\s+(' + N + r')\s+and\s+(' + N + r')', t)
    if arithmetic:
        a,b=Fraction(arithmetic[2]),Fraction(arithmetic[3])
        if arithmetic[1]=='quotient' and not b:return None
        value={'sum':lambda:a+b,'difference':lambda:abs(a-b),'product':lambda:a*b,'quotient':lambda:a/b}[arithmetic[1]]()
        return value, arithmetic[1]+' of the two stated numbers', 'Difference means absolute difference.' if arithmetic[1]=='difference' else ''
    choose = re.fullmatch(r'(?:what is |calculate |compute )?(\d{1,3})\s+choose\s+(\d{1,3})', t)
    if choose and 0 <= int(choose[2]) <= int(choose[1]) <= 200:
        return Fraction(math.comb(int(choose[1]),int(choose[2]))), 'n! / (k! * (n-k)!)', 'Unordered selections without replacement.'
    # Explicit annual compounding; never infer payment schedules or fees.
    compound = re.fullmatch(r'(?:what is (?:the )?(?:final )?(?:amount|value) (?:of )?)?\$(' + N + r')\s+(?:at|earning)\s+(' + N + r')\s*%\s+(?:annual interest\s+)?compounded annually\s+(?:for|after)\s+(\d{1,2})\s+years?',t)
    if compound and Fraction(compound[1])>=0 and Fraction(compound[2])>=0:
        p,r,y=Fraction(compound[1]),Fraction(compound[2])/100,int(compound[3])
        return p*(1+r)**y,'amount = principal * (1 + annual_rate)^years','Annual compounding, no fees or additional payments.'
    # Elementary probability only when fairness is explicit.
    coins = re.fullmatch(r'(?:what is (?:the )?)?probability of (exactly|at least|at most)\s+(\d{1,2})\s+heads?\s+in\s+(\d{1,2})\s+(?:fair coin (?:flips|tosses)|(?:flips|tosses) of a fair coin)', t)
    if coins and 0 <= int(coins[2]) <= int(coins[3]) <= 20:
        k,n=int(coins[2]),int(coins[3])
        eligible=[i for i in range(n+1) if (i==k if coins[1]=='exactly' else i>=k if coins[1]=='at least' else i<=k)]
        return Fraction(sum(math.comb(n,i) for i in eligible),2**n),'sum C(n,k) / 2^n over the requested head counts','Independent fair flips.'
    dice = re.fullmatch(r'(?:what is (?:the )?)?probability (?:of|that)\s+(?:a )?sum\s+(?:of|is)\s+(\d{1,2})\s+(?:with|on|when rolling)\s+(two|2)\s+fair\s+(?:six[- ]sided\s+)?dice',t)
    if dice:
        target=int(dice[1]);count=sum(a+b==target for a,b in itertools.product(range(1,7),repeat=2))
        return Fraction(count,36),'count ordered dice outcomes with the requested sum / 36','Two independent fair six-sided dice.'
    # A complete travel relation; quantities keep compatible units.
    travel = re.fullmatch(r'(?:a |the )?(?:car|train|cyclist)\s+travels\s+(' + N + r')\s+(km|miles)\s+in\s+(' + N + r')\s+hours?[.;]?\s+what is (?:its|the)\s+(?:average )?speed', t)
    if travel and Fraction(travel[3])>0:
        return Fraction(travel[1])/Fraction(travel[3]), 'average speed = distance / time', 'Units: '+travel[2]+'/hour.'
    duration = re.fullmatch(r'(?:at\s+)?(' + N + r')\s*(km/h|mph)[.;]?\s+how long (?:does|will) it take to travel\s+(' + N + r')\s+(km|miles)',t)
    if duration and Fraction(duration[1])>0 and (duration[2],duration[4]) in {('km/h','km'),('mph','miles')}:
        return Fraction(duration[3])/Fraction(duration[1]),'time = distance / constant speed','Result in hours; assumes constant speed.'
    average = re.fullmatch(r'(?:the )?average of (\d{1,2}) numbers is (' + N + r')[.;]? the first (\d{1,2}) (?:numbers )?are ([\d. \-]+(?: and [\d.\-]+)?)[.;]? what is the (?:last|missing) number',t)
    if average:
        count,mean,known=int(average[1]),Fraction(average[2]),int(average[3])
        values=[Fraction(x) for x in re.findall(N,average[4])]
        if 1<count<=20 and known==count-1 and len(values)==known:
            return count*mean-sum(values),'missing = count * mean - sum(known values)',''
    return None
