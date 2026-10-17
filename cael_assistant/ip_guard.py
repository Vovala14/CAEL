"""CAEL copyright/trademark guard for image + emoji requests (rule-based, no NN).
Before any generation, protected characters / brands / franchises are rewritten to a generic, creatable description.
1) curated table (aliases -> generic description + emoji subject + rights holder)
2) Wikidata check for words the emoji model doesn't know: exact-label entity whose 'instance of' (P31) is a fictional
   character / franchise / brand / logo class -> generic rewrite from its description.
Wikidata is CC0. Lookups cached in data/ip_guard_cache.json. User-Agent per Wikimedia policy."""
import re, json, time, urllib.request, urllib.parse
from pathlib import Path
CAEL = Path(__file__).resolve().parent.parent; CACHE = CAEL / 'data' / 'ip_guard_cache.json'
UA = {'User-Agent': 'CAEL/0.2 (https://github.com/Vovala14/CAEL)'}
# name aliases -> (generic description shown to user, emoji/image subject, what it is, holder)
T = {}
def _add(names, generic, subject, kind, holder):
    for n in names.split('|'): T[n] = (generic, subject, kind, holder)
_add('pikachu|pickachu|pikachoo', 'yellow mouse with red cheeks', 'yellow mouse', 'character', 'Nintendo / The Pokémon Company')
_add('pokemon|pokémon|pokeball|poke ball|poké ball', 'red and white ball', 'red ball', 'franchise', 'Nintendo / The Pokémon Company')
_add('charizard', 'orange dragon', 'dragon', 'character', 'The Pokémon Company')
_add('mickey|mickey mouse', 'cartoon mouse with round ears', 'mouse', 'character', 'Disney')
_add('minnie|minnie mouse', 'cartoon mouse with a red bow', 'mouse', 'character', 'Disney')
_add('donald duck', 'white duck in a sailor hat', 'duck', 'character', 'Disney')
_add('mario|super mario', 'man with red cap and mustache', 'man with cap', 'character', 'Nintendo')
_add('luigi', 'man with green cap and mustache', 'man with cap', 'character', 'Nintendo')
_add('yoshi', 'green dinosaur', 'dinosaur', 'character', 'Nintendo')
_add('zelda|link zelda', 'elf hero with a sword', 'elf', 'character', 'Nintendo')
_add('kirby', 'pink round puffball', 'pink circle', 'character', 'Nintendo / HAL')
_add('sonic|sonic the hedgehog', 'blue hedgehog', 'hedgehog', 'character', 'Sega')
_add('spiderman|spider-man|spider man|spidey', 'masked hero in red and blue', 'superhero', 'character', 'Marvel / Disney')
_add('batman|bat man', 'masked hero in a dark cape', 'superhero', 'character', 'DC / Warner Bros.')
_add('superman|super man', 'hero with a red cape', 'superhero', 'character', 'DC / Warner Bros.')
_add('wonder woman', 'heroine with a golden tiara', 'superhero', 'character', 'DC / Warner Bros.')
_add('iron man|ironman', 'hero in red and gold armour', 'robot', 'character', 'Marvel / Disney')
_add('hulk|the hulk', 'big green strongman', 'flexed biceps', 'character', 'Marvel / Disney')
_add('captain america', 'hero with a round star shield', 'shield', 'character', 'Marvel / Disney')
_add('elsa|frozen elsa', 'snow queen with a blonde braid', 'snowflake', 'character', 'Disney')
_add('olaf', 'friendly snowman', 'snowman', 'character', 'Disney')
_add('simba|lion king', 'lion cub', 'lion', 'character', 'Disney')
_add('winnie the pooh|pooh bear|winnie', 'honey-loving teddy bear', 'teddy bear', 'character', 'Disney')
_add('buzz lightyear', 'toy space ranger', 'astronaut', 'character', 'Disney / Pixar')
_add('woody toy story', 'toy cowboy', 'cowboy hat face', 'character', 'Disney / Pixar')
_add('nemo|finding nemo', 'orange clownfish', 'tropical fish', 'character', 'Disney / Pixar')
_add('stitch|lilo and stitch', 'blue alien creature', 'alien', 'character', 'Disney')
_add('shrek', 'green ogre', 'ogre', 'character', 'DreamWorks')
_add('minion|minions', 'small yellow helper with goggles', 'yellow circle', 'character', 'Illumination / Universal')
_add('hello kitty', 'white cat with a bow', 'cat face', 'character', 'Sanrio')
_add('garfield', 'orange cat', 'cat', 'character', 'Paws Inc. / Paramount')
_add('snoopy', 'white beagle', 'dog', 'character', 'Peanuts Worldwide')
_add('spongebob|sponge bob|spongebob squarepants', 'yellow sponge', 'sponge', 'character', 'Nickelodeon / Paramount')
_add('peppa|peppa pig', 'pink pig', 'pig', 'character', 'Hasbro')
_add('homer simpson|bart simpson|simpsons|the simpsons', 'yellow cartoon person', 'person', 'character', 'Disney / 20th Television')
_add('pac-man|pacman|pac man', 'yellow round chomper', 'yellow circle', 'character', 'Bandai Namco')
_add('darth vader|vader', 'masked knight in black armour', 'knight', 'character', 'Lucasfilm / Disney')
_add('yoda|baby yoda|grogu', 'small green wise creature', 'alien', 'character', 'Lucasfilm / Disney')
_add('r2d2|r2-d2|c3po|c-3po', 'friendly robot', 'robot', 'character', 'Lucasfilm / Disney')
_add('star wars|lightsaber', 'glowing sword', 'sword', 'franchise', 'Lucasfilm / Disney')
_add('harry potter|hogwarts', 'young wizard with round glasses', 'mage', 'character', 'Warner Bros. / J.K. Rowling')
_add('gandalf', 'old wizard with grey hat', 'mage', 'character', 'Tolkien Estate / Middle-earth Enterprises')
_add('totoro|my neighbor totoro', 'big grey forest spirit', 'bear', 'character', 'Studio Ghibli')
_add('goku|dragon ball', 'martial artist with spiky hair', 'martial arts uniform', 'character', 'Bird Studio / Shueisha / Toei')
_add('naruto', 'ninja with orange outfit', 'ninja', 'character', 'Shueisha')
_add('barbie', 'fashion doll', 'doll', 'character', 'Mattel')
_add('lego|lego brick', 'toy building brick', 'brick', 'brand', 'The LEGO Group')
_add('minecraft|creeper minecraft', 'blocky green figure', 'green square', 'franchise', 'Mojang / Microsoft')
_add('among us|amogus', 'bean-shaped space crewmate', 'astronaut', 'character', 'Innersloth')
# brands / logos
_add('nike|nike logo|swoosh|nike swoosh', 'running shoe', 'running shoe', 'brand/logo', 'Nike')
_add('adidas|adidas logo', 'sports shoe', 'running shoe', 'brand/logo', 'Adidas')
_add('apple logo|apple inc logo', 'red apple', 'red apple', 'brand/logo', 'Apple')
_add('iphone|i phone|ipad|macbook|airpods', 'generic smartphone', 'mobile phone', 'brand/product', 'Apple')
_add('coca cola|coca-cola|coke logo|pepsi|pepsi logo', 'soda cup', 'cup with straw', 'brand/logo', 'The Coca-Cola Company / PepsiCo')
_add('mcdonalds|mcdonald\'s|big mac|mcdonalds logo', 'hamburger and fries', 'hamburger', 'brand/logo', "McDonald's")
_add('starbucks|starbucks logo', 'coffee cup', 'hot beverage', 'brand/logo', 'Starbucks')
_add('google logo|google', 'colourful letter G', 'globe with meridians', 'brand/logo', 'Google')
_add('windows logo|microsoft logo', 'four coloured squares', 'window', 'brand/logo', 'Microsoft')
_add('twitter logo|twitter bird', 'small blue bird', 'bird', 'brand/logo', 'X Corp')
_add('facebook logo|instagram logo|whatsapp logo|tiktok logo|youtube logo', 'speech bubble', 'speech balloon', 'brand/logo', 'Meta / ByteDance / Google')
_add('ferrari logo|prancing horse', 'black horse', 'horse', 'brand/logo', 'Ferrari')
_add('batman logo|bat signal', 'bat', 'bat', 'brand/logo', 'DC / Warner Bros.')
_add('playstation|xbox|nintendo switch', 'game controller', 'video game', 'brand/product', 'Sony / Microsoft / Nintendo')
KEYS = sorted(T, key=len, reverse=True)
# Wikidata classes (P31 / P31-P279*) treated as protected: fictional/animated/comic/video-game/anime character, Pokémon,
# superhero, media franchise, brand, logo, trademark, mascot
WD_CLASSES = {'Q95074': 'fictional character', 'Q15632617': 'fictional human', 'Q15711870': 'animated character', 'Q1114461': 'comics character',
              'Q1569167': 'video game character', 'Q15773347': 'anime character', 'Q80447738': 'anime character', 'Q3966183': 'Pokémon species', 'Q188784': 'superhero',
              'Q196600': 'media franchise', 'Q431289': 'brand', 'Q1886349': 'logo', 'Q167270': 'trademark', 'Q1426855': 'mascot', 'Q3542731': 'fictional animal character',
              'Q20643955': 'fictional character type', 'Q63975020': 'cartoon character', 'Q4167410': None}
