"""Everyday conversation: natural replies to what people tell CAEL about their day, and to questions about CAEL itself.

Not a list of topics: each frame is a kind of situation (an achievement, a setback, being tired, nervous, bored,
sick, starting something, a trip, mixed feelings, thanks...) recognised from the wording, and the reply is built
from the person's own words (turned into "you" form) plus a frame-appropriate reaction and one follow-up question.
Non-neural: regular expressions, word lists and templates. A frame never invents facts about the person.
"""
import random
import re

from .chat_core import out, user_turns, you


def _clean(phrase):
    phrase = re.sub(r"\s+", ' ', phrase or '').strip(' .,!?;:')
    phrase = re.sub(r"(?i)\s+(?:today|yesterday|tonight|this (?:morning|week|weekend)|last (?:night|week)|again|finally)$", '', phrase)
    return phrase


def _y(phrase):
    return _clean(you(phrase))


def _pick(options, key):
    return options[sum(map(ord, key)) % len(options)]


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


FUN_QUESTIONS = [
    'If you could instantly master any skill, what would you pick?',
    'What is the best thing you have eaten in the last month?',
    'If your commute had a theme song today, what would it be?',
    'Which place have you never been to but would go to tomorrow if you could?',
    'What is a small thing that always makes your day better?',
    'If you could have dinner with any person, past or present, who would it be?',
]

CHEAP_IDEAS = ['a long walk somewhere you have not explored yet', 'a free museum or gallery', 'cooking something new from what is in the cupboard',
               'a film or board-game night with a friend', 'the library (books, films and often free events)', 'a picnic or a bike ride if the weather allows']

MOVIES = ['"Paddington 2" (warm and funny)', '"The Grand Budapest Hotel" (quirky and colourful)', '"Spirited Away" (beautiful animation)',
          '"Knives Out" (a fun mystery)', '"Little Miss Sunshine" (comforting road-trip comedy)']


