"""The Storyteller: very short stories about any character and goal the user names, and their rewrites.

"Can you write a very short story about a parrot who learns to say sorry?" -> a character (a parrot), what they learn or
want (to say sorry), and a five-beat plan: a setting, a want or flaw, a moment that goes wrong, a turn, and an ending.
The plan is filled from a few interchangeable patterns (chosen by the subject, so the same request gives the same
story), keeping the character and the goal consistent throughout. "A happier ending", "a sad ending", "make it
funnier", "make it shorter" rewrite the last beat or the whole length. Authored patterns; no model.
"""
import re

ASK = re.compile(r"(?i)\b(?:write|tell|make|give|create)\b[^.?!]{0,25}?\b(?:a |an )?(?:very |really )?(?:short |little |quick |tiny |bedtime |funny |sweet )*"
                 r"(?:story|tale|fable)\b\s+(?:about|of|where|in which)\s+(.+?)\s*[.?!]?\s*$")
NAMES = ['Pip', 'Juno', 'Mabel', 'Otto', 'Tilly', 'Rufus', 'Nell', 'Bramble', 'Kiki', 'Fig']
PLACES = ['a small town by the sea', 'a busy city flat', 'a quiet village at the edge of a forest', 'an old house full of creaky stairs',
          'a sunny corner shop', 'a garden that never stopped growing']


def parse(text):
    m = ASK.search(text)
    if not m:
        return None
    about = m[1].strip()
    about = re.sub(r"(?i)\s+(?:please|for me|for my \w+)$", '', about)
    c = re.match(r"(?i)(?:a|an|the|my|our)?\s*((?:[a-z]+ ){0,2}?[a-z]+?)\s+(?:who|that|which)\s+(.+)$", about)
    if c:
        who, goal = c[1].lower(), c[2]
    else:
        c = re.match(r"(?i)(?:a|an|the|my|our)?\s*((?:[a-z]+ ){0,2}?[a-z]+)$", about)
        if not c:
            return None
        who, goal = c[1].lower(), None
    goal = re.sub(r"(?i)^(?:is |was )", '', goal) if goal else None
    return dict(who=who, goal=goal)


def third(goal):
    """'learns to say sorry' -> ('learn', 'to say sorry'), for use as 'wanted to learn to say sorry'."""
    m = re.match(r"(?i)(\w+?)(?:e?s)?\b\s*(.*)$", goal)
    verb, rest = (m[1], m[2]) if m else (goal, '')
    base = {'learn': 'learn', 'want': 'want', 'tri': 'try', 'find': 'find', 'go': 'go', 'make': 'make', 'love': 'love', 'can': 'can'}.get(verb.lower(), verb)
    return base, rest


IRREGULAR = {'is': 'was', 'are': 'were', 'has': 'had', 'have': 'had', 'can': 'could', "can't": "couldn't", 'cannot': 'could not',
             "won't": "wouldn't", "doesn't": "didn't", "isn't": "wasn't", 'keeps': 'kept', 'keep': 'kept', 'loves': 'loved', 'finds': 'found',
             'gets': 'got', 'goes': 'went', 'makes': 'made', 'dreams': 'dreamed', 'lives': 'lived', 'thinks': 'thought', 'meets': 'met',
             'runs': 'ran', 'eats': 'ate', 'sleeps': 'slept', 'digs': 'dug', 'steals': 'stole', 'hides': 'hid', 'swims': 'swam', 'sings': 'sang',
             'flies': 'flew', 'falls': 'fell', 'takes': 'took', 'sees': 'saw', 'says': 'said', 'tells': 'told', 'wins': 'won', 'loses': 'lost',
             'leaves': 'left', 'brings': 'brought', 'buys': 'bought', 'catches': 'caught', 'fights': 'fought', 'feels': 'felt', 'hears': 'heard'}


def past(clause):
    """'wants to fly' -> 'wanted to fly'; 'keeps digging under the fence' -> 'kept digging under the fence'."""
    words = clause.split(' ', 1)
    v, rest = words[0], (' ' + words[1] if len(words) > 1 else '')
    if v.lower() in IRREGULAR:
        return IRREGULAR[v.lower()] + rest
    if v.endswith('ies'):
        return v[:-3] + 'ied' + rest
    if v.endswith('es') and v[-3] in 'sxz' or v.endswith(('ches', 'shes')):
        return v[:-2] + 'ed' + rest
    if v.endswith('s') and not v.endswith('ss'):
        base = v[:-1]
        return (base + 'd' if base.endswith('e') else base + 'ed') + rest
    return clause