def _cache():
    try: return json.loads(CACHE.read_text(encoding='utf-8'))
    except Exception: return {}
def _save(c):
    try: CACHE.parent.mkdir(parents=True, exist_ok=True); CACHE.write_text(json.dumps(c, indent=0), encoding='utf-8')
    except Exception: pass
def _get(url, t=5):
    from cael_unified.network import NETWORK
    return NETWORK.json(url, ttl=86400, timeout=min(t, 8))
def _classes(ids, depth=3):
    """protected class names reachable from ids via P279 (subclass of), up to depth levels."""
    seen = set(); front = [q for q in ids if q]
    for _ in range(depth + 1):
        hit = [WD_CLASSES[q] for q in front if WD_CLASSES.get(q)]
        if hit: return hit
        front = [q for q in front if q not in seen]; seen.update(front)
        if not front: return []
        e = _get('https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode(dict(action='wbgetentities', ids='|'.join(front[:50]), props='claims', format='json')))
        front = list({x['mainsnak'].get('datavalue', {}).get('value', {}).get('id') for v in e.get('entities', {}).values() for x in v.get('claims', {}).get('P279', [])} - {None})
    return []
def wikidata(word):
    """-> dict(qid, label, cls, desc) if an exact-label Wikidata entity is a protected kind, else None. Cached; network errors -> None."""
    c = _cache(); k = word.lower().strip()
    if k in c: return c[k]
    res = None
    try:
        s = _get('https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode(dict(action='wbsearchentities', search=word, language='en', limit=3, format='json')))
        hits = [h for h in s.get('search', []) if h.get('label', '').lower() == k or k in [a.lower() for a in h.get('aliases', [])] or (h.get('match', {}).get('text', '').lower() == k)]
        if hits:
            ids = '|'.join(h['id'] for h in hits[:3])
            e = _get('https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode(dict(action='wbgetentities', ids=ids, props='claims|descriptions|labels', languages='en', format='json')))
            for h in hits[:3]:
                ent = e['entities'].get(h['id'], {})
                p31 = [x['mainsnak'].get('datavalue', {}).get('value', {}).get('id') for x in ent.get('claims', {}).get('P31', [])]
                hit = _classes(p31)
                if hit:
                    res = dict(qid=h['id'], label=h.get('label', word), cls=hit[0], desc=ent.get('descriptions', {}).get('en', {}).get('value', '')); break
    except Exception:
        return None   # offline/transient: don't cache
    c[k] = res; _save(c); return res
GENERIC_WORDS = ['mouse', 'cat', 'dog', 'bear', 'rabbit', 'duck', 'bird', 'fox', 'pig', 'dragon', 'fish', 'robot', 'alien', 'ghost', 'monster',
                 'hedgehog', 'frog', 'lion', 'horse', 'turtle', 'penguin', 'unicorn', 'dinosaur', 'princess', 'prince', 'knight', 'wizard', 'ninja',
                 'girl', 'boy', 'woman', 'man', 'superhero', 'car', 'shoe', 'ball']
def check(text, known=None, use_wikidata=True):
    """Return None, or dict(original, generic, subject, kind, holder, via, text) with the protected name replaced in text."""
    low = ' ' + re.sub(r'\s+', ' ', text.lower()) + ' '
    for k in KEYS:
        m = re.search(r'(?<![a-z0-9])' + re.escape(k) + r'(?![a-z0-9])', low)
        if m:
            g, subj, kind, holder = T[k]
            if k == 'google' and not re.search(r'logo|icon', low): continue
            rest = low[:m.start()] + ' ' + low[m.end():]
            new = (low[:m.start()] + (subj if not re.search(r'(?<![a-z])' + re.escape(subj.split()[-1]) + r'(?![a-z])', rest) else '') + low[m.end():]).strip()
            new = re.sub(r'\blogo\b|\bicon\b', '', new).strip() if kind.startswith('brand') else new
            return dict(original=k, generic=g, subject=subj, kind=kind, holder=holder, via='table', text=re.sub(r'\s+', ' ', new))
    if not use_wikidata: return None
    words = [w for w in re.findall(r"[a-z][a-z'-]+", low) if len(w) > 3 and w not in ('emoji', 'emojis', 'make', 'draw', 'image', 'picture', 'please', 'with', 'create', 'show')]
    for w in words:
        if known and known(w): continue
        r = wikidata(w)
        if r:
            d = (r['desc'] + ' ' + r['label']).lower()
            gw = next((x for x in GENERIC_WORDS if re.search(r'\b' + x + r's?\b', d)), None) or 'smiling face'
            generic = gw if gw != 'smiling face' else 'smiley'
            new = re.sub(r'\s+', ' ', re.sub(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', gw, low)).strip()
            return dict(original=w, generic=generic, subject=gw, kind=r['cls'], holder=f"rights holder per Wikidata {r['qid']}", via=f"Wikidata {r['qid']} ({r['cls']})", text=new)
    return None
NICE = {'iphone': 'iPhone', 'nike logo': 'the Nike logo', 'apple logo': 'the Apple logo', 'spiderman': 'Spider-Man', 'spider man': 'Spider-Man', 'pokemon': 'Pokémon'}
def note(g):
    nm = NICE.get(g['original'], g['original'].title()); tm = any(x in g['kind'] for x in ('brand', 'logo', 'trademark'))
    return f"Made a generic {g['generic'].replace('generic ', '')} instead of {nm} ({'trademark' if tm else 'copyrighted'}, {g['holder']})."
