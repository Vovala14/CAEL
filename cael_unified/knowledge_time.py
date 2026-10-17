"""Conservative, extractive event/date selection from licensed source text."""
import re

from .knowledge_query import content_words

DATE = re.compile(r'\b(?:[12]\d{3}s?|\d{1,2}(?:st|nd|rd|th)[ -]century|\d{1,4}\s*(?:BC|BCE|AD|CE))\b', re.I)
EVENTS = {
    'born': r'\b(?:was|were|is) born\b',
    'founded': r'\b(?:founded|established|incorporated|formed)\b',
    'formed': r'\b(?:formed|founded|established)\b',
    'started': r'\b(?:formed|founded|established|incorporated|started|began)\b',
    'discovered': r'\b(?:discovered|discovery|first identified)\b',
    'created': r'\b(?:created|introduced|invented|developed|founded|conceived|began working on)\b',
    'developed': r'\b(?:developed|introduced|invented|successful test|patent|conceived|began working on)\b',
    'invented': r'\b(?:invented|developed|introduced|successful test|patent|demonstrated|built|constructed)\b',
}


def temporal_excerpt(passages, parsed, title):
    """A history heading alone is never evidence of the requested event/date."""
    event = parsed.get('event')
    if not event:
        event = next((key for key in EVENTS if re.search(r'\b' + key + r'\b', parsed['original'], re.I)), None)
    if event not in EVENTS:
        return None
    candidates = []
    predecessors = None
    title_terms = set(content_words(title))
    for row in passages:
        body = row['body']
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', body)
        if event == 'invented' and re.search(r'\binventors\b.+\b(?:prior to|before)\b', body, re.I):
            predecessors = row
            if parsed.get('focus') == 'agent':
                # Preserve the source's multiple-contributor account rather than
                # turn a dated milestone into a claim of sole inventorship.
                account = ' '.join(part for part in parts if re.search(r'\binventors\b|\bpre-dated\b', part, re.I))
                if 8 <= len(account.split()) <= 85:
                    return account, row
        for index, sentence in enumerate(parts):
            if not DATE.search(sentence) or not re.search(EVENTS[event], sentence, re.I):
                continue
            if re.match(r'(?i)^they\b', sentence):
                continue  # Plural subsidiary objects are not the article's subject.
            if event in ('founded', 'formed', 'started'):
                trigger = re.search(EVENTS[event], sentence, re.I)
                before, after = sentence[:trigger.start()], sentence[trigger.end():]
                passive = re.search(r'\b(?:was|were|been|is)\s*$', before, re.I)
                # "X formed in 1981" is intransitive; "A founded X in
                # 1981" anchors X after the verb. Never use a subsidiary's date.
                intransitive = re.match(r'\s+(?:in|on|during)\s+', after, re.I)
                # In the active form only the direct object is the founded
                # entity: "A formed B after leaving X in 1983" dates B, not X.
                entity_text = before if passive or intransitive else re.split(r'(?i)[,;]|\b(?:in|on|during|after|before|when|while|with|by|from|as)\b', after, maxsplit=1)[0]
                # "It was formed in 1981" refers back to the article subject
                # when the previous sentence names it.
                pronoun = (passive or intransitive) and re.fullmatch(
                    r'(?i)\s*(?:it|the (?:band|group|company|organi[sz]ation|firm|club|team|party|charity|movement))(?:\s+(?:was|were|is))?\s*', before)
                if pronoun and index and title_terms <= set(content_words(parts[index - 1] + ' ' + parts[0])):
                    entity_text = title
                if title_terms and not title_terms <= set(content_words(entity_text)):
                    continue
            historical = row['heading'] == 'Introduction' or re.search(r'\b(?:history|early|origins?|invention|development|childhood|life|birth)\b', row['heading'], re.I)
            tested_practical = re.search(r'\bfirst successful test\b', sentence, re.I) and re.search(r'\bpractical\b', body, re.I)
            if event in ('invented', 'created', 'developed') and not (historical or tested_practical):
                continue  # A component or later variant is not the whole invention.
            if event in ('invented', 'created', 'developed') and row['heading'] != 'Introduction' and not title_terms & set(content_words(sentence + ' ' + parts[0])):
                continue
            if event == 'invented' and not (re.search(r'\binvented\b', sentence, re.I) or
                    (re.search(r'\bfirst\b', sentence, re.I) and re.search(r'\b(?:developed|patent|demonstrated|built|constructed|successful test)\b', sentence, re.I))):
                continue  # A later introduction or upgrade does not date the invention.
            # Keep a preceding actor/context when the dated sentence refers back.
            prefix = ''
            if index and re.match(r'(?i)^(?:he|she|it|this|the (?:first|patent|instrument|device|invention|company))\b', sentence):
                prefix = parts[0] + ' '
            window = prefix + sentence
            if not window.endswith(('.', '!', '?')) or len(window.split()) > 85:
                continue  # Never truncate away the date or its qualifications.
            score = 100 * (row['heading'] == 'Introduction')
            score += 12 * len(title_terms & set(content_words(sentence))) / max(1, len(title_terms))
            score += 15 * bool(re.search(r'\b' + event + r'\b', sentence, re.I))
            if event in ('invented', 'developed', 'created'):
                score += 50 * bool(re.search(r'\bfirst successful test\b', sentence, re.I))
                score += 30 * bool(re.search(r'\bfirst\b.*\b(?:patent|invented|built|demonstrated)\b', sentence, re.I))
                score += 15 * bool(re.search(r'\bpractical\b', body, re.I))
                score -= 35 * bool(re.search(r'\b(?:research|researching|proposed|processing|method of)\b', sentence, re.I))
                score -= 40 * bool(re.search(r'\b(?:term|word|called)\b', sentence, re.I))
            score -= .002 * int(row['position']) + .001 * index
            candidates.append((score, window, row))
    if not candidates:
        return None
    _, text, chosen = max(candidates, key=lambda item: item[0])
    if predecessors is not None and re.search(r'\bfirst successful test\b', text, re.I):
        text = 'Earlier inventors also contributed. ' + text
    return text, chosen
