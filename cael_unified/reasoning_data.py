"""Read only selected public text archive members; never execute or extract them."""
from collections import defaultdict
import hashlib
import json
import re
import tarfile
import zipfile
from .bundle import ROOT

DATA = ROOT / 'research/reasoning_024'
TASKS = (1,2,3,5,6,7,8,9,10,15,18,19)


def babi(task, split):
    with tarfile.open(DATA / 'babi.tar.gz','r:gz') as archive:
        matches = [member for member in archive.getmembers() if f'/en-10k/qa{task}_' in member.name and member.name.endswith(f'_{split}.txt')]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous public task member')
        lines = archive.extractfile(matches[0]).read().decode('utf-8').splitlines()
    context = []
    for line in lines:
        number, text = line.split(' ',1)
        if number == '1':
            context = []
        if '\t' in text:
            question,answer,support = text.split('\t')
            yield dict(context=list(context), question=question.strip(), answer=answer.strip(), support=[int(v) for v in support.split()], task=task)
        else:
            context.append((int(number),text.strip()))


def pronto():
    with zipfile.ZipFile(DATA / 'prontoqa.zip') as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.json'):
                continue
            data = json.loads(archive.read(name))
            for identifier,row in data.items():
                for slot,example in row.items():
                    if not isinstance(example,dict) or 'question' not in example or 'query' not in example:
                        continue
                    yield dict(file=name, id=identifier, slot=slot, **example)


def signature(context):
    return hashlib.sha256(' '.join(context.lower().split()).encode()).hexdigest()
