"""Accepted answers from Stack Exchange sites as one more source for how-to questions (official public API, no key).

General search engines refuse or scramble automated queries, so the open web cannot be relied on for practical
questions ("how do I season a cast iron pan"). Stack Exchange publishes its questions and answers under CC BY-SA with
a documented API. For a question, the one or two sites whose subject matches its words are searched, and the accepted
answers of the best-matching questions are returned as pages for web_check to quote, with a link and the licence.

Only the question's keywords are sent, never the user's sentence. The keyless API allows about 300 calls a day per
address, so results are cached for a day and the source switches itself off for the day when the allowance runs low.
Set CAEL_STACKEXCHANGE=0 to turn it off.
"""
import html
import os
import re
import time
from urllib.parse import urlencode

from .network import NETWORK, LookupUnavailable

API = 'https://api.stackexchange.com/2.3/'
LICENCE = 'CC BY-SA (Stack Exchange)'
PAUSED = [0.0]          # no calls before this time (allowance low, or the API asked for a pause)
SITES = {
    'cooking': ('Seasoned Advice', 'cook bake baking recipe pan oven boil fry frying dough sauce meat egg rice bread knife iron flour sugar '
                                   'butter roast grill simmer pasta soup marinade spice salt chicken steak fish vegetable freezer skillet season'),
    'diy': ('Home Improvement', 'paint wall drill screw leak pipe tile floor door plumbing wire wiring repair install shelf drywall ceiling '
                                'window roof gutter caulk faucet toilet outlet insulation deck concrete hinge squeaky mould mold'),
    'gardening': ('Gardening & Landscaping', 'plant soil seed garden lawn prune compost tomato flower houseplant weed fertilizer fertiliser '
                                             'pot repot leaf leaves tree shrub herb watering succulent cactus orchid snake rose'),
    'pets': ('Pets', 'dog cat puppy kitten hamster rabbit pet litter leash vet bark barking scratch aquarium parrot guinea'),
    'travel': ('Travel', 'flight airport visa luggage passport trip hotel layover airline customs baggage train ticket itinerary hostel'),
    'fitness': ('Physical Fitness', 'workout exercise run running muscle stretch gym squat pushup plank cardio weight lifting jog marathon '
                                    'sore warmup deadlift protein'),
    'money': ('Personal Finance', 'budget saving savings loan credit mortgage invest investing tax debt interest pension retirement salary '
                                  'bank emergency fund rent'),
    'parenting': ('Parenting', 'toddler baby kid child children teen teenager bedtime tantrum newborn homework sibling daughter son potty'),
    'workplace': ('The Workplace', 'boss manager coworker colleague interview raise resign job promotion office resignation notice meeting '
                                   'salary negotiate feedback'),
    'interpersonal': ('Interpersonal Skills', 'friend apologise apologize partner roommate neighbour neighbor awkward conversation argue '
                                              'argument invite decline rude boundary'),
    'lifehacks': ('Lifehacks', 'stain wax remove clean cleaning smell odor odour organise organize tablecloth laundry sticky residue wrinkle '
                               'zipper declutter candle fridge shoe iron glue'),
    'bicycles': ('Bicycles', 'bike bicycle cycling tyre tire chain brake gear saddle puncture'),
    'mechanics': ('Motor Vehicle Maintenance', 'car engine oil brake battery tyre tire clutch coolant spark jump start windshield'),
    'outdoors': ('The Great Outdoors', 'camp camping hike hiking tent trail backpack campfire bear blister compass kayak'),
    'music': ('Music', 'guitar piano chord scale practice practise sing singing violin drum rhythm tune tuning'),
    'photo': ('Photography', 'camera photo lens exposure aperture shutter iso tripod portrait focus'),
    'boardgames': ('Board & Card Games', 'game games party board card chess poker dice players charades'),
    'languagelearning': ('Language Learning', 'language spanish french german japanese vocabulary fluent fluency conversational accent '
                                              'pronunciation learn learning immersion'),
    'english': ('English Language & Usage', 'grammar word sentence meaning phrase idiom comma apostrophe tense spelling synonym'),
    'superuser': ('Super User', 'computer laptop pc wifi router keyboard screen file folder browser printer usb password backup'),
    'coffee': ('Coffee', 'coffee espresso brew grind beans latte caffeine'),
    'sports': ('Sports', 'skateboard ollie football soccer basketball tennis swim swimming golf serve dribble'),
    'crafts': ('Arts & Crafts', 'knit knitting sew sewing crochet paint brush glue paper clay origami embroidery'),
    'sustainability': ('Sustainable Living', 'recycle recycling energy solar waste plastic compost insulation'),
}
STEMS = None


