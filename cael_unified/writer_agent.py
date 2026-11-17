"""The Writer: short messages that say something and ask something, their rewrites, and four-line rhymed poems.

"Can you write a short text to my landlord saying the kitchen tap is leaking and asking when someone can come to fix
it?" has two parts: something to tell and something to ask. The Writer takes both from the request in the user's own
words, turns the recipient's "her / him / them" into "you", and sets them out as a message with a greeting and a
close. "Make it more formal", "a bit friendlier", "shorter" write the same message again in that tone.

"Could you make it rhyme and keep it to four lines?" after a poem: four lines about the same subject from rhymed verse
patterns (AABB), which do rhyme and are four lines.

Other kinds of message (thanks, congratulations, apologies, invitations) stay with chat_plus.writer. No model.
"""
import re

FORM = r'(text|message|note|email|e-mail|letter|reply|whatsapp|sms|dm|memo)'
ASKED = re.compile(r"(?i)\b(?:write|draft|compose|put together|type up|help me (?:write|draft|word)|i need(?: to (?:write|send))?|can i get|give me)\b[^.?!]*?"
                   r"\b(?:a |an |me a |me an |up a )?(?:(?:short|quick|brief|polite|little|friendly|formal|nice|simple)\s+)*" + FORM + r"\b(.*)$", re.S)
TELL = r"(?:saying|telling (?:him|her|them)|to say|to tell (?:him|her|them)|letting (?:him|her|them) know|to let (?:him|her|them) know|explaining|" \
       r"informing (?:him|her|them)|mentioning|that says|which says|to explain)"
ASK = r"(?:asking(?: (?:him|her|them))?|to ask(?: (?:him|her|them))?|ask(?: (?:him|her|them))?|requesting|checking|to check|to find out|finding out|enquiring|inquiring)"
PERSON = r"(?:landlord|landlady|boss|manager|teacher|neighbou?r|colleague|coworker|co-worker|friend|flatmate|housemate|roommate|doctor|dentist|" \
         r"professor|tutor|coach|client|customer|supplier|plumber|builder|electrician|mum|mom|dad|mother|father|sister|brother|partner|wife|husband|" \
         r"son|daughter|team|class|group|agent|host|cleaner|babysitter|nanny|vet|accountant|lawyer|solicitor|bank|school|hr|recruiter|interviewer)"
TONE = re.compile(r"(?i)\b(?:make|can you make|could you make|rewrite|redo|write)\b.*?\b(?:it|that|this|the (?:message|text|note|email))?\b.*?"
                  r"\b(formal|professional|polite|friendl(?:y|ier)|casual|informal|relaxed|warm(?:er)?|short(?:er)?|brief(?:er)?|concise|chatty|nicer|kinder|softer|firmer|stronger|direct)\b")
TONES = dict(formal='formal', professional='formal', polite='formal', friendly='friendly', friendlier='friendly', casual='friendly', informal='friendly',
             relaxed='friendly', warm='friendly', warmer='friendly', chatty='friendly', nicer='friendly', kinder='friendly', softer='friendly',
             short='short', shorter='short', brief='short', briefer='short', concise='short', firmer='firm', stronger='firm', direct='firm')


def to_you(s):
    """The recipient in the third person becomes 'you': 'for her' -> 'for you', 'when she can' -> 'when you can'."""
    s = re.sub(r"(?i)\b(?:she|he|they)(?:'s| is| are)\b", "you're", s)
    s = re.sub(r"(?i)\b(?:she|he|they) (?:has|have)\b", "you have", s)
    s = re.sub(r"(?i)\b(?:she|he|they) (wants|needs|likes|knows|thinks|prefers)\b", lambda m: 'you ' + m[1][:-1], s)
    s = re.sub(r"(?i)\b(?:she|he|they)\b", "you", s)
    s = re.sub(r"(?i)\b(?:him|them)\b", "you", s)
    s = re.sub(r"(?i)\bher(?= (?:to|if|for|about|that|on|with|know|when|how|and|at|in|by|what|where|why)\b|\s*[.,!?]|\s*$)", "you", s)
    s = re.sub(r"(?i)\b(?:her|his|their)\b", "your", s)
    return s


def sentence(s):
    s = s.strip(' ,.;:!?')
    s = re.sub(r"\bi\b", 'I', s)
    s = re.sub(r"\bi'(m|ve|ll|d)\b", lambda m: "I'" + m[1], s)
    return s[:1].upper() + s[1:] if s else s


