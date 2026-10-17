"""Bounded observer-belief packet automaton; authored parser, fitted integer updates."""
import json
from pathlib import Path
import re
from .reasoning_logic import Unparsed, sentences

MODEL = Path(__file__).resolve().parents[1] / 'models/cael-social-v1/model.json'
NAME = r'([a-z][a-z -]*?)'


class SocialCA:
    def __init__(self, path=MODEL):
        self.model = json.loads(Path(path).read_text()) if Path(path).is_file() else None

    def query(self, context, question):
        question = question.lower().strip(' ?.')
        belief = re.fullmatch(r'where (?:will|would|does) ' + NAME + r' (?:look|search)(?: first)? for (?:the )?' + NAME, question)
        belief = belief or re.fullmatch(r'where does ' + NAME + r' (?:think|believe) (?:the )?' + NAME + r' is', question)
        knows = re.fullmatch(r'does ' + NAME + r' know where (?:the )?' + NAME + r' is', question)
        reality = re.fullmatch(r'where is (?:the )?' + NAME + r' really', question)
        if not self.model or not (belief or knows or reality):
            raise Unparsed('Not a supported observer-belief question')
        self.cells, self.world = {}, {}
        self.scene = None
        for index, statement in enumerate(sentences(context), 1):
            self.event(statement.lower().strip(' .'), index)
        if reality:
            value, proof = self.world.get(reality[1], (None, set()))
        else:
            actor, item = (belief or knows).groups()
            cell = self.cells.get(actor, {})
            value, proof = cell.get('beliefs', {}).get(item, (None, set()))
        if knows:
            actual, support = self.world.get(item, (None, set()))
            answer = 'unknown' if actual is None or value is None else 'yes' if value == actual else 'no'
            proof = proof | support
        else:
            answer = value or 'unknown'
        return dict(answer=answer, support=sorted(proof), depth=len(proof), observer_state=True)

    def cell(self, actor):
        return self.cells.setdefault(actor, dict(present=False, beliefs={}, presence_support=set()))

    def packet(self, item, place, witnesses, index, extra=()):
        # Synchronous radius-one propagation; each receiver reads only itself
        # and the packet arriving from its immediate left neighbour.
        rows = list(self.cells.items())
        carriers = [None] * len(rows)
        if rows:
            carriers[0] = (item, place, frozenset(witnesses), {index} | set(extra))
        for _ in rows:
            following = [None] * len(rows)
            for position, (actor, cell) in enumerate(rows):
                message = carriers[position]
                if message is not None:
                    key, value, audience, support = message
                    observed = int(actor in audience)
                    opcode = self.model['updates'][str(observed)]
                    if opcode == 1:
                        cell['beliefs'][key] = (value, support | cell['presence_support'])
                    elif key in cell['beliefs']:
                        old_value, old_support = cell['beliefs'][key]
                        cell['beliefs'][key] = (old_value, old_support | {index} | cell['presence_support'])
                    if position + 1 < len(rows):
                        following[position + 1] = message
            carriers = following

    def event(self, text, index):
        entered = re.fullmatch(NAME + r' (entered|returned to|left) the ([a-z ]+)', text)
        if entered:
            actors, verb, room = entered.groups()
            if self.scene is not None and room != self.scene:
                raise Unparsed('Belief tracking currently supports one shared room')
            self.scene = room
            for actor in actors.split(' and '):
                cell = self.cell(actor)
                cell['present'] = verb != 'left'
                cell['presence_support'] = {index}
            return
        moves = '|'.join(re.escape(word) for word in self.model['move_words'])
        moved = re.fullmatch(NAME + r' (' + moves + r') (?:the )?' + NAME + r' (?:in|into|to|inside) (?:the )?' + NAME, text)
        if moved:
            actor, _, item, place = moved.groups()
            cell = self.cell(actor)
            if not cell['present']:
                # A named action establishes the actor's participation, but
                # never silently brings a previously absent observer back.
                if cell['presence_support']:
                    raise Unparsed('Absent actor cannot move an object in the shared room')
                cell['present'] = True
            self.world[item] = (place, {index})
            self.packet(item, place, [name for name, c in self.cells.items() if c['present']], index)
            return
        saw = re.fullmatch(NAME + r' (?:saw|sees) (?:the )?' + NAME + r' (?:in|inside) (?:the )?' + NAME, text)
        if saw:
            actors, item, place = saw.groups()
            witnesses = actors.split(' and ')
            for actor in witnesses:
                self.cell(actor)
            self.world[item] = (place, {index})
            self.packet(item, place, witnesses, index)
            return
        report = re.fullmatch(NAME + r' told ' + NAME + r' that (?:the )?' + NAME + r' (?:is|was) (?:in|inside) (?:the )?' + NAME, text)
        if report:
            source, recipient, item, place = report.groups()
            self.cell(source)
            self.cell(recipient)
            # A report establishes beliefs, not the truth of the report.
            self.packet(item, place, [recipient], index)
            return
        initial = re.fullmatch(r'(?:the )?' + NAME + r' (?:is|was) (?:in|inside) (?:the )?' + NAME, text)
        if initial:
            self.world[initial[1]] = (initial[2], {index})
            return
        raise Unparsed('Unrecognized observer event: ' + text[:100])

    def choose(self, context, endings):
        """Answer only a recognized continuation; otherwise explicitly abstain."""
        parts = re.split(r'(?<=[.!?])\s+|\n+', context.strip())
        if len(parts) < 2:
            return None
        prefix, tail = ' '.join(parts[:-1]), parts[-1].strip()
        tail = re.sub(r'(?i)\b(?:will|would) look (?:first )?for (.+?) in(?: the)?$', r'will look for \1', tail)
        tail = re.sub(r'(?i)\b(?:thinks|believes) (?:that )?(?:the )?(.+?) is in(?: the)?$', r'thinks \1 is', tail)
        match = re.fullmatch(r'(?i)([a-z][a-z -]*?) (will look for .+)', tail)
        question = 'Where ' + match[1] + ' ' + match[2] if match else None
        if match:
            question = 'Where will ' + match[1] + ' look for ' + match[2].split('look for ', 1)[1]
        think = re.fullmatch(r'(?i)([a-z][a-z -]*?) thinks (.+?) is', tail)
        if think:
            question = f'Where does {think[1]} think {think[2]} is'
        if question is None:
            return None
        try:
            result = self.query(prefix, question)
        except Unparsed:
            return None
        if result['answer'] == 'unknown':
            return None
        matching = [i for i, ending in enumerate(endings) if re.sub(r'^(?:in |the |in the )+', '', ending.lower().strip(' .')) == result['answer']]
        return matching[0] if len(matching) == 1 else None
