"""The Planner's diary: what the user has on which day, kept from what they said in the conversation.

"On Monday I have a team meeting at 9 and the gym at 6. On Wednesday I have lunch with Priya at noon."
"Add a call with the bank on Tuesday at 4."   "Move the supplier call to Thursday at 10."   "Cancel the gym."
"What do I have on Tuesday and Wednesday?"    "What's on Thursday?"    "When is the call with the bank?"

The diary is rebuilt from the user's turns each time (nothing is stored), so a moved or cancelled entry is always
current. A telling turn is confirmed with the entries as understood; a question is answered with the day's entries in
time order. Only days of the week and today/tomorrow are read; anything else is left to the other agents.
"""
import re

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DAY = r'(?:mon|tues|wednes|thurs|fri|satur|sun)days?'
TIME = (r'(?:\d{1,2}(?:[:.]\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|noon|midday|midnight|half past \d{1,2}|quarter (?:past|to) \d{1,2})'
        r'(?:\s+in the (?:morning|afternoon|evening))?')
HAVE = r"(?:i have|i've got|i got|i'm having|there's|there is|we have|i need to go to|i'm going to|i'm at|it's|is)"


def day_of(word):
    w = word.lower().rstrip('s')
    for d in DAYS:
        if w.startswith(d[:3]) and d.startswith(w[:len(d)]):
            return d
    return None


def clean_what(text):
    text = re.sub(r'(?i)^\s*(?:and|then|also|plus|a|an|the|my|our|i have|have|go to|going to|got|there\'s)\s+', '', text.strip(' ,.;:'))
    text = re.sub(r'(?i)^\s*(?:a|an|the|my|our)\s+', '', text)
    text = re.sub(r"(?i)^\s*(?:i'm|i am|i'll be|i will be|we're|we are)\s+", '', text)
    text = re.sub(r"(?i)\bmy\b", 'your', text)
    return text.strip(' ,.;:')


def entries_in(segment):
    """[(what, time or '')] in 'a team meeting at 9 and the gym at 6' / 'lunch with Priya at noon'."""
    out = []
    for part in re.split(r'(?i)\s*(?:,\s*(?:and\s+)?(?:then\s+)?|\s+and\s+(?:then\s+)?|;\s*)', segment.strip(' .')):
        part = part.strip()
        if not part:
            continue
        m = re.search(r'(?i)^(.*?)\s+(?:at|from|@)\s+(' + TIME + r')\s*$', part)
        if m and clean_what(m[1]):
            out.append((clean_what(m[1]), m[2].strip()))
        else:
            m = re.search(r'(?i)^(' + TIME + r')\s*[:\-–]?\s+(.+)$', part)
            if m and re.search(r'[a-z]{3}', m[2]):
                out.append((clean_what(m[2]), m[1].strip()))
            elif clean_what(part) and re.search(r'[a-z]{3}', part) and len(part.split()) <= 8:
                out.append((clean_what(part), ''))
    return out


def tell(text):
    """{day: [(what, time)]} stated in one turn; {} when it tells no diary entries."""
    found = {}
    # "On Monday I have X at 9 and Y at 6." / "Monday I have X at 11, Wednesday Y at 3, and Friday Z at 1."
    # "I've got swimming on Saturday at 9 and a birthday party on Sunday at 3 pm."
    lead = re.match(r"(?i)\s*(?:this week |next week |so |ok(?:ay)?,? )?(?:i have|i've got|i got|i'm having|we have|we've got|there's)\s+(.+)$", text.strip())
    if lead and not re.match(r'(?i)\s*(?:on\s+)?' + DAY, text):
        for part in re.split(r'(?i)\s*(?:,\s*(?:and\s+)?|\s+and\s+|;\s*)', re.split(r'(?<=[.!?])\s+', lead[1])[0].strip(' .')):
            m = re.match(r'(?i)^(.+?)\s+(?:on|this|next)\s+(' + DAY + r')(?:\s+(?:at|from)\s+(' + TIME + r'))?\s*$', part.strip())
            m2 = re.match(r'(?i)^(.+?)\s+(?:at|from)\s+(' + TIME + r')\s+(?:on|this|next)\s+(' + DAY + r')\s*$', part.strip()) if not m else None
            if m and clean_what(m[1]):
                found.setdefault(day_of(m[2]), []).append((clean_what(m[1]), (m[3] or '').strip()))
            elif m2 and clean_what(m2[1]):
                found.setdefault(day_of(m2[3]), []).append((clean_what(m2[1]), m2[2].strip()))
        if found:
            return found
    pieces = re.split(r'(?i)(?:^|(?<=[.;:,])\s*|\s+and\s+|\s+then\s+)(?:on\s+)?(' + DAY + r')\b[,:]?\s*', text)
    if len(pieces) < 3:
        return found
    for i in range(1, len(pieces) - 1, 2):
        day, body = day_of(pieces[i]), pieces[i + 1]
        body = re.split(r'(?<=[.!?])\s+', body.strip())[0]
        body = re.sub(r'(?i)^\s*' + HAVE + r'\s+', '', body).strip(' .,;')
        body = re.sub(r'(?i),?\s*and\s*$', '', body)
        if not day or not body or '?' in body:
            continue
        items = entries_in(body)
        if items:
            found.setdefault(day, []).extend(items)
    return found