def frames(last, low, prev_low, turns):
    """Yield (route, reply) for the first frame that fits the last turn."""
    # thanks / just needed to vent
    if re.search(r"\b(?:thanks?|thank you)\b", low) and re.search(r"\b(?:needed to|just wanted to|say it|get it off|talk|listening|vent)\b", low):
        return 'thanks-vent', ("Of course. Saying it out loud can really take some of the weight off. "
                               "I'm glad you shared it, and I'm here whenever you want to talk about it more.")
    if re.fullmatch(r"\s*(?:ok(?:ay)?|cool|great|nice|thanks?|thank you|cheers|perfect|awesome)(?:[,!. ]+(?:thanks?|thank you|that helps|so much))*[.! ]*", low):
        return 'thanks', _pick(["You're welcome! Is there anything else I can help with?", "Happy to help. Let me know if anything else comes up!"], low)

    # questions about CAEL itself
    if re.search(r"\bwhat do you (?:like|enjoy|love) (?:to do|doing)\b|\bwhat are your hobbies\b|\bdo you have (?:any )?hobbies\b", low):
        return 'about-me', ("I don't have free time the way you do, but if I had to choose, I'd say I enjoy conversations like this one: "
                            "hearing about people's plans, helping untangle a problem, or swapping book and film ideas. What do you like to do for fun?")
    m = re.search(r"\bdo you have a favou?rite (\w+(?: \w+)?)", low)
    if m:
        thing = m[1]
        pick = {'book': '"The Hobbit": a cosy adventure that still holds up', 'film': '"Spirited Away"', 'movie': '"Spirited Away"',
                'food': 'a good homemade pizza', 'colour': 'deep blue', 'color': 'deep blue', 'song': '"Here Comes the Sun"',
                'animal': 'the octopus, because it is so clever', 'season': 'autumn'}.get(thing.split()[0])
        if pick:
            return 'about-me', f"I don't have personal favourites the way people do, but if I had to pick a {thing}, I'd say {pick}. What's yours?"
        return 'about-me', f"I don't really have a favourite {thing}, but I'd love to hear yours. What is it, and what do you like about it?"
    if re.search(r"\b(?:fun|interesting|random|good) question\b.*\b(?:ask|pass the time)\b|\bask me (?:a|something) (?:fun|interesting|random)\b", low):
        qs = FUN_QUESTIONS[:]
        random.Random(low).shuffle(qs)
        return 'fun-question', f"Here's one to pass the time: {qs[0]} And if you'd like a backup: {qs[1]}"
    m = re.search(r"\bdo you think (?:it|this|that|things?|i|you) (?:gets?|will get|become?s?|will become) (easier|better|less \w+)\b", low)
    if m or re.search(r"\b(?:get|gets|getting) (?:easier|better) with (?:practice|time)\b", low):
        topic = next((t for t in reversed(turns[:-1]) if t), '')
        mt = re.search(r"\b(?:started|began|took up|joined|learning|taking|doing|trying) (?:a |an |my |the )?([\w \-]+?)(?: class| lessons?| course)?\b(?: and|[.,!]|$)", topic, re.I)
        thing = mt[1].strip() if mt else 'it'
        return 'encourage', (f"Yes, it really does. {_cap(thing) if thing != 'it' else 'It'} is a skill, and almost everyone's first attempts are wobbly. "
                             "The improvement usually comes quickly once your hands and eyes get used to it: most people notice a real difference "
                             "after a handful of sessions. Keep that first attempt; it'll be fun to compare later.")

    # setbacks
    m = re.search(r"\bi (?:just )?(?:failed|didn't pass|did not pass|bombed|flunked) (?:my |the |an? )?([^.,!?]+)", low)
    if m:
        thing = _clean(m[1])
        return 'setback', (f"Oh no, I'm sorry. Failing your {thing} is really disappointing, especially after building up to it. "
                           "It happens to a lot of people the first time, and it says nothing about how you'll do next time. "
                           "Do you know what tripped you up, or when you can try again?")
    m = re.search(r"\bi (?:didn't|did not|don't) get (?:the |that |my )?([^.,!?]+)", low)
    if m and re.search(r"\b(?:job|offer|place|promotion|role|part|scholarship|apartment|flat|house)\b", m[1]):
        return 'setback', (f"I'm sorry, that's a real letdown. Not getting the {_clean(m[1])} stings, especially when you'd started picturing it. "
                           "How are you feeling about it?")
    if re.search(r"\b(?:i was so nervous|i panicked|i froze|my mind went blank|i forgot)\b", low) and re.search(r"\b(?:fail|test|exam|interview|speech|lost)\b", prev_low):
        return 'setback-detail', ("That makes complete sense: nerves can make anyone forget something they know perfectly well. "
                                  "The good news is that it was a nerves problem, not a skills problem, and nerves get easier the second time "
                                  "because you know exactly what to expect. A couple of practice runs focused on that one habit would help a lot.")

    # achievements
    m = re.search(r"\bi (?:just |finally |actually )?(?:finished|completed|passed|ran|won|got|graduated(?: from)?|made it (?:to|through)|nailed) "
                  r"(?:my |the |a |an )?((?:first )?[^.,!?]+)", low)
    if m and re.search(r"\b(?:marathon|race|exam|test|degree|course|project|thesis|job|offer|promotion|interview|half|5k|10k|book|competition|licen[cs]e|first)\b", m[1]) \
            and not re.search(r"\b(?:fail|didn't|not)\b", low):
        thing = _clean(m[1])
        return 'achievement', (f"Congratulations! Your {thing} is a big deal, and all that effort clearly paid off. "
                               "How are you feeling now, and are you doing anything to celebrate?")
    if re.search(r"\b(?:legs|muscles|body|feet|back) (?:are|is|feel|feels) (?:so |really |very )?(?:sore|stiff|tired|aching|dead)\b", low):
        return 'sore', ("That's well earned! For the next few days: keep moving gently (an easy walk helps more than staying still), drink plenty, "
                        "eat a proper meal with some protein, and sleep as much as you can. A warm bath can feel great too. "
                        "The soreness usually peaks after a day or two and then fades.")

    # nervous about something ahead
    m = re.search(r"\b(?:have|got) (?:a |an |my )?([^.,!?]*?(?:interview|exam|test|presentation|speech|date|appointment|meeting|audition|match|game|surgery|operation))"
                  r"(?: [^.,!?]*)?[.,!]?.*\b(?:nervous|anxious|scared|worried|terrified|stressed)\b", low)
    if m:
        thing = _clean(m[1])
        return 'nervous', (f"Feeling nervous before your {thing} is completely normal; it usually means you care about it. "
                           "A few things that help: prepare the two or three points you most want to get across, get things ready the night before, "
                           "and remember to breathe slowly when you start. What part are you most worried about?")
    m = re.search(r"\b(?:have to|need to|got to|asked to) (?:give|make|write|do) (?:a |the )?(speech|toast|presentation|talk)\b", low)
    if m:
        return 'big-task', (f"What an honour, and a bit of pressure too! A good {m[1]} doesn't need to be long: a warm opening, one or two personal stories, "
                            "and a toast or kind wish to finish. Would you like help with the opening line?")

    if re.search(r"\b(?:speech|toast)\b", prev_low) and re.search(r"\bhow (?:do|should|can) i (?:start|begin|open)\b|\b(?:opening|first) line\b", low):
        who = re.search(r"\bmy (sister|brother|friend|best friend|cousin|son|daughter|mum|mom|dad|colleague)\b", prev_low)
        w = who[1] if who else 'the couple'
        rel = {'sister': 'sibling', 'brother': 'sibling', 'friend': 'friend', 'best friend': 'best friend', 'cousin': 'cousin'}.get(w, 'friend')
        return 'speech-opening', ("A warm, simple opening works best. A few you could adapt:\n\n"
                                  f"- \"Good evening, everyone. For those who don't know me, I'm [your name], and I'm [name]'s proud {rel}. I've been looking forward to this all week.\"\n"
                                  "- \"I've known [name] for [number] years, and I've never seen them happier than today.\"\n"
                                  "- Start with a short, kind story: \"The first time I met [partner's name]...\"\n\n"
                                  "Then share one or two memories, say something kind about them as a couple, and finish by raising a glass. "
                                  "Would you like help with the story part?")

    # tired / long day / busy
    if re.search(r"\b(?:long|tough|hard|rough|exhausting|busy|crazy|stressful) (?:day|week|shift)\b|\b(?:so|really|very) (?:tired|exhausted|drained)\b|\bi'?m exhausted\b", low):
        return 'tired', ("That sounds draining. Days like that can leave you wiped out even when nothing dramatic happened. "
                         "Do you get some time to switch off this evening?")
    if re.search(r"\bmostly meetings\b|\bnothing got done\b|\bdidn't get anything done\b", low):
        return 'tired-detail', ("Meeting-heavy days are the worst for that: you're busy all day and still feel behind. "
                                "If it keeps happening, blocking an hour in your calendar for focused work can really help. For tonight, though, I hope you can rest.")
    if re.search(r"\b(?:train|bus|tube|subway|metro|traffic|commute)\b", low) and re.search(r"\b(?:packed|crowded|full|late|delayed|stuck|slow|cancell?ed)\b", low):
        greet = 'Morning! ' if re.search(r"\bmorning\b", low) else ''
        return 'commute', (f"{greet}Packed trains are no fun, especially first thing. I hope you at least managed to grab a seat or a spot by the window. "
                           "Is your commute usually this busy, or is today unusual?")

    # bored
    if re.search(r"\b(?:so |really |kind of )?bored\b", low):
        ideas = CHEAP_IDEAS[:]
        random.Random(low).shuffle(ideas)
        return 'bored', ("Let's fix that! A few ideas: " + ', '.join(ideas[:3]) + ". Do you feel like getting out of the house, or staying in?")
    if re.search(r"\b(?:cheap|free|low[- ]cost|on a budget)\b", low) and re.search(r"\bbored\b", prev_low):
        return 'bored-detail', ("Cheap is easy: " + '; '.join(CHEAP_IDEAS[:4]) + ". Many cities also list free events for the weekend online. Anything there sound good?")

    # sad / down / lonely / mixed feelings
    if re.search(r"\b(?:happy|glad|excited|proud)\b.*\bbut\b.*\b(?:sad|upset|worried|nervous|scared|miss)\b|\b(?:sad|bittersweet)\b.*\bbut\b.*\b(?:happy|glad|excited)\b", low):
        m = re.search(r"\bmy ([\w ]+?) is (?:moving|leaving|going|getting|starting)\b([^.,!?]*)", low)
        who = f"your {m[1]}" if m else 'them'
        return 'mixed', (f"That makes so much sense. You can be genuinely happy for {who} and still feel sad about what changes for you; both feelings are real. "
                         "It sounds like you're a really good friend. Have you talked about how you'll stay in touch?")
    if re.search(r"\b(?:feel|feeling|i'?m) (?:kind of |a bit |so |really |pretty )?(?:down|sad|low|blue|lonely|miserable|upset|meh)\b", low):
        cause = ''
        if re.search(r"\brain", low):
            cause = 'Grey, rainy days really can drag your mood down. '
        return 'down', (f"I'm sorry you're feeling down. {cause}Sometimes a slow, cosy day is exactly what's needed: something warm to drink, "
                        "a favourite film or a short walk if it clears up. Is it mostly the weather, or is something else on your mind?")
    if re.search(r"\b(?:watch a (?:movie|film)|movie night|film night)\b", low) and re.search(r"\b(?:suggest|recommend|ideas|any)\b", low):
        films = MOVIES[:]
        random.Random(low).shuffle(films)
        return 'films', ("Good plan for a rainy day! A few cosy picks: " + ', '.join(films[:3]) + ". Are you in the mood for something funny, or something to get lost in?")

    # sick
    m = re.search(r"\bi (?:have|got|'ve got|caught) (?:a |the )?(cold|flu|headache|migraine|fever|sore throat|cough|stomach bug)\b|\bi'?m (?:feeling )?(?:sick|ill|unwell)\b", low)
    if m:
        what = m[1] if m and m.lastindex else 'feeling unwell'
        return 'sick', (f"Sorry to hear that, being ill is miserable. Rest, plenty of fluids and something warm usually help; and if it gets worse "
                        "or doesn't improve in a few days, it's worth checking with a doctor. Are you able to take it easy today?")

    # new things: adopted, bought, started, moved
    m = re.search(r"\bi (?:just |finally )?adopted (?:a |an |two )?([^.,!?]+)", low)
    if m:
        pet = _clean(m[1])
        return 'new-pet', (f"Congratulations, a new {pet}! That's so exciting. What's their name, and how are they settling in?")
    m = re.search(r"\bi (?:just |finally )?(?:bought|got) (?:a |an |my first |a new )([^.,!?]+)", low)
    if m and not re.search(r"\b(?:cold|flu|headache|job|offer)\b", m[1]):
        return 'new-thing', f"Nice, a new {_clean(m[1])}! What made you go for it, and are you happy with it so far?"
    m = re.search(r"\b[Ii](?:'m| am) (?:going|heading|travell?ing|flying|off) to ([A-Z][\w]+(?: [A-Z][\w]+)*)(?: for| in| next| this| on|[.!,]|$)", last)
    if m:
        place = m[1].strip()
        first = ' for the first time' if re.search(r"first time", low) else ''
        when = ' Spring is a lovely time to go.' if re.search(r"\bspring\b", low) else (' Summer should be fun.' if re.search(r"\bsummer\b", low) else '')
        return 'trip', (f"How exciting, {place}{first}!{when} Have you planned your route yet, or are you still deciding what to see? "
                        "I'm happy to help you put a list together.")
    m = re.search(r"\bi (?:just )?(?:started|began|took up|joined|signed up for) (?:a |an |my |the )?([\w \-]+?)(?: class| course| lessons?| club)?\b(.*)", low)
    if m and not re.search(r"\b(?:to|feeling|crying)\b", m[1]):
        thing = _clean(m[1])
        rest = m[2]
        if re.search(r"\b(?:wonky|bad|terrible|awful|failed|wrong|lopsided|ugly|mess)\b", rest):
            return 'new-hobby-wobbly', (f"Welcome to {thing}! Honestly, a wonky first attempt is practically a tradition, and it means you actually made something. "
                                        "Keep it: it'll be fun to look back on once you've improved. What did you enjoy most about the class?")
        return 'new-hobby', f"That's great, {thing} is a lovely thing to start. How are you finding it so far, and what made you want to try it?"
    m = re.search(r"\bmy ([\w ]+?) is (?:getting married|having a baby|moving|retiring|graduating)\b", low)
    if m:
        return 'family-news', f"How lovely, congratulations to your {m[1]}! How are you feeling about it?"

    # greetings
    if re.fullmatch(r"\s*(?:hi|hello|hey|hiya|good (?:morning|afternoon|evening)|morning|evening)(?: there)?[!. ]*(?:how are you(?: doing)?\??)?\s*", low):
        return 'greeting', "Hi! I'm doing well, thanks for asking. How's your day going?"
    if re.search(r"^\s*how are you\b|\bhow'?s (?:it going|your day)\b", low):
        return 'how-are-you', "I'm doing well, thank you! How about you, how's your day been?"
    return None


