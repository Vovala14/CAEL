"""Questions about CAEL itself, and about the current time and date (no model, no web).

'Do you have internet access?', 'Can you browse the web?', 'What time is it?', 'What's the date?', 'What time is it in Tokyo?',
'Do you remember what I told you yesterday?', 'Are you an AI?', 'Who made you?', 'How do you work?'. Every answer is true of
CAEL: a non-neural system (rules, search, counted statistics), which sees only the current conversation.
The clock is the machine's clock; city times use fixed offsets with the usual summer-time rules.
"""
import datetime as dt
import os
import re

YOU = r"(?:you|u|cael)"


def web_on():
    return os.environ.get('CAEL_WEB_SEARCH', '1') != '0'


# city: (UTC offset in hours, summer-time rule: 'eu', 'us', 'au', 'nz', 'cl', or None)
CITIES = {
    'london': (0, 'eu'), 'dublin': (0, 'eu'), 'lisbon': (0, 'eu'), 'edinburgh': (0, 'eu'), 'manchester': (0, 'eu'),
    'paris': (1, 'eu'), 'berlin': (1, 'eu'), 'madrid': (1, 'eu'), 'rome': (1, 'eu'), 'amsterdam': (1, 'eu'), 'brussels': (1, 'eu'),
    'vienna': (1, 'eu'), 'stockholm': (1, 'eu'), 'oslo': (1, 'eu'), 'copenhagen': (1, 'eu'), 'warsaw': (1, 'eu'), 'prague': (1, 'eu'),
    'zurich': (1, 'eu'), 'barcelona': (1, 'eu'), 'munich': (1, 'eu'), 'budapest': (1, 'eu'),
    'athens': (2, 'eu'), 'helsinki': (2, 'eu'), 'kyiv': (2, 'eu'), 'kiev': (2, 'eu'), 'bucharest': (2, 'eu'), 'riga': (2, 'eu'),
    'tallinn': (2, 'eu'), 'vilnius': (2, 'eu'), 'sofia': (2, 'eu'), 'cairo': (2, None), 'johannesburg': (2, None), 'cape town': (2, None),
    'jerusalem': (2, None), 'tel aviv': (2, None),
    'istanbul': (3, None), 'moscow': (3, None), 'nairobi': (3, None), 'riyadh': (3, None), 'doha': (3, None),
    'dubai': (4, None), 'abu dhabi': (4, None), 'tehran': (3.5, None), 'karachi': (5, None), 'tashkent': (5, None),
    'delhi': (5.5, None), 'new delhi': (5.5, None), 'mumbai': (5.5, None), 'bangalore': (5.5, None), 'kolkata': (5.5, None),
    'kathmandu': (5.75, None), 'dhaka': (6, None), 'bangkok': (7, None), 'jakarta': (7, None), 'hanoi': (7, None),
    'beijing': (8, None), 'shanghai': (8, None), 'hong kong': (8, None), 'singapore': (8, None), 'taipei': (8, None),
    'manila': (8, None), 'kuala lumpur': (8, None), 'perth': (8, None),
    'tokyo': (9, None), 'osaka': (9, None), 'seoul': (9, None),
    'adelaide': (9.5, 'au'), 'brisbane': (10, None), 'sydney': (10, 'au'), 'melbourne': (10, 'au'), 'canberra': (10, 'au'),
    'auckland': (12, 'nz'), 'wellington': (12, 'nz'),
    'reykjavik': (0, None), 'lagos': (1, None), 'casablanca': (1, None),
    'new york': (-5, 'us'), 'boston': (-5, 'us'), 'washington': (-5, 'us'), 'miami': (-5, 'us'), 'toronto': (-5, 'us'), 'atlanta': (-5, 'us'),
    'chicago': (-6, 'us'), 'dallas': (-6, 'us'), 'houston': (-6, 'us'), 'mexico city': (-6, None),
    'denver': (-7, 'us'), 'phoenix': (-7, None), 'los angeles': (-8, 'us'), 'san francisco': (-8, 'us'), 'seattle': (-8, 'us'),
    'vancouver': (-8, 'us'), 'las vegas': (-8, 'us'), 'anchorage': (-9, 'us'), 'honolulu': (-10, None),
    'sao paulo': (-3, None), 'são paulo': (-3, None), 'rio de janeiro': (-3, None), 'buenos aires': (-3, None), 'santiago': (-4, 'cl'),
    'lima': (-5, None), 'bogota': (-5, None), 'bogotá': (-5, None),
}


