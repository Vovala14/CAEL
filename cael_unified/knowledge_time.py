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

FOUNDING = {'founded', 'formed', 'started'}
ADVERB = r'(?:(?:probably|possibly|likely|reportedly|apparently|traditionally|first)\s+)?'


def passive_before(before):
    return re.search(r'\b(?:was|were|been|is)\s+' + ADVERB + r'$', before, re.I)


def subject_context(previous, title):
    """Only an adjacent, simple article-subject definition can license 'It'."""
    return bool(re.match(r'\s*' + re.escape(title) + r'\s+(?:is|was)\s+(?:an?|the)\s+', previous, re.I)
                and not re.search(r'(?i)\b(?:subsidiary|division|another|other|members?|named|called|renamed|founded|formed|created)\b|\b(?:and|but|while|whereas)\b.+\b(?:is|are|was|were)\b', previous))


def sentence_parts(body):
    """Keep honorifics and initials with the attributed agent's name."""
    protected = re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|c|ca)\.',
                       lambda match: match[0].replace('.', '\ue000'), body, flags=re.I)
    protected = re.sub(r'\b(?:[A-Za-z]\.){2,}', lambda match: match[0].replace('.', '\ue000'), protected)
    protected = re.sub(r'\b[A-Z]\.(?=\s+[A-Z])', lambda match: match[0].replace('.', '\ue000'), protected)
    return [part.replace('\ue000', '.') for part in re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)]


def founding_date(sentence, trigger):
    """Exclude an actor's lifespan and dates in a later, unrelated clause."""
    after = re.sub(r'\([^)]*\)', '', sentence[trigger.end():])
    after = re.split(r'(?i)\b(?:after|before|when|while|whose|who|which)\b|;', after, maxsplit=1)[0]
    date = DATE.search(after)
    if (date and re.search(r'(?i)\b(?:in|on|during|around|about|circa|c\.)\s+[^.;]*$', after[:date.start()])
            and not re.search(r'(?i)\b(?:born|died|graduated|married|retired|leaving|joined|left|became)\b', after[:date.start()])):
        return True
    before = sentence[:trigger.start()]
    return bool(re.match(r'(?i)\s*(?:in|on|during|around|about|circa)\s+(?:[12]\d{3}|(?:the\s+)?\d{1,2}(?:st|nd|rd|th)[ -]century)\b', before))


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
        parts = sentence_parts(body)
        if event == 'invented' and re.search(r'\binventors\b.+\b(?:prior to|before)\b', body, re.I):
            predecessors = row
            if parsed.get('focus') == 'agent':
                # Preserve the source's multiple-contributor account rather than
                # turn a dated milestone into a claim of sole inventorship.
                account = ' '.join(part for part in parts if re.search(r'\binventors\b|\bpre-dated\b', part, re.I))
                if 8 <= len(account.split()) <= 85:
                    return account, row
        for index, sentence in enumerate(parts):
            trigger = re.search(EVENTS[event], sentence, re.I)
            if not trigger:
                continue
            dated = bool(DATE.search(sentence))
            undated_founder = parsed.get('focus') == 'agent' and event in FOUNDING
            if not dated and not undated_founder:
                continue
            if parsed.get('focus')=='agent':
                passive=passive_before(sentence[:trigger.start()])
                intransitive=re.match(r'\s+(?:in|on|during)\s+',sentence[trigger.end():],re.I)
                if (passive or intransitive) and not re.search(r'\bby\s+[A-Za-z]',sentence[trigger.end():],re.I):
                    continue  # A founding date alone does not identify the founder.
                if re.search(r'(?i)\bby\s+(?:(?:an?|the)\s+)?(?:(?:royal|government|presidential|imperial)\s+)?(?:merg(?:ing|er)|combin(?:ing|ation)|join(?:ing)?|using|means|shaping|law|decree|act|statute)\b', sentence[trigger.end():]):
                    continue  # A formation mechanism is not an identified founder.
                if not dated and not passive and re.match(r'(?i)\s*(?:he|she|they|it|its|this|that|these|those)\b', sentence):
                    continue
            if re.match(r'(?i)^they\b', sentence):
                continue  # Plural subsidiary objects are not the article's subject.
            expanded_subject = False
            retained_context = None
            if event in FOUNDING:
                before, after = sentence[:trigger.start()], sentence[trigger.end():]
                if re.search(r"(?i)\b(?:not|never|wasn['’]t|weren['’]t|isn['’]t)\b", before):
                    continue
                if parsed.get('focus') != 'agent' and not founding_date(sentence, trigger):
                    continue
                passive = passive_before(before)
                # "X formed in 1981" is intransitive; "A founded X in
                # 1981" anchors X after the verb. Never use a subsidiary's date.
                intransitive = re.match(r'\s+(?:in|on|during)\s+', after, re.I)
                # In the active form only the direct object is the founded
                # entity: "A formed B after leaving X in 1983" dates B, not X.
                entity_text = before if passive or intransitive else re.split(r'(?i)[,;]|\b(?:in|on|during|after|before|when|while|with|by|from|as)\b', after, maxsplit=1)[0]
                # "It was formed in 1981" refers back to the article subject
                # when the previous sentence names it.
                pronoun = (passive or intransitive) and re.fullmatch(
                    r'(?i)\s*(?:it|the (?:band|group|company|organi[sz]ation|firm|club|team|party|charity|movement))(?:\s+(?:was|were|is)\s+' + ADVERB + r')?\s*', before)
                if pronoun and index and subject_context(parts[index - 1], title):
                    entity_text = title
                    previous = parts[index - 1]
                    if re.search(r'(?i)\b(?:uncertain|unknown|disputed|debated|contested|unconfirmed|unverified|fictional|imaginary|invented|legendary|mythical|believed|reported|alleged|claimed|not|possibly|perhaps|may|might|probably|approximately|roughly|traditionally|according)\b', previous):
                        retained_context = previous
                    else:
                        sentence = re.sub(r'(?i)^(?:it|the (?:band|group|company|organi[sz]ation|firm|club|team|party|charity|movement))\b', lambda _: title, sentence)
                        expanded_subject = True
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
            if retained_context:
                prefix = retained_context + ' '
            elif index and not expanded_subject and re.match(r'(?i)^(?:he|she|it|this|the (?:first|patent|instrument|device|invention|company))\b', sentence):
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