def kind_of(goal):
    """The shape of the story the goal asks for, and its key words."""
    g = (goal or '').strip().rstrip('.')
    m = re.match(r"(?i)(?:is |was |gets |feels )?(?:scared|afraid|frightened|terrified|nervous) of (.+)$", g)
    if m:
        return 'fear', m[1]
    m = re.match(r"(?i)(?:keeps?|always|won'?t stop) (\w+ing)\b\s*(.*)$", g)
    if m:
        return 'habit', (m[1] + (' ' + m[2] if m[2] else '')).strip()
    m = re.match(r"(?i)(?:can'?t|cannot|couldn'?t|is unable to|never) (.+)$", g)
    if m:
        return 'cannot', m[1]
    m = re.match(r"(?i)(?:wants?|wishes|dreams|hopes) (?:to |of )?(.+)$", g)
    if m:
        return 'want', m[1]
    return 'other', g


def base_verb(doing):
    """'digging under the fence' -> 'dig'; 'barking at the postman' -> 'bark'; 'running away' -> 'run'."""
    v = doing.split(' ', 1)[0].lower()
    if v.endswith('ing'):
        v = v[:-3]
        if len(v) > 2 and v[-1] == v[-2] and v[-1] not in 'lsz':
            v = v[:-1]
        elif v in ('chas', 'hid', 'mak', 'bit', 'tak', 'driv', 'smil', 'writ', 'rid', 'danc', 'giv', 'liv', 'mov', 'sav', 'shar', 'skat', 'bak',
                   'wav', 'chok', 'hop', 'escap', 'explor', 'squeez', 'sneez', 'com', 'leav', 'serv', 'argu', 'us', 'los', 'clos'):
            v += 'e'                        # making -> make, hiding -> hide, chasing -> chase
    return v


def plural(x):
    x = x.strip()
    return x if x.endswith('s') else x + 's'


