"""Rule-based image-request detection and prompt writing. No NN, no embeddings: regexes + hand-written vocab lists."""
import re, random, hashlib

VERB = r'(make|draw|generate|create|paint|render|sketch|produce|give me|show me|design|imagine|can you (make|draw|generate|create|paint))'
NOUN = r'(image|picture|pic|photo|photograph|portrait|drawing|painting|illustration|artwork|selfie|render)'
IMG_RE = re.compile(rf'\b{VERB}\b.{{0,40}}?\b{NOUN}s?\b|\b(draw|paint|sketch)\b\s+(me\s+)?(a|an|the|some)\b|^\s*{NOUN}\s+of\b', re.I)
CODE_VETO = re.compile(r'\b(python|javascript|html|css|canvas|matplotlib|pillow|opencv|svg|code|function|script|program|api|docker|dockerfile|image file|resize|crop|compress|jpe?g|png|bitmap|pixels? array|numpy)\b', re.I)
HOWTO_VETO = re.compile(r'^\s*(how (do|can|to|should)|what is|what are|why|explain|tips)\b', re.I)

def is_image_request(text, ca_typ=None):
    t = text.strip()
    if not IMG_RE.search(t): return False
    if CODE_VETO.search(t) or HOWTO_VETO.search(t): return False
    if ca_typ == 'code': return False
    return True

COLOURS = ['red', 'pink', 'orange', 'yellow', 'green', 'blue', 'purple', 'brown', 'black', 'white', 'grey', 'gray', 'blonde',
           'golden', 'gold', 'silver', 'teal', 'navy', 'beige', 'violet', 'crimson', 'scarlet', 'maroon', 'turquoise', 'auburn', 'ginger', 'brunette']
COL_ALIAS = {'crimson': 'red', 'scarlet': 'red', 'maroon': 'red', 'turquoise': 'teal', 'auburn': 'red', 'ginger': 'red',
             'brunette': 'brown', 'gray': 'grey', 'golden': 'gold'}
GARMENTS = ['dress', 'gown', 'shirt', 't-shirt', 'blouse', 'top', 'sweater', 'jumper', 'hoodie', 'jacket', 'coat', 'blazer', 'suit',
            'scarf', 'cardigan', 'uniform', 'kimono', 'sari', 'robe', 'turtleneck', 'tank top', 'vest']
ACCESS = ['glasses', 'sunglasses', 'hat', 'earrings', 'necklace', 'headband', 'beret', 'crown', 'flower', 'hijab', 'headscarf']
HAIRSTYLE = ['long', 'short', 'curly', 'wavy', 'straight', 'braided', 'ponytail', 'bun', 'bob', 'pixie']
EXPR = {'smiling': 'warm, cheerful', 'smile': 'warm, cheerful', 'happy': 'joyful', 'laughing': 'joyful', 'serious': 'calm, serious',
        'sad': 'melancholic', 'thoughtful': 'pensive', 'confident': 'confident', 'mysterious': 'mysterious', 'calm': 'serene'}
WOMAN = r'\b(woman|women|lady|ladies|female|girl|girlfriend|her|she|actress|queen|princess|bride|businesswoman|mother|grandmother)\b'
OTHER_SUBJ = {'man': 'a man', 'men': 'men', 'boy': 'a boy', 'guy': 'a man', 'male': 'a man', 'dog': 'a dog', 'cat': 'a cat', 'horse': 'a horse',
              'bird': 'a bird', 'car': 'a car', 'house': 'a house', 'robot': 'a robot', 'dragon': 'a dragon', 'tree': 'a tree', 'flower': None,
              'landscape': 'a landscape', 'mountain': 'mountains', 'mountains': 'mountains', 'city': 'a city', 'skyline': 'a city skyline',
              'sunset': 'a sunset', 'ocean': 'the ocean', 'sea': 'the sea', 'forest': 'a forest', 'castle': 'a castle', 'planet': 'a planet',
              'space': 'outer space', 'food': 'food', 'pizza': 'a pizza', 'logo': 'a logo', 'baby': 'a baby', 'child': 'a child', 'kid': 'a child'}