def parse(text):
    m = ASKED.search(text.strip())
    if not m:
        return None
    form = {'e-mail': 'email', 'whatsapp': 'message', 'sms': 'text', 'dm': 'message'}.get(m[1].lower(), m[1].lower())
    rest = m[2].strip().rstrip('?.! ')
    who = re.match(r"(?i)\s*(?:to|for) (?:my |our |the )?((?-i:[A-Z][a-z]+(?: [A-Z][a-z]+)?)|" + PERSON + r")(?:,? (?-i:([A-Z][a-z]+)))?\b", rest)
    name, role = '', ''
    if who:
        if re.fullmatch('(?i)' + PERSON, who[1]):
            role, name = who[1].lower(), who[2] or ''
        else:
            name = who[1]
        rest = rest[who.end():]
    tell = re.search(r"(?i)\b" + TELL + r"\s+(?:that\s+)?(.+?)(?=(?:,?\s+and\s+|,\s*|\s+)" + ASK + r"\b|$)", rest, re.S)
    ask = re.search(r"(?i)\b" + ASK + r"\s+(.+)$", rest, re.S)
    if tell and ask and ask.start() < tell.start():
        tell2 = re.search(r"(?i)\b" + TELL + r"\s+(?:that\s+)?(.+)$", rest, re.S)
        ask = re.search(r"(?i)\b" + ASK + r"\s+(.+?)(?=(?:,?\s+and\s+|,\s*|\s+)" + TELL + r"\b|$)", rest, re.S)
        tell = tell2
    if not tell and not ask:
        return None
    told = to_you(tell[1].strip()) if tell else ''
    told = re.sub(r"(?i)\s+and\s*$", '', told)
    asked = to_you(ask[1].strip()) if ask else ''
    if not told and not asked:
        return None
    return dict(form=form, name=name, role=role, tell=told, ask=asked, short=bool(re.search(r'(?i)\b(?:short|quick|brief)\b', text)))


def question(ask, tone):
    """The thing to ask as a sentence in the given tone."""
    a = ask.strip(' .?!')
    todo = re.match(r"(?i)(?:you )?to (.+)$", a)
    thing = re.match(r"(?i)for (.+)$", a)
    can_i = re.match(r"(?i)(?:if|whether) I (?:can|could|may|might) (.+)$", a)
    can_you = re.match(r"(?i)(?:if|whether) you (?:can|could|would|will|are able to) (.+)$", a)
    wants = re.match(r"(?i)(?:if|whether) you(?:'d| would)? (?:want|like|fancy|care) to (.+)$", a)
    if wants:
        return {'formal': f"I would be delighted if you could {wants[1]}.", 'firm': f"Please let me know if you will {wants[1]}."}.get(
            tone, f"Would you like to {wants[1]}?")
    if todo or can_you:
        act = (todo or can_you)[1]
        return {'formal': f"I would be grateful if you could {act}.", 'friendly': f"Would you be able to {act}?", 'firm': f"Please {act}.",
                'short': f"Could you {act}?"}.get(tone, f"Could you please {act}?")
    if can_i:
        act = can_i[1]
        return {'formal': f"I would be grateful if I could {act}.", 'friendly': f"Would it be okay if I {act}?", 'firm': f"I need to {act}; please confirm.",
                'short': f"Could I {act}?"}.get(tone, f"Would it be all right if I {act}?")
    if thing:
        return {'formal': f"I would like to request {thing[1]}.", 'friendly': f"Any chance of {thing[1]}?", 'firm': f"I need {thing[1]}.",
                'short': f"Could I have {thing[1]}?"}.get(tone, f"Could I ask for {thing[1]}?")
    clause = re.sub(r"(?i)^(?:about )", '', a)
    if not re.match(r"(?i)(?:if|whether|when|what|where|who|why|how|which)\b", clause):
        clause = 'about ' + clause
    return {'formal': f"I would be grateful if you could let me know {clause}.", 'friendly': f"Could you let me know {clause}?",
            'firm': f"Please let me know {clause}.", 'short': f"Can you tell me {clause}?"}.get(tone, f"Could you let me know {clause}?")


def compose(req, tone='neutral'):
    who = req['name']
    hello = {'formal': f"Dear {who or '[Name]'},", 'friendly': f"Hi {who}!" if who else "Hi there!", 'short': f"Hi {who}," if who else "Hi,",
             'firm': f"Hello {who}," if who else "Hello,"}.get(tone, f"Hi {who}," if who else "Hi,")
    lines = []
    if req['tell']:
        t = sentence(req['tell'])
        lower = t[:1].lower() + t[1:] if not re.match(r"I\b|I'", t) and not re.match(r'[A-Z][a-z]+ [A-Z]', t) else t
        lines.append({'formal': f"I am writing to let you know that {lower}.", 'friendly': f"Just to let you know, {lower}.",
                      'firm': f"{t}."}.get(tone, f"{t}."))
    if req['ask']:
        lines.append(question(req['ask'], tone))
    close = {'formal': "Thank you for your time.\n\nKind regards,\n[Your name]", 'friendly': "Thanks so much!\n[Your name]", 'short': "Thanks,\n[Your name]",
             'firm': "Thank you,\n[Your name]"}.get(tone, "Thanks,\n[Your name]")
    body = ' '.join(lines)
    return f"{hello}\n\n{body}\n\n{close}"