def stem(w):
    w = w.lower()
    for suf in ('ing', 'es', 's', 'ed'):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def sites_for(text, limit=2):
    """The sites whose subject words appear in the question, best first."""
    global STEMS
    if STEMS is None:
        STEMS = {site: {stem(w) for w in words.split()} for site, (_, words) in SITES.items()}
    asked = {stem(w) for w in re.findall(r'[A-Za-z]+', text)}
    scored = sorted(((len(asked & stems), site) for site, stems in STEMS.items()), reverse=True)
    top = scored[0][0] if scored else 0
    return [site for n, site in scored if n >= 1 and n == top][:limit]      # a second site only on a tie


def plain(body):
    body = re.sub(r'(?is)<(pre|code|blockquote)\b.*?</\1>', ' ', body)
    body = re.sub(r'(?i)</(p|li|h\d|ul|ol|div)>|<br\s*/?>', '. ', body)
    body = html.unescape(re.sub(r'<[^>]+>', '', body))
    body = re.sub(r'\s*\.(\s*\.)+', '.', re.sub(r'\s+', ' ', body))
    return re.sub(r'([.!?:;,])\.', r'\1', body).strip()


def call(path, network=None, **params):
    if time.time() < PAUSED[0]:
        raise LookupUnavailable('Stack Exchange allowance is used up for now')
    data = (network or NETWORK).json(API + path + '?' + urlencode(params), ttl=86400)
    if data.get('backoff'):
        PAUSED[0] = time.time() + int(data['backoff']) + 1
    if isinstance(data.get('quota_remaining'), int) and data['quota_remaining'] < 20:
        PAUSED[0] = time.time() + 6 * 3600
    if data.get('error_id'):
        raise LookupUnavailable(str(data.get('error_message', 'Stack Exchange error')))
    return data.get('items', [])


def pages(keywords, question, limit=3, network=None, sites=None):
    """(source name, host, title, body, url): the best answer to each stored question that matches the user's question."""
    if os.environ.get('CAEL_STACKEXCHANGE', '1') == '0' or os.environ.get('CAEL_WEB_SEARCH', '1') == '0':
        return []
    common = set('how do i can you what is are the a an to of in on for my your some good best way get make should would with out it '
                 'does did and or from at be this that there any when where why which who'.split())
    asked = {stem(w) for w in re.findall(r'[A-Za-z]+', question.lower()) if w not in common}
    try:
        from . import open_chat
        rarest = max(asked, key=lambda w: open_chat.idf(open_chat.stem(w))) if asked else None
    except Exception:
        rarest = None
    out = []
    for site in (sites or sites_for(question)):
        questions = {}
        for path, params in (('similar', dict(title=question[:200])), ('search/advanced', dict(q=keywords[:200]))):
            try:
                for q in call(path, network, site=site, sort='relevance', order='desc', pagesize=6, **params):
                    title = {stem(w) for w in re.findall(r'[A-Za-z]+', html.unescape(q.get('title', '')).lower())}
                    # the stored question must be about the same thing: its rarest word ("pigeons") and one more, or a third of
                    # the asked words ("How can I repel pigeons from roosting on my apartment balcony?" for "get pigeons to stop
                    # coming to my balcony")
                    shared = asked & title
                    if q.get('answer_count') and (len(shared) >= max(1, (len(asked) + 2) // 3) or (rarest in shared and len(shared) >= 2)):
                        questions.setdefault(str(q['question_id']), q)
            except LookupUnavailable:
                continue
            if len(questions) >= limit:
                break
        if not questions:
            continue
        keep = dict(list(questions.items())[:limit])
        best = {}
        for a in call('questions/' + ';'.join(keep) + '/answers', network, site=site, filter='withbody', sort='votes', order='desc', pagesize=20):
            qid = str(a.get('question_id'))
            rank = (bool(a.get('is_accepted')), a.get('score', 0))
            if qid in keep and a.get('score', 0) >= 1 and rank > best.get(qid, ((False, -1), None))[0]:
                best[qid] = (rank, a)
        for qid, (_, a) in best.items():
            body = plain(a.get('body', ''))
            if len(body) > 120:
                q = keep[qid]
                out.append((f'Stack Exchange ({SITES[site][0]})', 'stackexchange', html.unescape(q.get('title', '')), body[:20000], q.get('link', '')))
    return out