SETTINGS = {'beach': 'on a sunny beach', 'city': 'on a city street', 'street': 'on a city street', 'park': 'in a green park', 'forest': 'in a forest',
            'garden': 'in a flower garden', 'studio': 'in a photo studio', 'office': 'in a modern office', 'cafe': 'in a cosy cafe', 'café': 'in a cosy cafe',
            'library': 'in a library', 'kitchen': 'in a kitchen', 'room': 'in a room', 'bedroom': 'in a bedroom', 'snow': 'in falling snow',
            'rain': 'in the rain', 'night': 'at night in the city', 'mountains': 'in the mountains', 'desert': 'in the desert', 'stage': 'on a stage', 'pool': 'by a pool'}
STYLES = {'photo': 'photograph', 'photograph': 'photograph', 'realistic': 'photorealistic', 'painting': 'oil painting', 'oil': 'oil painting',
          'watercolor': 'watercolour', 'watercolour': 'watercolour', 'anime': 'anime illustration', 'cartoon': 'cartoon', 'sketch': 'pencil sketch',
          'pixel': 'pixel art', 'vintage': 'vintage film photo', 'cinematic': 'cinematic still'}
# blocked adult-content terms, stored as sha256 prefixes so the words are not in the source; first-7-letter prefixes are checked too
UNSAFE_H = {'12a667c9be6ff8f6', '13a465fc6616da8d', '1dba4b3306b4de8e', '2c84e0563bb7e03e', '38136d6e343860f6', '3b283e93debf035e',
            '431e876d148bdfb0', '4ae1915834846378', '6c4e44004698c129', '7f5a9ba14cb89dc2', '8c5c04391361cbf4', '98d44e13f455d916',
            'a368606514955567', 'c6603565c5159fbe', 'd84f691fc4981d9d', 'd92f4cf1e2d7e812', 'd937a9f37df4a9b5', 'e683679358a5aea3', 'ff5ae7e8d206066d'}
def _h(x): return hashlib.sha256(x.encode()).hexdigest()[:16]
def is_unsafe(text):
    return any(_h(w) in UNSAFE_H or _h(w[:7]) in UNSAFE_H for w in re.findall(r'[a-z]+', text.lower()))
EMOJI_RE = re.compile(r'\bemojis?\b', re.I)
EMOJI_ASK = re.compile(rf'\b{VERB}\b|^\s*emojis?\s+(of|for)\b|\bemojis?\s+(of|for)\b', re.I)
def is_emoji_request(text):
    t = text.strip()
    return bool(EMOJI_RE.search(t) and EMOJI_ASK.search(t) and not CODE_VETO.search(t) and not HOWTO_VETO.search(t))
def emoji_subject(text):
    t = text.strip().rstrip('.!?')
    m = re.search(r'\bemojis?\s+(?:of|for|with|showing)\s+(.+)$', t, re.I)
    if m: return m.group(1)
    m = re.search(rf'\b{VERB}\b\s+(?:me\s+)?(?:an?|the|some)?\s*(.+?)\s+emojis?\b', t, re.I)
    return m.group(m.lastindex) if m else re.sub(r'\bemojis?\b', '', t, flags=re.I)
MINOR = re.compile(r'\b(child|kid|minor|teen|teenager|schoolgirl|underage|little girl|young girl|(1[0-7]|[1-9])[- ]?(year|yr)s?[- ]?old)\b', re.I)
REAL_PERSON = re.compile(r'\b(taylor swift|celebrity|famous|president|real person|lookalike)\b', re.I)