ADD = re.compile(r'(?i)^\s*(?:please\s+|can you\s+|could you\s+|oh,?\s+|also,?\s+|and\s+)*(?:add|put|schedule|book|pencil in|note|include|stick)\s+(.+?)\s+(?:on|for)\s+(' + DAY
                 + r')(?:\s+(?:at|from)\s+(' + TIME + r'))?\s*(?:too|as well|please)?[.!]?\s*$')
ADD2 = re.compile(r'(?i)^\s*(?:please\s+|can you\s+|could you\s+|oh,?\s+|also,?\s+|and\s+)*(?:add|put|schedule|book|pencil in|note|include)\s+(.+?)\s+(?:at|from)\s+(' + TIME
                  + r')\s+(?:on|for)\s+(' + DAY + r')\s*(?:too|as well|please)?[.!]?\s*$')
MOVE = re.compile(r'(?i)^\s*(?:please\s+|can you\s+|could you\s+|actually,?\s+|oh,?\s+)*(?:move|shift|push|change|reschedule|bump|switch)\s+(.+?)\s+to\s+(' + DAY
                  + r')?(?:\s*(?:at|to)?\s*(' + TIME + r'))?\s*(?:instead|please)?[.!]?\s*$')
CANCEL = re.compile(r'(?i)^\s*(?:please\s+|can you\s+|could you\s+|actually,?\s+|oh,?\s+)*(?:cancel|remove|delete|drop|scrap|take off|forget)\s+(.+?)(?:\s+(?:on|from)\s+('
                    + DAY + r'))?\s*(?:please)?[.!]?\s*$')
ASK_DAY = re.compile(r"(?i)\b(?:what(?:'s| is| do| have)?|anything|do i have (?:anything|something)|am i (?:free|busy)|what am i doing|how (?:busy|full)|"
                     r"(?:tell|remind) me what)\b[^?.]*?\b(?:on|for)?\s*(" + DAY + r"(?:\s*(?:,|and|or|&)\s*(?:on\s+)?" + DAY + r")*)")
ASK_WHEN = re.compile(r"(?i)^\s*(?:and\s+|so\s+|remind me,?\s+)?(?:when|what day|what time)(?:'s| is| was| do i have| am i| are)\s+(?:the |my |i (?:have|having|seeing|meeting|doing) (?:the |my )?)?(.+?)\s*(?:again)?\?\s*$")