def tell(req, ending='happy', length='short'):
    who, goal = req['who'], req['goal']
    seed = sum(map(ord, who + (goal or '')))
    name = NAMES[seed % len(NAMES)]
    place = PLACES[seed % len(PLACES)]
    kind, what = kind_of(goal)
    learning = goal and re.match(r"(?i)(?:(?:wants?|tries|wishes|hopes|needs) to )?learn(?:s|ed)? (?:how )?to (.+)$", goal)
    if learning:
        skill = learning[1].rstrip('.')
        beats = [f"In {place} lived a {who} called {name}, who could do many things, but could not {skill}.",
                 f"Every time something went wrong, {name} would look away and say nothing, and the others slowly stopped asking {name} to join in.",
                 f"One morning {name} knocked over a friend's favourite thing, and the room went very quiet.",
                 f"{name} thought about all the times before, took a deep breath, and tried something new: {name} managed to {skill}, a little shakily, but clearly."]
        endings = {'happy': f"The friend smiled, and from that day on {name} found it got easier every time; soon nobody could remember the old, silent {name} at all.",
                   'happier': f"The friend laughed, hugged {name}, and the whole room cheered. That evening they all celebrated together, and {name} "
                              f"discovered that being able to {skill} made {name} the happiest {who} in town.",
                   'funny': f"It went so well that {name} couldn't stop. By teatime {name} had tried to {skill} to the postman, the goldfish and a lamp post, "
                            f"and the lamp post, everyone agreed, took it very well.",
                   'sad': f"But it was too late to mend the thing that had broken. {name} learned the lesson anyway, and never let a chance pass by again."}
    elif kind == 'fear':
        them = what.rstrip('.')
        many = bool(re.search(r"(?i)(?:s|mice|people|children|geese|sheep|fish)$", them)) or them.lower().startswith(('other ', 'all '))
        one = them if many or re.match(r"(?i)(?:the|a|an|my|its|his|her) ", them) else ('an ' if them[:1] in 'aeiou' else 'a ') + them
        shy = {'cat': "whiskers droop", 'kitten': "whiskers droop", 'mouse': "whiskers quiver", 'rabbit': "ears flatten", 'dog': "ears flatten",
               'puppy': "ears flatten", 'fox': "ears flatten", 'horse': "ears flatten"}.get(who)
        beats = [f"In {place} lived a {who} called {name}, who was brave about almost everything, except {them}.",
                 f"Just the thought of {them} made {name}'s {shy} and {name}'s tail tuck itself away." if shy
                 else f"Just the thought of {them} made {name} want to hide under the nearest table.",
                 f"Then one evening, there {'they were' if many else 'it was'}: {one}, right in the middle of {name}'s favourite spot.",
                 f"{name} froze. But as {name} looked closer, {name} saw something surprising: {'they' if many else 'it'} looked every bit as frightened as {name} felt."]
        endings = {'happy': f"So {name} sat down very slowly, and nobody ran. By morning they were sharing the warm spot, and {name} wasn't scared any more.",
                   'happier': f"So {name} sat down very slowly, and nobody ran. Before long they were the best of friends, and the whole house "
                              f"talked about the {who} and {'the ' + them if not many else 'the ' + them.replace('other ', '')} who did everything together.",
                   'funny': f"So {name} took a deep breath and said, very politely, \"After you.\" {'They' if many else 'It'} said, \"No, after you.\" "
                            f"They are, as far as anyone knows, still standing in the doorway being polite to each other.",
                   'sad': f"But before {name} could be brave, the moment passed and they both ran off in opposite directions. Still, {name} "
                          f"kept the memory, and the next time felt a little less scary."}
    elif kind == 'habit':
        doing = what.rstrip('.')
        beats = [f"In {place} lived a {who} called {name}, who {past('keeps ' + doing)}, no matter what anyone said.",
                 f"The family tried everything: a stern voice, a special treat, even a sign that said \"PLEASE STOP\", which {name} could not read.",
                 f"One day they followed {name} to see why, and found that {name} wasn't being naughty at all: {name} was looking for something.",
                 f"Next door, a small, lonely friend had been waiting on the other side all along."]
        endings = {'happy': f"So the family made a proper gate between the two gardens, and {name} never needed to {base_verb(doing)} again.",
                   'happier': f"So the family made a proper gate between the two gardens. Now the two friends visit every afternoon, and both families "
                              f"say it's the best thing that ever happened on their street.",
                   'funny': f"But when the family finally let {name} carry on, {name} came back very proudly with the neighbour's slipper, two tennis balls, "
                            f"a garden gnome and, somehow, a cheese sandwich. Nobody ever found out where the sandwich came from.",
                   'sad': f"But the friend moved away before they ever met properly. {name} still checks the old spot sometimes, just in case."}
    elif kind == 'cannot':
        thing = what.rstrip('.')
        beats = [f"In {place} lived a {who} called {name}, who couldn't {thing}, however hard {name} tried.",
                 f"{name} tried everything anyone suggested, one idea after another, and none of it worked.",
                 f"Late one night, tired and fed up, {name} met a very old owl who had seen this kind of problem before.",
                 f"\"Stop trying so hard,\" said the owl, \"and do the thing you love most instead.\" So {name} did."]
        endings = {'happy': f"And while {name} was busy enjoying it, without even noticing, {name} managed to {thing} after all.",
                   'happier': f"And while {name} was busy enjoying it, {name} managed to {thing} after all, and woke up to find all {name}'s friends had come to celebrate.",
                   'funny': f"It worked so well that {name} managed to {thing} in the bath, at the breakfast table and once, briefly, halfway up a tree. "
                            f"The owl said that was rather overdoing it.",
                   'sad': f"It didn't work that night, but {name} wasn't alone any more, and that made the long hours much easier."}
    else:
        want = past(goal.rstrip('.')) if goal else 'wanted to find somewhere to belong'
        beats = [f"In {place} lived a {who} called {name}" + (f", who {want}." if goal else '.'),
                 f"{name} had a plan, but plans have a way of going sideways.",
                 f"Just when it seemed everything had gone wrong, {name} noticed something nobody else had: a small, simple way through.",
                 f"With a bit of courage and a lot of help from a new friend, {name} tried it."]
        endings = {'happy': f"It worked, and {name} went to sleep that night smiling.",
                   'happier': f"It worked better than anyone had hoped; there was a party, a new best friend, and {name} was happier than ever.",
                   'funny': f"It worked, though not at all the way anyone expected: {name} ended up famous, mostly for the wrong reasons, and wore a small hat about it for weeks.",
                   'sad': f"It didn't quite work, but {name} had found a friend along the way, which mattered more."}
    story = beats + [endings.get(ending, endings['happy'])]
    if length == 'shorter':
        story = [story[0], story[2], story[-1]]
    title = f"*{name} the {who.title()}*"
    return title + '\n\n' + ' '.join(story)


def respond(messages):
    users = [m['content'] for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1]
    req = parse(last)
    if req:
        return dict(route='chat/story', response=tell(req), sources=[], details='A short story from a five-beat plan (story_agent.py).')
    m = re.search(r"(?i)\b(happier|happy|sad|sadder|funnier|funny|sillier|silly|shorter)\b[^.?!]{0,20}\b(?:ending|version|end|story|one)?", last)
    if m and len(last.split()) <= 18 and re.search(r"(?i)\b(?:give|make|change|could|can|rewrite|write)\b", last):
        for t in reversed(users[:-1][-3:]):
            req = parse(t)
            if req:
                kind = m[1].lower()
                ending = {'happier': 'happier', 'happy': 'happier', 'sad': 'sad', 'sadder': 'sad', 'funnier': 'funny', 'funny': 'funny',
                          'sillier': 'funny', 'silly': 'funny'}.get(kind, 'happy')
                length = 'shorter' if kind == 'shorter' else 'short'
                lead = {'happier': "Here it is with a happier ending:", 'sad': "Here it is with a sadder ending:", 'shorter': "Here's a shorter version:",
                        'funny': "Here it is with a funnier ending:"}.get(
                    ending if kind != 'shorter' else 'shorter', "Here's another version:")
                return dict(route='chat/story', response=f"{lead}\n\n{tell(req, ending, length)}", sources=[], details='The story rewritten (story_agent.py).')
    return None
