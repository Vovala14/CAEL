"""What an abbreviation stands for ("What does CPU stand for?", "What is NASA short for?"), from WordNet 3.0.

WordNet lists abbreviations as synonyms of their full names. A full name is accepted only when its words' initials
spell the abbreviation (ignoring small words like "of" and "and"), so "CPU" gives "central processing unit" and not
"processor". Several meanings are listed together (ATM: automated teller machine, asynchronous transfer mode).
"""
import json
import re
import sqlite3

from .bundle import ROOT

ASK = re.compile(r"(?i)^\s*(?:what|wat)\s+(?:does|do|did)\s+(?:the\s+)?(?:abbreviation\s+|acronym\s+)?([A-Za-z][A-Za-z.&]{1,9})\s+"
                 r"(?:stand|stands)\s+for\s*\??\s*$|^\s*(?:what\s+is|what's)\s+([A-Za-z][A-Za-z.&]{1,9})\s+short\s+for\s*\??\s*$|"
                 r"^\s*(?:what\s+is\s+the\s+)?(?:full\s+form|meaning)\s+of\s+([A-Z][A-Z.&]{1,9})\s*\??\s*$")
SMALL = {'of', 'and', 'the', 'for', 'in', 'on', 'to', 'a', 'an', '&'}


def initials(name):
    parts = [p for p in re.split(r'[\s\-/]+', name) if p and p.lower() not in SMALL]
    return ''.join(p[0] for p in parts).lower()


def expansions(abbreviation):
    letters = re.sub(r'[^a-z]', '', abbreviation.lower())
    if len(letters) < 2:
        return []
    found = []
    try:
        with sqlite3.connect(f'file:{ROOT / "models/cael-dictionary-wn30/dictionary.sqlite"}?mode=ro', uri=True) as db:
            rows = db.execute('select s.words, s.gloss from lemma l join synset s on s.id = l.synset where l.word = ?',
                              (letters,)).fetchall()
    except sqlite3.Error:
        return []
    for words, gloss in rows:
        for w in json.loads(words):
            if ' ' in w or '-' in w:
                if initials(w) == letters and w.lower() not in [f[0].lower() for f in found]:
                    found.append((w, gloss))
                    break
    return found


ROLE = re.compile(r"(?i)^\s*what\s+(?:does|do)\s+(?:an?\s+|the\s+)?([a-z]+(?:\s[a-z]+)?)\s+do\s*(?:for a living|all day|at work)?\s*\??\s*$")
PERSON_HINTS = re.compile(r'\b(?:person|someone|one who|who |specialist|practitioner|worker|expert|professional|officer|member|'
                          r'employee|teacher|operator|artist|scientist)\b')


def role_reply(text):
    """"What does a doctor do?": the WordNet definition of that person, if the word names a person."""
    m = ROLE.match(text)
    if not m:
        return None
    word = m.group(1).lower().strip()
    try:
        with sqlite3.connect(f'file:{ROOT / "models/cael-dictionary-wn30/dictionary.sqlite"}?mode=ro', uri=True) as db:
            rows = db.execute("select s.gloss from lemma l join synset s on s.id = l.synset where l.word = ? and l.pos = 'noun' "
                              "order by l.rank", (word.replace(' ', '_'),)).fetchall() or \
                   db.execute("select s.gloss from lemma l join synset s on s.id = l.synset where l.word = ? and l.pos = 'noun' "
                              "order by l.rank", (word,)).fetchall()
    except sqlite3.Error:
        return None
    # The sense describing a job ("a licensed health professional ...") beats other person senses ("a woman who ...").
    job = re.compile(r'\b(?:professional|practitioner|trained|licensed|skilled|specialist|employed|whose job|who works|'
                     r'works? (?:in|for|on|with)|operat|qualified|expert)\b')
    rows = [(g,) for (g,) in rows if not re.search(r'\(\d{3,4}\s*-\s*\d{2,4}\)|\b(?:born|died)\b', g)]   # not a named person's biography
    gloss = next((g for (g,) in rows if job.search(g)), None) or next((g for (g,) in rows if PERSON_HINTS.search(g)), None)
    if not gloss:
        return None
    gloss = gloss.split(';')[0].strip()
    article = 'an' if word[0] in 'aeiou' else 'a'
    return dict(route='chat/role-definition', sources=[],
                response=f'{article.capitalize()} {word} is {gloss}.',
                details='From the WordNet 3.0 definition of the word. No neural model.')


def reply(text):
    m = ASK.match(text)
    if not m:
        return role_reply(text)
    abbreviation = next(g for g in m.groups() if g)
    found = expansions(abbreviation)
    if not found:
        return None
    shown = abbreviation.upper() if abbreviation.isalpha() and len(abbreviation) <= 6 else abbreviation
    if len(found) == 1:
        name, gloss = found[0]
        response = f'{shown} stands for **{name}**: {gloss.split(";")[0]}.'
    else:
        response = f'{shown} can stand for:\n' + '\n'.join(f'- **{n}**: {g.split(";")[0]}' for n, g in found[:4])
    return dict(route='chat/acronym', response=response, sources=[],
                details='Expanded from WordNet 3.0, where the full name\'s initials spell the abbreviation. No neural model.')