def reply(messages):
    turns = user_turns(messages)
    if not turns:
        return None
    last = turns[-1].strip()
    if len(last) > 400 or re.search(r"\d+\s*(?:\+|-|\*|/|x)\s*\d+|```", last):
        return None
    low = last.lower().replace("’", "'")
    prev_low = turns[-2].lower() if len(turns) > 1 else ''
    found = message_reply(messages)
    if found:
        return found
    hit = frames(last, low, prev_low, turns)
    if not hit:
        return None
    route, text = hit
    return out('talk-' + route, text, 'Everyday conversation frame (everyday_talk.py): situation recognised from wording; non-neural templates.')


# ------------------------------------------------------------------ short messages, notes and emails to someone
MSG = re.compile(r"(?i)\b(?:write|draft|compose|help me (?:write|with))\b(?: me)?(?: (?:a|an|the))?((?: \w+,?){0,3}?) (message|note|text|email|e-mail|letter|card)"
                 r"(?: (?:to|for) (?:my |our |the |a )?([\w' ]+?))?(?:,? (asking|to ask|telling|to tell|letting|to let|inviting|to invite|thanking|to thank|"
                 r"saying|apologi[sz]ing|to apologi[sz]e|reminding|to remind|wishing|to wish|about|that)\b ?(.*))?$")