def out(text, kind):
    return dict(route='chat/plus-writing', response=text, sources=[], details=f'Written by the Writer from the request ({kind}; writer_agent.py).')


VERSES = [
    ("O {s}, steady, calm and bright,", "you keep your watch through day and night;", "when all the world has gone to sleep,", "you hold the quiet that I keep."),
    ("The {s} waits, and so do I,", "beneath a wide and patient sky;", "it asks for nothing, speaks no word,", "and still it is the best I've heard."),
    ("I stopped beside the {s} today,", "and felt my worries drift away;", "I breathed, I looked, I looked once more,", "and left much lighter than before."),
    ("The {s} keeps its gentle ground,", "with hardly any stir or sound;", "I carry it, a little light,", "to warm me through the longest night."),
]
POEM = re.compile(r"(?i)\b(?:poem|verse|rhyme|haiku|limerick)\b[^.?!]*?\b(?:about|on|for)\s+(?:the |a |an |my |our )?(.+?)\s*[.?!]?\s*$")


def poem_first(messages):
    """'Can you write me a short poem about the sea at night?': four rhymed lines (AABB) about it."""
    last = [m['content'] for m in messages if m.get('role') == 'user'][-1]
    m = re.search(r"(?i)\b(?:write|give|make|compose|do)\b[^.?!]{0,20}?\b(?:a |an )?(?:short |little |quick |simple |rhyming |cute |nice )*(?:poem|rhyme|verse)\b"
                  r"\s+(?:about|on|for|of)\s+(?:the |a |an |my |our )?(.+?)\s*(?:please)?[.?!]?\s*$", last)
    if not m or len(m[1].split()) > 8:
        return None
    subject = re.sub(r'(?i)\s+(?:please|for me)$', '', m[1].strip())
    pick = VERSES[sum(map(ord, subject)) % len(VERSES)]
    title = ' '.join(w.capitalize() if len(w) > 3 or i == 0 else w for i, w in enumerate(subject.split()))
    return dict(route='chat/plus-writing', sources=[], details='Rhymed verse patterns, AABB (writer_agent.py).',
                response=f"*{title}*\n\n" + '\n'.join(line.format(s=subject) for line in pick))


def poem_again(messages):
    users = [m['content'] for m in messages if m.get('role') == 'user']
    last = users[-1]
    if not re.search(r"(?i)\brhym|\b(?:four|4|two|2|three|3)[- ]lines?\b|\bquatrain\b|\bshorter\b", last) or len(last.split()) > 30:
        return None
    subject = None
    for t in reversed(users[:-1][-3:]):
        m = POEM.search(t)
        if m:
            subject = m[1].strip()
            break
    mine = POEM.search(last)
    if mine and not subject:
        subject = mine[1].strip()
    if not subject or len(subject.split()) > 8:
        return None
    subject = re.sub(r'(?i)\s+(?:please|for me|if you can)$', '', subject)
    pick = VERSES[sum(map(ord, subject)) % len(VERSES)]
    lines = [line.format(s=subject) for line in pick]
    title = ' '.join(w.capitalize() if len(w) > 3 or i == 0 else w for i, w in enumerate(subject.split()))
    if re.search(r"(?i)\b(?:two|2)[- ]lines?\b|\bcouplet\b", last):
        two = [lines[0], lines[1].rstrip(';,') + '.']
        return dict(route='chat/plus-writing', sources=[], details='Two rhymed lines (writer_agent.py).',
                    response=f"Here it is in two rhyming lines:\n\n*{title}*\n\n" + '\n'.join(two))
    return dict(route='chat/plus-writing', sources=[], details='Four lines from rhymed verse patterns, AABB (writer_agent.py).',
                response=f"Here it is in four rhyming lines:\n\n*{title}*\n\n" + '\n'.join(lines) + "\n\n(Rhyme scheme AABB: the first two lines rhyme, and the last two.)")