# hand-written scene vocab (compatible choices by setting)
SCENE = {
  'default': dict(setting=['against a soft neutral backdrop', 'in a sunlit room', 'in front of a plain studio wall', 'by a window'],
                  light=['soft window light', 'diffused daylight', 'gentle studio softbox light', 'warm afternoon light']),
  'beach': dict(light=['golden-hour sunlight', 'bright midday sun with soft fill', 'warm sunset backlight']),
  'city': dict(light=['overcast city daylight', 'warm streetlight glow', 'neon reflections']), 'street': dict(light=['overcast city daylight', 'warm streetlight glow']),
  'night': dict(light=['neon signs and streetlight', 'moody low-key light']), 'studio': dict(light=['clean three-point studio light', 'single softbox key light']),
  'forest': dict(light=['dappled light through leaves', 'misty morning light']), 'park': dict(light=['dappled afternoon sun', 'soft overcast light']),
  'garden': dict(light=['bright spring daylight', 'dappled sun']), 'snow': dict(light=['cool diffuse winter light']), 'rain': dict(light=['grey rainy light, wet reflections']),
  'cafe': dict(light=['warm tungsten interior light']), 'office': dict(light=['cool fluorescent office light', 'soft window light']),
  'library': dict(light=['warm reading-lamp light']), 'stage': dict(light=['dramatic spotlight']), 'desert': dict(light=['harsh bright sun', 'warm dusk light']),
  'mountains': dict(light=['crisp alpine daylight']), 'kitchen': dict(light=['bright morning window light']), 'pool': dict(light=['bright summer sun'])}
POSES = ['looking at the camera', 'head turned slightly to the side', 'three-quarter view, glancing toward the viewer', 'chin slightly raised',
         'soft over-the-shoulder look', 'facing forward with relaxed shoulders']
MOODS = ['calm', 'serene', 'confident', 'warm', 'thoughtful', 'gentle', 'elegant']
CAMERAS = ['85mm portrait lens, shallow depth of field', '50mm lens, eye-level, natural perspective', 'close-up head-and-shoulders framing, f/2.0 bokeh',
           'medium close-up, soft background blur']

def _w(t): return re.findall(r"[a-zA-Z\-']+|\d+", t.lower())

def parse(text):
    t = text.lower(); w = _w(t); P = dict(raw=text, colours={}, garments=[], accessories=[], hair={}, expr=None, setting=None, style=None)
    P['woman'] = bool(re.search(WOMAN, t))
    P['other'] = [v or k for k, v in OTHER_SUBJ.items() if re.search(rf'\b{k}\b', t) and not (k == 'flower' and P['woman'])]
    P['unsafe'] = is_unsafe(t); P['minor'] = bool(MINOR.search(t)); P['real_person'] = bool(REAL_PERSON.search(t))
    for i, x in enumerate(w):
        if x in GARMENTS or (x == 'top' and i and w[i - 1] == 'tank'):
            g = 'tank top' if x == 'top' and i and w[i - 1] == 'tank' else x
            col = next((w[j] for j in range(i - 1, max(-1, i - 4), -1) if w[j] in COLOURS), None)
            P['garments'].append(g)
            if col: P['colours'][g] = COL_ALIAS.get(col, col)
        if x in ACCESS and x not in P['accessories']: P['accessories'].append(x)
        if x == 'hair' or x == 'haired':
            for j in range(i - 1, max(-1, i - 4), -1):
                if w[j] in COLOURS: P['hair'].setdefault('colour', COL_ALIAS.get(w[j], w[j]))
                elif w[j] in HAIRSTYLE: P['hair'].setdefault('style', []).insert(0, w[j])
        if x in ('blonde', 'brunette', 'redhead', 'ginger') and 'colour' not in P['hair']:
            P['hair']['colour'] = {'redhead': 'red', 'brunette': 'brown', 'ginger': 'red'}.get(x, x)
        if x in EXPR and not P['expr']: P['expr'] = x
        if x in SETTINGS and not P['setting'] and not (x == 'room'): P['setting'] = x
        if x in STYLES and not P['style']: P['style'] = STYLES[x]
    if P['setting'] in P['other'] or SETTINGS.get(P['setting'] or '', None) and any(o in ('mountains', 'a city', 'a forest') for o in P['other']):
        pass
    # scene words that are settings are not 'other subjects' when a woman is present
    if P['woman']:
        P['other'] = [o for o in P['other'] if o not in ('a city', 'a forest', 'mountains', 'the ocean', 'the sea', 'a sunset', 'a landscape', 'a city skyline')]
    return P

