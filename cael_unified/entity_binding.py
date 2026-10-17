"""Authored deterministic entity addresses for non-neural language counts."""
import re

COMMON=set(('A An The At In On For To By With Without After Before During Until While When If Because Since As Although '
    'And But Or So Then Now Later First Finally One Two Both Each Every Everyone Someone Nobody Neither Only '
    'No All Some Most This That These Those It Its There Here They Their Them He His She Her We Our You Your I '
    'What Which Who Why How Where Does Do Did Is Are Was Were Can Could Would Will Should Please Choose Select '
    'Question Answer Context Story Given Facts Suppose True False Mr Mrs Ms Dr Miss Teacher Coach Mom Dad '
    'Good Great Wonderful Suddenly Unfortunately Fortunately Meanwhile However Instead Once Despite').lower().split())
ADDRESSES=('personalpha','personbeta','persongamma','persondelta','personepsilon','personzeta','personeta','persontheta',
           'personiota','personkappa','personlambda','personmu')


def bindings(context):
    found={}
    for match in re.finditer(r"\b[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\b",context):
        word=match[0].lower()
        if word not in COMMON and word not in found and len(found)<len(ADDRESSES):
            found[word]=ADDRESSES[len(found)]
    return found


def replace(text,mapping):
    if not mapping:
        return text
    return re.sub(r'\b(?:'+'|'.join(re.escape(word) for word in sorted(mapping,key=len,reverse=True))+r')\b',
                  lambda match:mapping[match[0].lower()],text,flags=re.I)


def normalize(context,endings=()):
    mapping=bindings(context)
    return replace(context,mapping),[replace(ending,mapping) for ending in endings],mapping