THANKS = re.compile(r"(?i)\b(?:write|draft|compose|put together|help me (?:write|word)|need)\b[^.?!]{0,30}?\b(?:a |an )?(?:(?:short|quick|brief|little|nice|lovely|simple|heartfelt)\s+)*"
                    r"thank[- ]?you (note|card|message|email|e-mail|letter|text)\s+(?:to|for) (?:my |our |the )?(.+?)\s+for\s+(.+?)\s*[.?!]?\s*$")


THANKING = re.compile(r"(?i)\b(?:write|draft|compose|put together|help me (?:write|word)|need)\b[^.?!]{0,30}?\b(?:a |an )?"
                      r"(?:(?:short|quick|brief|little|nice|lovely|simple|heartfelt|friendly|warm|kind),?\s+)*"
                      r"(note|card|message|email|e-mail|letter|text)\s+(?:to|for) (?:my |our |the )?(.+?)\s+thanking (?:her|him|them)\s+for\s+(.+?)\s*[.?!]?\s*$")


def thank_parse(text):
    m = THANKS.search(text.strip()) or THANKING.search(text.strip())
    if not m:
        return None
    form = {'e-mail': 'email'}.get(m[1].lower(), m[1].lower())
    who = m[2].strip()
    owner = re.match(r"(?i)(?:my |our )?([a-z]+)'s ([a-z]+)$", who)          # "daughter's teacher"
    for_what = m[3].strip()
    if owner:
        child = owner[1].lower()
        # "helping her settle in at her new school": the first "her" is the child, named as such
        for_what = re.sub(r"(?i)\b(her|him|them)\b", f'our {child}', for_what, count=1)
        for_what = re.sub(r"(?i)\b(?:she|he|they)\b", f'our {child}', for_what, count=1)
        role = owner[2].lower()
    else:
        role = re.sub(r"(?i)^(?:my|our|the)\s+", '', who).lower()
        for_what = to_you(for_what)
    for_what = re.sub(r"(?i)\bmy\b", 'my', for_what)
    return dict(form=form, role=role, why=for_what.rstrip('.'), child=owner[1].lower() if owner else None)


def thank_note(req, tone='neutral'):
    role, why = req['role'], req['why']
    name = f"[{role.capitalize()}'s name]"
    child = req['child']
    pron = {'daughter': 'she', 'son': 'he'}.get(child, 'they')
    verb = 'comes' if pron != 'they' else 'come'
    if tone == 'friendly':
        body = (f"I just wanted to say a huge thank you for {why}. You've made such a difference: {pron} {verb} home happy and talking about "
                f"{'school' if 'school' in why else 'it'}, and that means the world to us.\n\nThank you for your patience, your kindness and everything you do."
                if child else f"I just wanted to say a huge thank you for {why}. It made a real difference, and I'm so grateful for your kindness and patience.")
        close = "With love and gratitude,\n[Your name]"
    elif tone == 'formal':
        body = f"I am writing to thank you sincerely for {why}. Your care and attention have been greatly appreciated."
        close = "With kind regards,\n[Your name]"
    elif tone == 'short':
        body = f"Thank you so much for {why}. It meant a lot."
        close = "Best wishes,\n[Your name]"
    else:
        body = (f"Thank you so much for {why}. Starting somewhere new is a big step, and your patience and kindness have made it so much easier. "
                f"It really means a lot to us." if child else f"Thank you so much for {why}. It really meant a lot, and I appreciate the time and care you put in.")
        close = "Warm wishes,\n[Your name]"
    return f"Dear {name},\n\n{body}\n\n{close}"


REFERENCE = re.compile(r"(?i)\b(?:write|draft|compose|put together|help me (?:write|word)|need)\b[^.?!]{0,30}?\b(?:a |an )?(?:(?:short|quick|brief|good|glowing|character|personal)\s+)*"
                       r"(?:reference|recommendation)(?: letter)?\s+for\s+(?:my |our |the )?([a-z]+)(?:,?\s+(?-i:([A-Z][a-z]+)),?)?(.*)$")


def reference_parse(text):
    m = REFERENCE.search(text.strip())
    if not m:
        return None
    role, name, rest = m[1].lower(), m[2] or '', (m[3] or '').strip(' .?!')
    did = re.search(r"(?i)\b(?:who|that)\s+(?:has\s+|had\s+|have\s+)?(.+?)(?:\s+for\s+((?:about |nearly |over |almost )?(?:\w+ ){0,2}(?:years?|months?|weeks?)))?\s*$", rest)
    work = did[1].strip() if did else ''
    span = did[2] if did and did[2] else ''
    work = re.sub(r"(?i)^(?:has |have |had )", '', work)
    work = re.sub(r"(?i)\bour\b", 'our', work)
    return dict(role=role, name=name, work=work, span=span)