def _nth_sunday(year, month, n):
    """n-th Sunday of a month (n=-1: the last)."""
    if n > 0:
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - 6) % 7)


def summer(rule, utc):
    """Is summer time in force for this rule at this UTC moment (approximate to the day)?"""
    d = utc.date()
    y = d.year
    if rule == 'eu':
        return _nth_sunday(y, 3, -1) <= d < _nth_sunday(y, 10, -1)
    if rule == 'us':
        return _nth_sunday(y, 3, 2) <= d < _nth_sunday(y, 11, 1)
    if rule == 'au':
        return not (_nth_sunday(y, 4, 1) <= d < _nth_sunday(y, 10, 1))
    if rule == 'nz':
        return not (_nth_sunday(y, 4, 1) <= d < _nth_sunday(y, 9, -1))
    if rule == 'cl':
        return not (_nth_sunday(y, 4, 1) <= d < _nth_sunday(y, 9, 1))
    return False


def city_time(city, now_utc=None):
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc)
    offset, rule = CITIES[city]
    hours = offset + (1 if rule and summer(rule, now_utc) else 0)
    return now_utc + dt.timedelta(hours=hours), hours


def clock(t):
    return f"{t.strftime('%H:%M')} ({(t.hour % 12) or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'})"


def day_text(t):
    return f"{t.strftime('%A')} {t.day} {t.strftime('%B %Y')}"


def offset_text(hours):
    sign = '+' if hours >= 0 else '−'
    h = abs(hours)
    return f"UTC{sign}{int(h)}" + (f":{int(round((h % 1) * 60)):02d}" if h % 1 else '')


INTERNET = re.compile(r"(?i)^\s*(?:so,?\s+|hey,?\s+|ok,?\s+)?(?:do|can|are|have)\s+" + YOU + r"(?:\s+\w+){0,4}?\s+(?:(?:access|connection) to the (?:internet|web)|"
                      r"(?:the )?internet(?: access)?|online|on the internet|connected(?: to the (?:internet|web))?|browse(?: the (?:web|internet))?|"
                      r"search the (?:web|internet)|google(?: things)?|look (?:things|stuff) up(?: online)?)\s*\??\s*$|^\s*are you (?:online|offline)\s*\??\s*$")
TIME_NOW = re.compile(r"(?i)^\s*(?:hey,?\s+|so,?\s+|ok,?\s+|please,?\s+)?(?:what(?:'s| is)? the (?:current )?time|what time is it|do you know (?:what )?(?:the )?time|"
                      r"tell me the time|current time|time now|what's the time)\b(?!.*\b(?:when|if|takes?|flight|train|recipe|oven)\b)")
DATE_NOW = re.compile(r"(?i)\b(?:what(?:'s| is) (?:the )?(?:date|day)(?: today| it)?|what (?:day|date) is it|today'?s date|what is today|which day is it|"
                      r"what (?:month|year) is it|what(?:'s| is) the (?:month|year)|what day of the (?:week|month) is it|which day of the week)\b")
IN_CITY = re.compile(r"(?i)\btime\b.{0,20}\bin ([a-zà-ü][a-zà-ü .'-]{1,24}?)\s*(?:right now|now|today)?\s*\??\s*$")
MEMORY = re.compile(r"(?i)\b(?:do|can|will|did) " + YOU + r" (?:remember|recall|keep|save|store)\b|\b" + YOU + r" (?:remember|recall) (?:me|what|our|my)\b|"
                    r"\bwhat did i (?:tell|say to) you (?:yesterday|last time|before|earlier)\b")
WHAT_ARE = re.compile(r"(?i)\b(?:are you|r u) (?:an? )?(?:ai|bot|robot|chatbot|computer|machine|human|real person|person|real|chatgpt|gpt|llm|language model|neural network)\b|"
                      r"\bwhat (?:are|kind of (?:ai|thing|program|bot) are) you\b|\bare you (?:a )?(?:human|person)\b")
