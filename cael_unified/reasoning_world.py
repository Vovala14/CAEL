"""Local packet automaton for bounded chronological fact/ownership scenarios."""
from dataclasses import dataclass, field
import re
from .reasoning_logic import Unparsed, sentences


@dataclass
class Cell:
    name: str
    kind: str
    locations: set = field(default_factory=set)
    excluded: set = field(default_factory=set)
    owner: str | None = None
    support: set = field(default_factory=set)
    history: list = field(default_factory=list)


class WorldCA:
    def __init__(self, model):
        self.model = model
        self.cells = {}
        self.gifts = []

    def event(self, statement):
        statement = statement.lower().strip(' .')
        uncertain = re.fullmatch(r'(.+?) is either in (?:the )?(.+?) or (?:the )?(.+)', statement)
        if uncertain:
            return ('uncertain', uncertain[1], uncertain[2], uncertain[3])
        negative = re.fullmatch(r'(.+?) is (?:not|no longer) in (?:the )?(.+)', statement)
        if negative:
            return ('exclude', negative[1], negative[2])
        located = re.fullmatch(r'(.+?) is in (?:the )?(.+)', statement)
        if located:
            return ('move', located[1], located[2])
        for phrase, operation in sorted(self.model.get('events', {}).items(), key=lambda row: -len(row[0])):
            if operation=='give':
                match=re.fullmatch(r'([a-z][a-z -]*?) '+re.escape(phrase)+r' (?:the )?(.+?) to (.+)',statement)
                if match:
                    return ('give',match[1],match[2],match[3])
                continue
            match = re.fullmatch(r'([a-z][a-z -]*?) ' + re.escape(phrase) + r' (?:the )?(.+?)(?: there)?', statement)
            if match:
                return (operation, match[1], match[2])
        raise Unparsed('Unrecognized event: ' + statement[:100])

    @staticmethod
    def locate(cell, locations, support):
        locations = set(locations)
        if locations != cell.locations and len(locations) == 1:
            cell.history.append((next(iter(locations)), set(support)))
        cell.locations, cell.excluded, cell.support = locations, set(), set(support)

    def apply(self, event, index):
        op, actor, value, *extra = event
        if actor not in self.cells:
            self.cells[actor] = Cell(actor, 'actor')
        if op in ('take', 'drop','give') and value not in self.cells:
            self.cells[value] = Cell(value, 'object')
        if op=='give':
            if extra[0] not in self.cells:
                self.cells[extra[0]]=Cell(extra[0],'actor')
            self.gifts.append((actor,value,extra[0],index))
        actor_cell = self.cells[actor]
        packet = dict(op=op, actor=actor, value=value, extra=extra, support={index} | actor_cell.support,
                      locations=set(actor_cell.locations))
        rows = list(self.cells.values())
        carriers = [None] * len(rows)
        carriers[0] = packet
        # A packet moves one neighbouring cell per synchronous tick. Each cell
        # reads only its own state and its local packet, as in the story CA.
        for _ in range(len(rows)):
            following = [None] * len(rows)
            for position, cell in enumerate(rows):
                message = carriers[position]
                if message is None:
                    continue
                if op in ('move', 'uncertain', 'exclude') and (cell.name == actor or cell.owner == actor):
                    if op == 'move':
                        self.locate(cell, {value}, {index} if cell.name == actor else cell.support | {index})
                    elif op == 'uncertain':
                        self.locate(cell, {value, extra[0]}, {index})
                    else:
                        cell.locations = set()
                        cell.excluded = {value}
                        cell.support = {index}
                elif op in ('take', 'drop','give') and cell.name == value:
                    if op == 'drop' and cell.owner not in (None, actor):
                        raise Unparsed('An actor cannot drop an object held by someone else')
                    cell.owner = extra[0] if op=='give' else actor if op == 'take' else None
                    self.locate(cell, message['locations'], message['support'])
                if position + 1 < len(rows):
                    following[position + 1] = message
            carriers = following

    def query(self, context, question):
        self.cells = {}
        self.gifts = []
        for index, statement in enumerate(sentences(context), 1):
            self.apply(self.event(statement), index)
        question = question.lower().strip(' ?.!.')
        gift_forms=[(r'what did (.+?) give to (.+)',lambda m,g:g[0]==m[1] and g[2]==m[2],1),
                    (r'who (?:gave|handed) (?:the )?(.+?) to (.+)',lambda m,g:g[1]==m[1] and g[2]==m[2],0),
                    (r'who (?:gave|handed) (?:the )?(.+)',lambda m,g:g[1]==m[1],0),
                    (r'who received (?:the )?(.+)',lambda m,g:g[1]==m[1],2),
                    (r'who did (.+?) give (?:the )?(.+?) to',lambda m,g:g[0]==m[1] and g[1]==m[2],2)]
        for pattern,accept,field in gift_forms:
            match=re.fullmatch(pattern,question)
            if match:
                matching=[g for g in self.gifts if accept(match,g)]
                if field==1 and len({gift[field] for gift in matching})>1:
                    return dict(answer='unknown',support=sorted(gift[3] for gift in matching),depth=1)
                gift=matching[-1] if matching else None
                return dict(answer=gift[field] if gift else 'unknown',support=[gift[3]] if gift else [],depth=1)
        match = re.fullmatch(r'where (?:is|was) (?:the )?(.+?)(?: before (?:the )?(.+))?', question)
        if match:
            name, before = match.groups()
            cell = self.cells.get(name)
            if cell is None:
                return dict(answer='unknown', support=[], depth=0)
            if before:
                # Last visit to the named location, with the preceding distinct place.
                positions = [i for i, (place, _) in enumerate(cell.history) if place == before and i > 0]
                if not positions:
                    return dict(answer='unknown', support=[], depth=0)
                i = positions[-1]
                answer, support = cell.history[i - 1]
                return dict(answer=answer, support=sorted(support | cell.history[i][1]), depth=3)
            answer = next(iter(cell.locations)) if len(cell.locations) == 1 else 'unknown'
            return dict(answer=answer, support=sorted(cell.support), depth=2 if cell.kind == 'object' else 1)
        match = re.fullmatch(r'is (.+?) in (?:the )?(.+)', question)
        if match:
            cell = self.cells.get(match[1])
            location = match[2]
            answer = 'unknown'
            if cell:
                if location in cell.excluded:
                    answer = 'no'
                elif cell.locations:
                    answer = 'yes' if cell.locations == {location} else 'maybe' if location in cell.locations else 'no'
            return dict(answer=answer, support=sorted(cell.support) if cell else [], depth=1)
        match = re.fullmatch(r'(?:how many objects is|what is) (.+?) carrying', question)
        if match:
            actor = match[1]
            if actor not in self.cells:
                return dict(answer='unknown', support=[], depth=0)
            held = sorted(cell.name for cell in self.cells.values() if cell.owner == actor)
            support = sorted(set().union(*(cell.support for cell in self.cells.values() if cell.kind == 'object')))
            if question.startswith('how many'):
                answer = ['none', 'one', 'two', 'three', 'four', 'five'][len(held)] if len(held) < 6 else str(len(held))
            else:
                answer = ','.join(held) if held else 'nothing'
            return dict(answer=answer, support=support, depth=2)
        match = re.fullmatch(r'who (?:has|holds|owns|is carrying) (?:the )?(.+)', question)
        if match:
            cell = self.cells.get(match[1])
            return dict(answer=cell.owner if cell and cell.owner else 'unknown', support=sorted(cell.support) if cell else [], depth=1)
        raise Unparsed('Unrecognized state question')