def match(entries, what):
    """Index of the diary entry a phrase refers to ("the supplier call" -> "call with the supplier")."""
    stop = {'the', 'my', 'a', 'an', 'with', 'at', 'on', 'to', 'of', 'for', 'appointment', 'thing', 'one', 'that', 'this', 'session'}
    words = {w.rstrip('s') for w in re.findall(r"[a-z']+", what.lower())} - stop
    best, score = None, 0
    for i, (day, item, time) in enumerate(entries):
        have = {w.rstrip('s') for w in re.findall(r"[a-z']+", item.lower())} - stop
        hit = len(words & have)
        if hit and (hit > score or (hit == score and best is not None and len(have) < len({w for w in re.findall(r"[a-z']+", entries[best][1].lower())}))):
            best, score = i, hit
    return best if score and score >= max(1, (len(words) + 1) // 2) else None


def diary(turns):
    """([(day, what, time)], what the last turn did): the diary after every user turn in order."""
    entries, last_action = [], None
    for t in turns:
        last_action = None
        text = t.strip()
        m = ADD.match(text) or None
        m2 = ADD2.match(text) if not m else None
        if m or m2:
            what, day, time = (clean_what(m[1]), day_of(m[2]), m[3] or '') if m else (clean_what(m2[1]), day_of(m2[3]), m2[2])
            entries.append((day, what, (time or '').strip()))
            last_action = ('added', entries[-1])
            continue
        m = MOVE.match(text)
        if m and (m[2] or m[3]):
            i = match(entries, m[1])
            if i is not None:
                old = entries[i]
                entries[i] = (day_of(m[2]) if m[2] else old[0], old[1], (m[3] or old[2]).strip() if m[3] or m[2] is None else old[2] if not m[3] else m[3].strip())
                if m[2] and not m[3]:
                    entries[i] = (day_of(m[2]), old[1], old[2])
                last_action = ('moved', entries[i], old)
                continue
        m = CANCEL.match(text)
        if m and '?' not in text:
            i = match([e for e in entries if not m[2] or e[0] == day_of(m[2])] if False else entries, m[1])
            if i is not None:
                last_action = ('cancelled', entries.pop(i))
                continue
        told = tell(text) if '?' not in text or re.search(r'(?<=[.!])\s', text) else {}
        if told:
            new = []
            for day, items in told.items():
                for what, time in items:
                    entries.append((day, what, time))
                    new.append(entries[-1])
            last_action = ('told', new)
    return entries, last_action


def minutes(time):
    """Sort key for '9', '6', 'noon', '11:30 am': bare small hours after noon are afternoon/evening only if 1-6."""
    t = time.lower().strip()
    if not t:
        return 24 * 60
    if t.startswith(('noon', 'midday')):
        return 12 * 60
    if t.startswith('midnight'):
        return 0
    m = re.match(r'(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?', t)
    if not m:
        return 24 * 60
    h, mi = int(m[1]), int(m[2] or 0)
    mer = (m[3] or '').replace('.', '')
    if mer == 'pm' and h < 12:
        h += 12
    elif mer == 'am' and h == 12:
        h = 0
    elif not mer and 1 <= h <= 6:
        h += 12                             # "the gym at 6", "a call at 4": afternoon unless said otherwise
    elif not mer and 'evening' in t and h < 12:
        h += 12
    return h * 60 + mi


def say(item, time):
    return f'{item} at {time}' if time else item


def day_line(entries, day):
    items = sorted([e for e in entries if e[0] == day], key=lambda e: minutes(e[2]))
    if not items:
        return f'**{day.capitalize()}**: nothing that you have told me about.'
    return f'**{day.capitalize()}**: ' + '; '.join(say(w, t) for _, w, t in items) + '.'


def out(text, kind):
    return dict(route='chat/plus-schedule', response=text, sources=[], reasoning=True,
                details=f'From the diary kept from this conversation ({kind}; schedule_agent.py).')


def respond(messages):
    turns = [m['content'] for m in messages if m.get('role') == 'user']
    if not turns:
        return None
    last = turns[-1].strip()
    entries, action = diary(turns)
    if action:
        kind = action[0]
        if kind == 'added':
            day, what, time = action[1]
            return out(f'Added: {say(what, time)} on {day.capitalize()}.\n\n{day_line(entries, day)}', 'added')
        if kind == 'moved':
            (day, what, time), old = action[1], action[2]
            return out(f'Done: {what} is now on {day.capitalize()}{" at " + time if time else ""} (it was on {old[0].capitalize()}'
                       f'{" at " + old[2] if old[2] else ""}).\n\n{day_line(entries, day)}', 'moved')
        if kind == 'cancelled':
            day, what, time = action[1]
            return out(f'Cancelled: {say(what, time)} on {day.capitalize()}.\n\n{day_line(entries, day)}', 'cancelled')
        if kind == 'told' and '?' not in last:
            days = list(dict.fromkeys(e[0] for e in action[1]))
            lines = '\n'.join('- ' + day_line(entries, d) for d in sorted(days, key=DAYS.index))
            return out(f"Got it, I've noted those:\n\n{lines}\n\nAsk me what's on any day, or tell me to add, move or cancel something.", 'noted')
    if not entries or '?' not in last and not re.match(r'(?i)\s*(?:what|anything|remind|tell)\b', last):
        return None
    m = ASK_DAY.search(last)
    if m and not re.search(r'(?i)\b(?:weather|forecast|open|closed|happen(?:ed|s)? in|date)\b', last):
        days = [day_of(d) for d in re.findall(DAY, m[1], flags=re.I)]
        days = [d for d in dict.fromkeys(days) if d]
        if days:
            if len(days) == 1:
                return out(day_line(entries, days[0]), 'asked for a day')
            return out('\n'.join('- ' + day_line(entries, d) for d in days), 'asked for days')
    m = ASK_WHEN.match(last)
    if m:
        i = match(entries, m[1])
        if i is not None:
            day, what, time = entries[i]
            return out(f'Your {what} is on **{day.capitalize()}{" at " + time if time else ""}**.', 'asked when')
    if re.search(r"(?i)\bwhat(?:'s| is| do i have)?\b.*\b(?:this week|my week|my schedule|my diary|my calendar|coming up|planned)\b", last):
        days = sorted(dict.fromkeys(e[0] for e in entries), key=DAYS.index)
        return out('\n'.join('- ' + day_line(entries, d) for d in days), 'asked for the week')
    return None
