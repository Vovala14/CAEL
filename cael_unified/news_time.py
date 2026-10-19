"""Authored date-scope guards for the bounded recent-news providers.

No event knowledge or current answers live here. Dates in product/topic names
are not interpreted as request dates without a temporal frame.
"""
from datetime import datetime, timezone
import re

MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
WEEKDAY = r'(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)'
DATED = re.compile(
    r'\b(?:in|on|during|since|before|after|between|from|for|as of)\s+(?:the\s+)?(?:'
    r'\d{4}(?:-\d{1,2}(?:-\d{1,2})?|s)?\b|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|'
    r'\d{1,2}(?:st|nd|rd|th)?\s+' + MONTH + r'\b|' + MONTH + r'\b|' + WEEKDAY + r'\b|'
    r'\d{1,2}(?:st|nd|rd|th)[ -]century\b)|'
    r'\b(?:last|next|this)\s+(?:month|year)\b|\b(?:last|next)\s+(?:week|' + WEEKDAY + r')\b|'
    r'\b(?:tomorrow|day after tomorrow|day before yesterday|historical|archived?)\b|'
    r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\s+(?:hours?|days?|weeks?|months?|years?)\s+ago\b|'
    r'\b(?:past|last|previous|next)\s+(?:\d+|one|two|three|four|five|six|seven|a|an)\s+(?:hours?|days?|weeks?|months?|years?)\b|'
    r'\b(?:past|previous|coming)\s+(?:month|year|week)\b', re.I)
NON_NEWS = re.compile(r'\b(?:write|draw|generate|create|debug|fix|script|function|my|your|our|story|poem)\b|'
                      r'^\s*(?:what (?:is|are)\s+(?:the\s+)?(?:news|headlines)[?.!]*$|'
                      r'what (?:does|do)\s+(?:the\s+)?(?:news|headlines)\s+mean\b|'
                      r'define\s+(?:the\s+)?(?:news|headlines)\b|'
                      r'explain\s+(?:the\s+)?meaning of\s+(?:news|headlines)\b)', re.I)


def unsupported_period(text):
    """Return the explicit unsupported scope, not a guessed date from a number."""
    if len(text) > 1600:
        return None
    # The recent fallback covers up to seven dates; exact hour windows do not.
    for match in DATED.finditer(text):
        phrase = match[0]
        if re.fullmatch(r'(?i)past (?:week|7 days|seven days)', phrase):
            continue
        return phrase
    if re.search(r'(?i)\blast 24 hours\b', text):
        return 'last 24 hours'
    return None


def news_scope_request(text):
    """An explicit dated news/events request, excluding creative/personal frames."""
    if NON_NEWS.search(text) or not unsupported_period(text):
        return False
    return bool(re.search(r'(?i)\b(?:news|headlines|updates|happening|developments)\b|^\s*what happened\b', text))


def historical_question(text, now=None):
    """Narrow event/year grammar; current/future years keep freshness controls."""
    if len(text) > 1600 or NON_NEWS.search(text):
        return None
    year_first = re.fullmatch(r'(?i)what happened in ([12]\d{3}) (?:in|to|at) (.+?)[?.!]*', text.strip())
    subject_first = re.fullmatch(r'(?i)what happened (?:in|to|at) (.+?) in ([12]\d{3})[?.!]*', text.strip())
    if not (year_first or subject_first):
        return None
    year, subject = year_first.groups() if year_first else subject_first.groups()[::-1]
    subject = subject.strip(' ?.!,')
    now = now or datetime.now(timezone.utc)
    if not subject or len(subject) > 160 or int(year) >= now.year:
        return None
    if re.search(r'(?i)\b(?:today|now|yesterday|tomorrow|latest|current|recent|news|headlines)\b|\d{4}|[;\n]', subject):
        return None
    from .knowledge_query import content_words, static_allowed
    if not static_allowed(text):
        return None
    return dict(kind='historical-event', subject=subject, terms=content_words(subject)[:16],
                static=True, original=text, year=year)


def historical_excerpt(passages, parsed, title):
    """Select one complete, explicitly dated source sentence; no date inference."""
    from .knowledge_query import content_words
    wanted = set(content_words(title))
    year = re.compile(r'\b' + re.escape(parsed['year']) + r'\b(?!\s*(?:BC|BCE))', re.I)
    candidates = []
    for row in passages:
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', row['body'])
        for index, sentence in enumerate(parts):
            if not year.search(sentence) or not sentence.endswith(('.', '!', '?')):
                continue
            # A list/range/reference/publication date is not a verified event
            # occurring in the year. Require explicit event-time grammar.
            dated_event = re.search(r'(?i)\b(?:in|on|during)\s+(?:\d{1,2}\s+' + MONTH + r'\s+|' + MONTH + r'\s+\d{1,2},?\s+)?' + re.escape(parsed['year']) + r'\b(?!\s*(?:BC|BCE))', sentence)
            if not dated_event or re.search(r'(?i)\b(?:published|edition|accessed|retrieved|ISBN|bibliography)\b', sentence):
                continue
            years = set(re.findall(r'\b[12]\d{3}\b', sentence))
            if years != {parsed['year']}:
                # Keep an explicitly bounded aftermath ("X surrendered in 1945
                # and remained occupied until 1952") with its qualification.
                # Other mixed-year clauses cannot establish the requested event.
                later = sentence[dated_event.end():]
                aftermath = set(re.findall(r'(?i)\buntil\s+([12]\d{3})\b', later))
                if (years - {parsed['year']} != aftermath or not aftermath
                        or not wanted <= set(content_words(sentence[:dated_event.start()]))
                        or any(int(other) <= int(parsed['year']) for other in aftermath)):
                    continue
            if re.search(r'\b(?:[12]\d{3})\s*(?:[–—-]|to|and)\s*' + parsed['year'] + r'\b', sentence):
                continue
            # Evidence must name the topic in the same sentence, or in an
            # immediately preceding sentence when a singular pronoun refers back.
            prefix = ''
            if wanted and not wanted <= set(content_words(sentence)):
                if index and re.match(r'(?i)^(?:it|the country|the city|the company|the band)\b', sentence) and wanted <= set(content_words(parts[index - 1])):
                    prefix = parts[index - 1] + ' '
                else:
                    continue
            window = prefix + sentence
            if not 8 <= len(window.split()) <= 80:
                continue
            historical = bool(re.search(r'(?i)history|modern era|post.?war|ancient|medieval|early modern', row['heading']))
            score = 10 * (row['heading'] == 'Introduction') + 5 * historical - .001 * int(row['position']) - .01 * index
            candidates.append((score, window, row))
    if not candidates:
        return None
    _, text, row = max(candidates, key=lambda item: item[0])
    return text, row