def _person(who):
    who = (who or '').strip()
    if not who:
        return '[Name]'
    parts = who.split()
    if parts[-1][:1].isupper():
        return parts[-1]                       # "my colleague Sam" -> Sam
    return f"[{_cap(who)}'s name]"


def _clause(text):
    t = _clean(text)
    t = re.sub(r"(?i)[.;]?\s*(?:please )?(?:use|with|include|add|leave) (?:some )?placeholders?\b.*$", '', t)
    t = re.sub(r"(?i)^(?:if|whether) (?:they|he|she|you) (?:could|can|would|might|will)(?: be able to)? ", '', t)
    t = re.sub(r"(?i)^(?:them|him|her|you) (?:if (?:they|he|she) could |whether (?:they|he|she) could |to )?", '', t)
    t = re.sub(r"(?i)\b(?:they|he|she)\b", 'you', t)
    t = re.sub(r"(?i)\b(?:their|his|her)\b", 'your', t)
    t = re.sub(r"(?i)\b(?:them|him)\b", 'you', t)
    return _clean(t)


def compose_message(purpose, clause, who, style, placeholders):
    name = _person(who)
    away = bool(re.search(r"(?i)\b(?:while|when) i(?:'m| am) (?:away|gone|on holiday|on vacation)\b", clause))
    core = _clean(re.sub(r"(?i)\s*\b(?:while|when) i(?:'m| am) (?:away|gone|on holiday|on vacation)\b", '', clause))
    dates = ' from [start date] to [end date]' if (placeholders or away) else ''
    polite = style == 'polite'
    hello = f"Dear {name}," if polite else f"Hi {name},"
    if purpose in ('asking', 'to ask', ''):
        if polite:
            body = (f"I hope this message finds you well. I will be away{dates}, and I wondered whether you might possibly be able to {core} while I am away."
                    if away else f"I hope this message finds you well. I wondered whether you might possibly be able to {core}{dates}.")
            body += ("\n\nI completely understand if it isn't convenient, so please don't hesitate to say no. "
                     "I would be very grateful, and I'd be happy to return the favour at any time.")
            return f"{hello}\n\n{body}\n\nWith many thanks,\n[Your name]"
        body = (f"I hope you're doing well! I'm going to be away{dates}, and I was wondering if you'd be able to {core} while I'm gone?"
                if away else f"I hope you're doing well! I was wondering if you'd be able to {core}{dates}?")
        body += " I'm happy to leave everything you need, and of course I'd be glad to return the favour. Just let me know if that works for you."
        return f"{hello}\n\n{body}\n\nThanks so much,\n[Your name]"
    if purpose.endswith('thank') or purpose == 'thanking':
        lead = 'I wanted to say a heartfelt thank you' if polite else 'Just wanted to say a huge thank you'
        core = re.sub(r"(?i)^(?:you )?(?:for )?", '', core)
        return f"{hello}\n\n{lead} for {core}. It really meant a lot to me.\n\n{'With warm regards' if polite else 'Thanks again'},\n[Your name]"
    if 'invit' in purpose:
        core = re.sub(r"(?i)^(?:you )?(?:to )?", '', core)
        return (f"{hello}\n\nI'd love to invite you to {core} on [date] at [time]. It would be {'a real pleasure' if polite else 'great'} to have you there. "
                f"Could you let me know by [RSVP date] whether you can make it?\n\n{'Kind regards' if polite else 'Hope to see you there'},\n[Your name]")
    if 'apolog' in purpose:
        core = re.sub(r"(?i)^(?:for )?", '', core)
        return (f"{hello}\n\nI'm really sorry for {core}. I didn't mean to cause any trouble, and I'd like to make it right. "
                f"Please let me know if there's anything I can do.\n\n{'Sincerely' if polite else 'Sorry again'},\n[Your name]")
    if 'remind' in purpose:
        core = re.sub(r"(?i)^(?:you )?", '', core)
        joiner = '' if re.match(r"(?i)(?:about|that|to)\b", core) else 'about '
        return (f"{hello}\n\n{'I hope you are well. This is a gentle reminder' if polite else 'Just a quick reminder'} {joiner}{core}"
                f"{' on [date]' if placeholders else ''}. {'Thank you very much.' if polite else 'Thanks!'}\n\n[Your name]")
    core = re.sub(r"(?i)^(?:you )?(?:know )?(?:that )?", '', core)
    lead = {'saying': 'I just wanted to say', 'about': 'I wanted to get in touch about', 'wishing': 'I wanted to wish you',
            'to wish': 'I wanted to wish you'}.get(purpose, 'I wanted to let you know that')
    return (f"{hello}\n\n{'I hope you are well. ' if polite else 'Hope you are doing well! '}{lead} {core}. "
            f"{'Please let me know if you have any questions.' if polite else 'Let me know if you have any questions.'}\n\n"
            f"{'Kind regards' if polite else 'Best'},\n[Your name]")