def reference_note(req, tone='neutral'):
    who = req['name'] or f'our {req["role"]}'
    Who = who[:1].upper() + who[1:]
    work = req['work'] or f'worked with us as our {req["role"]}'
    span = f" for {req['span']}" if req['span'] else ''
    role = req['role']
    if tone == 'formal':
        return (f"To whom it may concern,\n\nI am pleased to provide a reference for {who}, who has {work}{span}. Throughout this time {who} has been "
                f"reliable, punctual and trustworthy, and has shown consistent care, patience and good judgement.\n\n{Who} is responsible and calm, "
                f"communicates clearly, and follows our routines and instructions carefully. We have complete confidence in {who}'s abilities and "
                f"would recommend {who} without reservation for any {role} position.\n\nPlease do not hesitate to contact me should you require "
                f"any further information.\n\nYours faithfully,\n[Your name]\n[Phone number]")
    return (f"To whom it may concern,\n\nI'm happy to recommend {who}, who has {work}{span}. {Who} has always been reliable, punctual and "
            f"trustworthy, and our children look forward to every visit. {Who} is patient, kind and sensible, keeps to our routines, and we have "
            f"always felt completely at ease leaving them in {who}'s care.\n\nI would recommend {who} without hesitation. Please feel free to "
            f"contact me if you have any questions.\n\nKind regards,\n[Your name]\n[Phone number]") if role in ('babysitter', 'nanny', 'childminder', 'au') else \
        (f"To whom it may concern,\n\nI'm happy to recommend {who}, who has {work}{span}. {Who} has always been reliable, punctual and "
         f"trustworthy, and does excellent work with real care.\n\nI would recommend {who} without hesitation. Please feel free to contact me "
         f"if you have any questions.\n\nKind regards,\n[Your name]\n[Phone number]")


def respond(messages):
    users = [m['content'] for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1].strip()
    again = poem_again(messages) or poem_first(messages)
    if again:
        return again
    ref = reference_parse(last)
    if ref:
        return out(f"Here's a short reference you could use:\n\n{reference_note(ref)}\n\nI can make it more formal, warmer or shorter, or add "
                   f"specific examples if you tell me a few.", 'reference')
    tone_ref = TONE.search(last)
    if tone_ref and len(last.split()) <= 16:
        for t in reversed(users[:-1][-4:]):
            req = reference_parse(t)
            if req:
                mode = TONES[tone_ref[1].lower()]
                return out(f"Here's a more formal version:\n\n{reference_note(req, 'formal')}" if mode in ('formal', 'firm') else
                           f"Here's another version:\n\n{reference_note(req)}", 'reference rewrite')
    thanks = thank_parse(last)
    if thanks:
        return out(f"Here's a short {thanks['form']} you could send:\n\n{thank_note(thanks)}\n\nI can make it warmer, more formal or shorter if you like.", 'thank-you')
    tone = TONE.search(last)
    if tone and len(last.split()) <= 16:
        for t in reversed(users[:-1][-4:]):
            req = thank_parse(t)
            if req:
                mode = TONES[tone[1].lower()]
                lead = {'formal': "Here's a more formal version:", 'friendly': "Here's a warmer version:" if 'warm' in tone[1].lower() else "Here's a friendlier version:",
                        'short': "Here's a shorter version:", 'firm': "Here's a more direct version:"}[mode]
                return out(f"{lead}\n\n{thank_note(req, mode if mode != 'firm' else 'formal')}", 'thank-you rewrite')
            if parse(t):
                break
    req = parse(last)
    if req:
        text = compose(req, 'short' if req['short'] and False else 'neutral')
        kind = req['form']
        return out(f"Here's {'an' if kind[0] in 'aeiou' else 'a'} {kind} you could send:\n\n{text}\n\nI can make it more formal, friendlier or shorter if you like.", 'message')
    tone = TONE.search(last)
    if tone and len(last.split()) <= 16:
        for t in reversed(users[:-1][-4:]):
            req = parse(t)
            if req:
                mode = TONES[tone[1].lower()]
                if re.search(r'(?i)\bless (?:formal|serious|professional|stiff)\b|\btoo (?:formal|serious|stiff|stuffy)\b', last):
                    mode = 'friendly'
                if re.search(r'(?i)\bless (?:casual|informal|chatty|friendly)\b|\btoo (?:casual|informal|chatty|friendly)\b', last):
                    mode = 'formal'
                lead = {'formal': "Here's a more formal version:", 'friendly': "Here's a friendlier version:", 'short': "Here's a shorter version:",
                        'firm': "Here's a firmer version:"}[mode]
                return out(f"{lead}\n\n{compose(req, mode)}", 'rewrite')
    return None