def build(P, variant=0):
    """Fill missing scene parts with compatible hand-written choices; return rich prompt, short caption, colour targets."""
    seed = int(hashlib.md5((P['raw'].lower().strip() + str(variant)).encode()).hexdigest()[:8], 16); r = random.Random(seed)
    sc = SCENE.get(P['setting'] or '', {}); df = SCENE['default']
    setting = SETTINGS[P['setting']] if P['setting'] else r.choice(df['setting'])
    light = r.choice(sc.get('light', df['light'])); pose = r.choice(POSES)
    mood = EXPR[P['expr']] if P['expr'] else r.choice(MOODS); camera = r.choice(CAMERAS); style = P['style'] or 'photograph'
    subj = 'a woman' if P['woman'] or not P['other'] else ' and '.join(P['other'])
    hair = P['hair']; hs = ' '.join(hair.get('style', [])); hc = hair.get('colour')
    hair_txt = ' '.join(x for x in [hs, hc, 'hair'] if x) if (hs or hc) else None
    garms = [f"{P['colours'].get(g, '')} {g}".strip() for g in P['garments']]
    wear = ('wearing ' + _join([_art(g) + g for g in garms])) if garms else None
    acc = ('with ' + _join(P['accessories'])) if P['accessories'] else None
    parts = [f'{style.capitalize()}, head-and-shoulders portrait of {subj}' if P['woman'] or not P['other'] else f'{style.capitalize()} of {subj}']
    if hair_txt: parts.append(f'with {hair_txt}')
    if wear: parts.append(wear)
    if acc: parts.append(acc)
    person = P['woman'] or not P['other'] or any(o in ('a man', 'men', 'a boy', 'a baby', 'a child') for o in P['other'])
    if not person: pose = r.choice(COMPOSE); camera = r.choice(['wide-angle 24mm lens', '35mm lens, eye-level', 'telephoto 200mm, compressed perspective'])
    if not person and P['setting'] and SETTINGS[P['setting']].split()[-1] in ' '.join(P['other']): setting = r.choice(['under a dramatic sky', 'in a quiet scene', 'with a soft hazy horizon'])
    parts += [setting, pose, light, f'{mood} mood', camera]
    rich = ', '.join(parts) + '.'
    cap = 'a woman'
    if garms: cap += ' in ' + _art(garms[0]) + garms[0]
    if hair_txt: cap += (' with ' if cap.count(' in ') else ' with ') + hair_txt
    if P['setting']: cap += ' ' + SETTINGS[P['setting']].replace('a sunny ', 'the ').replace('a green ', 'the ').replace('a cosy ', 'a ')
    targets = []
    if garms:
        c = P['colours'].get(P['garments'][0]);  c and targets.append(('clothing', c))
    if hc: targets.append(('hair', hc))
    return dict(rich=rich, caption=cap, targets=targets, choices=dict(setting=setting, light=light, pose=pose, mood=mood, camera=camera, style=style))

def _join(xs): return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]

PLURAL = {'glasses', 'sunglasses', 'earrings', 'shorts', 'jeans', 'trousers'}
def _art(g): return '' if g.split()[-1] in PLURAL else ('an ' if g[0] in 'aeiou' else 'a ')
COMPOSE = ['rule-of-thirds composition', 'centred composition', 'low-angle view', 'leading lines toward the subject']

