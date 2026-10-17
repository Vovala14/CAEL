"""Bounded transitive relation and shortest-path solvers over stated premises."""
from collections import deque
import re
from .reasoning_logic import Unparsed, sentences

INVERSE = {'north':'south', 'south':'north', 'east':'west', 'west':'east'}


def relations(context, question):
    bigger, graph = {}, {}
    mode = None
    def edge(a,b,index):
        bigger.setdefault((a,b), {index})
    for index, statement in enumerate(sentences(context), 1):
        statement = re.sub(r'(?i)\bthe ', '', statement).lower()
        size = re.fullmatch(r'(.+?) (?:is bigger than|fits inside|is smaller than) (.+)', statement)
        direction = re.fullmatch(r'(.+?) is (north|south|east|west) of (.+)', statement)
        if size:
            if mode == 'path':
                raise Unparsed('Mixed relation domains')
            mode = 'size'
            a,b=size.groups()
            edge(a,b,index) if 'bigger than' in statement else edge(b,a,index)
        elif direction:
            if mode == 'size':
                raise Unparsed('Mixed relation domains')
            mode = 'path'
            a,d,b = direction.groups()
            graph.setdefault(b, []).append((a,d,index))
            graph.setdefault(a, []).append((b,INVERSE[d],index))
        else:
            raise Unparsed('Unrecognized relation premise')
    question = re.sub(r'(?i)\bthe ', '', question.lower().strip(' ?.!.'))
    if mode == 'size':
        if len({name for pair in bigger for name in pair})>64:
            raise Unparsed('Use at most 64 related objects')
        for _ in range(24):
            old = dict(bigger)
            outgoing={}
            for (c,d),other in old.items():
                outgoing.setdefault(c,[]).append((d,other))
            for (a,b), support in old.items():
                for d,other in outgoing.get(b,[]):
                    if a != d:
                        bigger.setdefault((a,d), support | other)
            if len(old) == len(bigger):
                break
        if any((b,a) in bigger for a,b in bigger):
            return dict(answer='conflicting', support=[], depth=0)
        match = re.fullmatch(r'is (.+?) bigger than (.+)', question)
        if match:
            a,b = match.groups()
        else:
            match = re.fullmatch(r'does (.+?) fit in (.+)', question)
            if not match:
                raise Unparsed('Unrecognized size question')
            b,a = match.groups()
        pair = (a,b) if (a,b) in bigger else (b,a)
        return dict(answer='yes' if (a,b) in bigger else 'no' if (b,a) in bigger else 'unknown',
                    support=sorted(bigger.get(pair, [])), depth=len(bigger.get(pair, [])))
    match = re.fullmatch(r'how (?:do you go|to get|do i get) from (.+?) to (.+)', question)
    if mode == 'path' and match:
        start, target = match.groups()
        queue = deque([(start, [], [])]); visited={start}
        while queue:
            node, path, support = queue.popleft()
            if node == target:
                return dict(answer=','.join(step[0] for step in path), directions=path, support=sorted(support), depth=len(path))
            for neighbour,direction,index in graph.get(node, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append((neighbour,path + [direction],support + [index]))
        return dict(answer='unknown', support=[], depth=0)
    raise Unparsed('Unrecognized relation question')