def message_reply(messages):
    turns = user_turns(messages)
    if not turns:
        return None
    last = turns[-1].strip()
    req = None
    for i in range(len(turns) - 1, max(-1, len(turns) - 4), -1):
        first = re.split(r"(?<=[.!?])\s+", turns[i].strip())[0].rstrip('.!?')
        m = MSG.search(first)
        if m:
            req = (i, m, turns[i])
            break
    if not req:
        return None
    i, m, text = req
    style = None
    if i != len(turns) - 1:
        lowl = last.lower()
        if re.search(r"\b(?:more polite|politer|more formal|formal|more respectful|more professional)\b", lowl):
            style = 'polite'
        elif re.search(r"\b(?:more casual|less formal|friendlier|more friendly|warmer|more relaxed)\b", lowl):
            style = 'friendly'
        else:
            return None
    style = style or ('polite' if re.search(r"(?i)\b(?:polite|formal|professional)\b", m[1] or '') else 'friendly')
    placeholders = bool(re.search(r"(?i)placeholder|\[date\]", text))
    purpose = (m[4] or '').lower()
    clause = _clause(m[5] or '')
    if not clause:
        return None
    msg = compose_message(purpose, clause, m[3], style, placeholders)
    if i != len(turns) - 1:
        lead = 'Here is a more polite version:' if style == 'polite' else 'Here is a friendlier version:'
    else:
        lead = 'Here is a message you could send:'
    return out('talk-message', f"{lead}\n\n{msg}", 'Message composed from the request (everyday_talk.py): recipient, purpose and clause; non-neural.')