WHO_MADE = re.compile(r"(?i)\b(?:who|which company) (?:made|built|created|developed|programmed|trained|owns|runs) " + YOU + r"\b|\bwho(?:'s| is) your (?:maker|creator|developer|owner)\b|^\s*who are you\s*\??\s*$")
HOW_WORK = re.compile(r"(?i)\bhow do " + YOU + r" (?:work|think|know|learn|answer)\b|\bhow (?:were|was) " + YOU + r" (?:made|built|trained)\b|\bwhat are you (?:made|built) (?:of|from|with)\b")
NAME = re.compile(r"(?i)\bwhat(?:'s| is) your name\b|\bwho am i (?:talking|speaking|chatting) (?:to|with)\b")
SEE = re.compile(r"(?i)\b(?:can|do) " + YOU + r" (?:see|read|look at|open|understand) (?:images?|pictures?|photos?|files?|pdfs?|attachments?|videos?)\b")


def reply(text, kind):
    return dict(route='chat/about-' + kind, response=text, sources=[], details='About CAEL itself (about_me.py): true statements about how it works; the time is the machine clock.')


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 160:
        return None
    if INTERNET.search(text):
        if web_on():
            return reply("Yes. When a question needs current or outside facts, I can search the web and I tell you where the answer came from. "
                         "I can't log in to sites, open your links behind a login, buy things or send messages for you, and I don't download files. "
                         "For everyday things (sums, writing, Python, advice) I answer from my own rules and notes without searching.", 'internet')
        return reply("Not right now: web search is switched off here, so I'm answering only from my own rules and notes. I can still work things out, "
                     "write, help with Python and give everyday advice.", 'internet')
    m = IN_CITY.search(text)
    if m and re.search(r"(?i)\bwhat(?:'s| is)? the time\b|\bwhat time\b|\btime is it\b|\blocal time\b|\bcurrent time\b", text):
        city = m[1].strip(" .'?").lower()
        city = re.sub(r'^(?:the city of |central )', '', city)
        if city in CITIES:
            t, hours = city_time(city)
            return reply(f"In {city.title()} it's about **{clock(t)}** on {day_text(t)} ({offset_text(hours)}). "
                         "That's from my clock and the city's usual time-zone and summer-time rules, so it can be off by an hour around a clock change.", 'city-time')
        return reply(f"I don't have {m[1].strip()} in my time-zone list. Tell me the country, or its offset from UTC, and I'll work it out.", 'city-time-unknown')
    if TIME_NOW.search(text):
        now = dt.datetime.now().astimezone()
        hours = now.utcoffset().total_seconds() / 3600
        return reply(f"It's **{clock(now)}** on {day_text(now)} where I'm running ({offset_text(hours)}). "
                     "If you're in a different time zone, tell me your city and I'll convert it.", 'time')
    if DATE_NOW.search(text):
        now = dt.datetime.now().astimezone()
        return reply(f"Today is **{day_text(now)}** (by the clock where I'm running; near midnight it may already be a different day where you are).", 'date')
    if MEMORY.search(text):
        return reply("Only within this conversation: I can use anything you've said earlier in this chat. I don't remember separate, earlier "
                     "conversations, so if it was in another chat, please tell me again.", 'memory')
    if WHAT_ARE.search(text):
        return reply("I'm CAEL, a computer program, not a person. Unusually for a chat assistant, I'm not a neural network or a large language model: "
                     "I work with hand-written rules, search, and counted statistics from text, plus web search when a question needs it. "
                     "That makes me careful about what I claim, but I know less than a big AI model and I get some questions wrong.", 'what')
    if WHO_MADE.search(text):
        return reply("I'm CAEL, made by the vynly project: an independent effort to build a useful chat assistant without neural networks. "
                     "My code and models are published openly on GitHub and Hugging Face.", 'who')
    if HOW_WORK.search(text):
        return reply("A team of small specialists handles each message: a calculator for sums, a writer for messages and notes, a programmer for "
                     "Python, a supporter for difficult moments, an advisor for everyday problems, and researchers who search the web and quote "
                     "their sources. Each one uses rules and search rather than a neural network, and checks its own answer where it can "
                     "(for example by running code or redoing a sum).", 'how')
    if NAME.search(text):
        return reply("I'm CAEL. What would you like to talk about?", 'name')
    if SEE.search(text):
        return reply("I can only read the text you type. I can't open images, files or links, so paste the text or describe what's in it.", 'see')
    return None
