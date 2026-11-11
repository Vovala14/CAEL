"""Authored image-brief expansion, no neural inference, images or network.

Keep the cleaned brief verbatim, then fill unspecified visual dimensions with
subject-specific details. Do not map an unfamiliar animal to a drawing proxy.
"""
import random
import re

MEDIA = [(r'water\s?colou?r', 'watercolor'), (r'oil paint', 'oil'),
         (r'pixel\s?art', 'pixel'), (r'vector|flat design|logo|icon', 'vector'),
         (r'anime|manga', 'anime'), (r'3d|cgi|blender|octane|3-d', '3d'),
         (r'pencil|charcoal|ink drawing|sketch|line art', 'sketch'),
         (r'cartoon|comic|illustration|drawing|storybook', 'illustration'),
         (r'photo(?:graph(?:ic)?)?|photorealistic|realistic|cinematic', 'photo')]
SUBJECTS = [
    ('dragon', 'creature', 'dragon dragons wyvern'), ('unicorn', 'creature', 'unicorn unicorns'),
    ('fox', 'animal', 'fox foxes'), ('cat', 'animal', 'cat cats kitten tabby'),
    ('dog', 'animal', 'dog dogs puppy corgi husky poodle'), ('wolf', 'animal', 'wolf wolves'),
    ('bear', 'animal', 'bear bears'), ('horse', 'animal', 'horse horses pony'),
    ('rabbit', 'animal', 'rabbit rabbits bunny'), ('bird', 'bird', 'bird birds owl eagle sparrow parrot penguin'),
    ('whale', 'aquatic', 'whale whales'), ('dolphin', 'aquatic', 'dolphin dolphins'),
    ('shark', 'aquatic', 'shark sharks'), ('fish', 'aquatic', 'fish goldfish trout salmon'),
    ('butterfly', 'animal', 'butterfly butterflies moth moths dragonfly'),
    ('astronaut', 'person', 'astronaut astronauts cosmonaut'), ('chef', 'person', 'chef chefs cook baker'),
    ('doctor', 'person', 'doctor doctors surgeon nurse'),
    ('engineer', 'person', 'engineer engineers mechanic technician scientist researcher'),
    ('person', 'person', 'man woman men women person people girl boy child children lady gentleman warrior knight wizard witch queen king princess prince soldier farmer sailor pirate samurai ninja monk dancer musician artist teacher student explorer cowboy grandmother grandfather athlete firefighter pilot photographer waiter waitress detective librarian architect programmer hacker'),
    ('submarine', 'vehicle', 'submarine submarines submersible'),
    ('spacecraft', 'vehicle', 'spaceship spacecraft rocket shuttle'), ('boat', 'vehicle', 'boat ship yacht canoe kayak'),
    ('car', 'vehicle', 'car cars truck motorcycle bike bicycle bus tractor'), ('train', 'vehicle', 'train trains locomotive'),
    ('aircraft', 'vehicle', 'airplane aeroplane aircraft helicopter'),
    ('cake', 'food', 'cake cakes cupcake pastry'), ('drink', 'food', 'coffee tea'), ('food', 'food', 'food pizza burger sandwich soup salad bread sushi steak chocolate'),
    ('flower', 'plant', 'flower flowers rose roses tulip orchid sunflower daisy'),
    ('tree', 'plant', 'tree trees oak pine palm birch maple'),
    ('castle', 'building', 'castle cathedral temple palace church'),
    ('lighthouse', 'building', 'lighthouse tower skyscraper house cabin cottage building'),
    ('landscape', 'place', 'landscape city skyline forest mountains mountain valley ocean beach village island desert planet space waterfall volcano'),
    ('logo', 'graphic', 'logo logos icon icons emblem badge'), ('robot', 'object', 'robot robots android'),
    ('snowman', 'object', 'snowman snowmen'),
    ('object', 'object', 'phone camera watch shoe bag bottle chair table book mug teapot lamp ring necklace dress vase sculpture'),
]
INDEX = [(word, topic, kind) for topic, kind, words in SUBJECTS for word in words.split()]
INDOOR = r'\b(?:room|kitchen|hospital|garage|cafe|café|library|office|studio|laboratory|workshop|indoors|interior|inside|window)\b'
OUTDOOR = r'\b(?:outside|outdoors|forest|meadow|park|street|beach|mountain|valley|garden|coast|road|desert|field|shore|harbou?r|sky|rooftop)\b'
SETTING = r'\b(?:in|on|at|by|near|under|inside|through|across|over|beneath|behind|beside|between|against|above|atop|outside|within)\s+(?!focus\b|detail\b|black\b|white\b)\w|\b(?:underwater|submerged|indoors|outdoors)\b'
LIGHT = r'\b(?:soft|hard|natural|ambient|diffused|studio|dramatic|practical|neon|volumetric)\s+light(?:ing)?\b|\b(?:backlit|rim[- ]light|candlelight|moonlight|sunlight|silhouette)\b'
FRAMING = r'\b(?:close[- ]?up|portrait|full[- ]body|wide[- ]shot|wide[- ]angle|wide shot|wide angle|aerial|top[- ]down|from above|macro|side view|low[- ]angle|centered|centred|symmetrical)\b'
ACTION = r'\b(?:running|walking|cooking|working|riding|playing|dancing|repairing|operating|holding)\b'
MONO = r'\b(?:black[- ]and[- ]white|monochrome|grayscale|greyscale|no colou?r)\b'
REQUEST = (r'(?i)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+(?:please\s+)?)?'
           r'(?:(?:make|create|draw|generate|paint|render|design|produce|show|give)(?:\s+me)?'
           r'|i\s*(?:want|need|would like|\'d like|wish)(?:\s+to\s+(?:see|have|make|get))?)\s+')
PREFIX = r'(?i)^(?:(?:an?|the|some)\s+)?(?:ai\s+)?(?:image|picture|photo|photograph|drawing|illustration|painting|artwork|pic|render)s?\s+(?:of|showing|for)\s+'
NOT_AN_IDEA = r'(?i)^(?:hi|hello|hey|thanks|thank you|ok|okay|yes|no|test|help|\?+)\W*$'

# Visual themes named in the brief, each with details, light and colours that belong to it: what the brief is about
# shapes what gets added, instead of the same generic tail for every person or object.
THEMES = [
    (r'cyber\s?punk|neon|futuristic city|blade runner|synthwave', ['neon signage reflected in rain-slick pavement', 'holographic advertisements and dense overhead cables', 'steam drifting through pools of coloured light'],
     'mixed neon lighting with deep shadows', 'a magenta, cyan and deep blue palette'),
    (r'steampunk', ['brass gears, rivets and copper pipework', 'ornate Victorian machinery'], 'warm gas-lamp light', 'a brass, copper and sepia palette'),
    (r'fantasy|magic(?:al)?|enchanted|wizard|witch|elf|elves|fairy|fae|mythical|knights?|dragons?|sorcer\w*', ['glowing motes of magic drifting in the air', 'ancient carved stone and twisting roots', 'subtle runes glowing faintly'],
     'ethereal glowing light', 'rich jewel-toned colours'),
    (r'horror|creepy|haunted|eerie|spooky|sinister|ghost', ['long shadows and an unsettling stillness', 'peeling textures and faint drifting fog'], 'dim low-key lighting', 'a desaturated palette with sickly greens'),
    (r'co[sz]y|hygge|snug', ['soft knitted textures and warm wooden surfaces', 'a steaming mug and gently glowing lamps'], 'warm lamp light', 'a warm amber and cream palette'),
    (r'vintage|retro|old[- ]fashioned|19[0-9]0s|film photo', ['period-accurate clothing and props', 'subtle film grain'], '', 'faded warm vintage tones'),
    (r'forest|woods|woodland|jungle|rainforest', ['shafts of light through the canopy', 'moss-covered roots and ferns in the foreground', 'dappled light on the forest floor'], '', 'deep greens and earthy browns'),
    (r'beach|seaside|coast(?:al|line)?|shore', ['gentle surf and wet-sand reflections', 'sea spray catching the light'], '', 'turquoise, sand and soft blue tones'),
    (r'underwater|coral|reef|ocean floor|seabed', ['drifting particles and rippling caustic light', 'coral and small schools of fish'], '', 'deep teal and aquamarine tones'),
    (r'winter|snow(?:y|ing)?|blizzard|frost(?:y)?|icy', ['fresh snow on every surface', 'visible breath in the cold air', 'frost on the edges of things'], 'cool winter light', 'cool whites and pale blues'),
    (r'autumn|fall foliage', ['drifting golden leaves', 'rich autumn foliage'], 'low golden autumn light', 'rust, amber and gold tones'),
    (r'spring|blossom(?:s|ing)?|cherry tree', ['blossoms and fresh green growth'], 'fresh soft daylight', 'soft pastel tones'),
    (r'rain(?:y|ing)?|storm(?:y)?|thunder', ['rain streaks and puddle reflections', 'dark clouds gathering overhead'], 'moody overcast light', 'muted slate and silver tones'),
    (r'desert|dunes?|sahara', ['wind-carved dunes and shimmering heat haze'], 'harsh bright sunlight', 'warm ochre and sand tones'),
    (r'mountains?|alpine|peaks?', ['layered ridgelines fading into haze'], '', 'cool blue mountain tones'),
    (r'space|galaxy|nebula|cosmic|stars|planet', ['a star-filled sky and a glowing nebula', 'distant planets suspended in the dark'], '', 'deep violet and electric blue'),
    (r'city|street|urban|alley|market|stall|downtown|skyline', ['bustling street details and layered signage', 'passers-by softly blurred in the background'], '', ''),
    (r'sunset|golden hour|dusk', ['long warm shadows'], '', 'warm orange and pink sky tones'),
    (r'night|midnight|moon(?:lit|light)?', ['scattered pools of light in the darkness'], '', 'deep blues with warm highlights'),
]
MOODS = [(r'happy|joyful|cheerful|playful|fun', 'a joyful, lively mood'), (r'sad|melanchol\w*|lonely|grief|somber|sombre', 'a quiet, melancholic mood'),
         (r'calm|peaceful|serene|tranquil|relaxing', 'a calm, serene atmosphere'), (r'epic|dramatic|heroic|powerful', 'an epic, dramatic atmosphere'),
         (r'myster\w*|secret|hidden', 'a mysterious atmosphere'), (r'romantic|love', 'a tender, romantic mood'), (r'scary|terrifying|dark', 'a tense, foreboding mood')]
SCENE_NOUNS = r'\b(?:street|stall|market|alley|city|town|village|shop|bar|pub|restaurant|cafe|café|kitchen|bedroom|forest|beach|desert|jungle|garden|park|field|room|studio|stage|library|office|lake|river)\b'
PERSON_DETAILS = ['natural skin texture and catchlights in the eyes', 'a relaxed, candid pose', 'an expressive face and clear clothing folds',
                  'windswept hair and a confident expression', 'a gentle expression and soft fabric textures', 'a thoughtful gaze and finely detailed clothing',
                  'expressive hands and a natural stance', 'subtle freckles and realistic hair strands']


def themes_in(idea):
    return [t for t in THEMES if re.search(r'\b(?:' + t[0] + r')\b', idea, re.I)][:2]


def clean_brief(brief):
    text = re.sub(REQUEST, '', brief.strip(), count=1)
    if re.fullmatch(r'(?i)(?:(?:an?|the)\s+)?(?:image|picture|photo|drawing|illustration|painting)(?:\s+(?:of|showing|for))?', text):
        return ''
    text = re.sub(PREFIX, '', text, count=1).strip().rstrip('.!?')
    return '' if re.match(NOT_AN_IDEA, text) else text


EDIT = (r'(?i)^\s*(?:(?:ok(?:ay)?|now|and|but|also|then|great|nice|cool|good)[,!.]?\s+)*'
        r'(?:make (?:it|her|him|them|the \w+)|turn (?:it|her|him|them) into|change (?:it|the \w+)(?: to)?|put (?:it|her|him|them)|give (?:it|her|him|them)|'
        r'add|remove|without|with|no|more|less|instead|same(?: but)?|at night|at sunset|at dawn|in (?:the )?(?:rain|snow|winter|summer|autumn|spring)|'
        r'in (?:an? )?[\w-]+ style|as (?:an? )?[\w-]+|older|younger|darker|brighter|lighter|bigger|smaller|happier|sadder|closer|wider|from above|close[- ]?up)\b')
LEAD = r'(?i)^\s*(?:now|but|instead|then|ok(?:ay)?,? now)\b'


def is_edit(text):
    """'make it at night', 'now in watercolor', 'older and smiling': a change to the last scene, not a new idea."""
    if re.match(EDIT, text) or re.match(LEAD, text):
        return True
    media = '|'.join(pattern for pattern, _ in MEDIA)
    return bool(re.match(r'(?i)^\s*(?:in|as)\s+(?:an?\s+)?(?:' + media + r')\b', text))


def merge_edit(previous, edit):
    """'a woman with red hair in a forest' + 'make it at night' -> 'a woman with red hair in a forest at night';
    + 'now in watercolor' -> the same scene in watercolour, with the earlier medium dropped."""
    change = re.sub(r'(?i)^\s*(?:(?:ok(?:ay)?|now|and|but|also|then|great|nice|cool|good)[,!.]?\s+)*', '', edit).strip().rstrip('.!?')
    change = re.sub(r'(?i)^(?:make (?:it|her|him|them)|turn (?:it|her|him|them) into|change it to|same but)\s*', '', change).strip()
    change = re.sub(r'(?i)[,\s]+instead$|^instead[,\s]+', '', change).strip()
    base = previous
    if any(re.search(r'\b(?:' + pattern + r')\b', change, re.I) for pattern, _ in MEDIA):
        for pattern, _ in MEDIA:          # a new medium replaces the old one rather than piling up
            base = re.sub(r'(?i),?\s*\b(?:in (?:an? )?|as (?:an? )?)?(?:' + pattern + r')(?:\s+(?:style|painting|art|drawing|photo))?\b', '', base).strip(' ,')
    removed = re.match(r'(?i)remove (?:the )?(.+)', change)
    if removed:
        thing = removed[1].strip()
        if re.search(r'\b' + re.escape(thing) + r'\b', base, re.I):
            parts = [p for p in base.split(', ')]
            kept = [parts[0]] + [p for p in parts[1:] if not re.search(r'\b' + re.escape(thing) + r'\b', p, re.I)]
            if len(kept) < len(parts):
                return ', '.join(kept)          # the whole added phrase goes ("with a dragon behind him")
            return re.sub(r'(?i)\s*(?:with |and )?(?:an? |the )?\b' + re.escape(thing) + r'\b', '', base).strip(' ,')
        change = 'without ' + thing
    change = re.sub(r'(?i)^add\s+', 'with ', change)
    return f'{base}, {change}' if change else base


def subject_part(text):
    return re.split(r'[;\n]|\s+(?:in|on|at|by|near|under|inside|through|across|over|beneath|behind|beside|between|against|above|atop|outside|with|without)\s+', text, 1, flags=re.I)[0]


def subject(text):
    head = subject_part(text).lower()
    matches = [(m.start(), -len(word), topic, kind) for word, topic, kind in INDEX
               if (m := re.search(r'\b' + re.escape(word) + r'\b', head))]
    return min(matches)[2:] if matches else ('subject', 'generic')


def subject_kind(text):
    return subject(text)[1]


def scene_context(text, topic):
    if re.search(r'\b(?:underwater|under water|submerged|beneath (?:the )?(?:sea|ice)|seabed|ocean floor)\b', text, re.I): return 'underwater'
    if re.search(r'\b(?:space|orbit|mars|moon|lunar|asteroid)\b', text, re.I): return 'space'
    if re.search(r'\b(?:cave|cavern)\b', text, re.I): return 'cave'
    if re.search(OUTDOOR, text, re.I): return 'outdoor'
    if re.search(INDOOR, text, re.I) or re.search(r'\b(?:plain|white|black|transparent|neutral) background\b', text, re.I): return 'indoor'
    return 'underwater' if topic in ('whale', 'fish', 'shark', 'dolphin', 'submarine') else 'outdoor'


def subject_detail(topic, kind, style, rng):
    details = {
        'dragon': ['layered scales following the body contours', 'a clearly defined head and tail silhouette', 'overlapping scales with subtle tonal variation'],
        'unicorn': ['a flowing mane and a clearly defined spiral horn'],
        'butterfly': ['delicate wing patterns and clearly defined antennae'],
        'astronaut': ['layered spacesuit panels, readable equipment shapes and restrained visor reflections'],
        'chef': ['clear hand gestures and tactile detail in the cooking tools'],
        'doctor': ['an attentive expression and clearly rendered professional clothing'],
        'engineer': ['precise tool shapes and visible fabric and equipment textures'],
        'submarine': ['a streamlined pressure hull, visible panel seams and subtle metal reflections'],
        'spacecraft': ['layered hull panels and clearly defined engine structures'],
        'boat': ['a clearly defined hull and restrained surface reflections'],
        'flower': ['layered petal edges, delicate leaf veins and a defined flower centre'],
        'tree': ['branching structure, varied leaf clusters and textured bark'],
        'robot': ['articulated mechanical joints and layered manufactured panels'],
        'snowman': ['rounded snow forms and subtle granular surface texture'],
        'drink': ['liquid surface detail and controlled highlights on the vessel'],
    }
    if topic in ('fox', 'cat', 'dog', 'wolf', 'bear', 'rabbit', 'horse'):
        return rng.choice(['directional coat detail and an expressive gaze', 'distinctive facial markings and a readable silhouette', 'fine coat texture following the body contours'])
    general = {
        'person': PERSON_DETAILS, 'animal': ['a readable silhouette and coherent natural features'],
        'bird': ['layered feather patterns and a clearly defined beak'], 'aquatic': ['a streamlined silhouette and subtle surface texture'],
        'vehicle': ['coherent body proportions, defined mechanical details and controlled reflections'],
        'food': ['distinct ingredient textures and a clear appetising focal point'],
        'building': ['readable architectural proportions, layered facades and material detail'],
        'place': ['a distinct foreground, layered middle distance and an atmospheric horizon'],
        'graphic': ['a recognisable silhouette, deliberate spacing and clean contour geometry'],
    }
    return rng.choice(details.get(topic, general.get(kind, ['precise material textures and readable edge contours', 'a clear silhouette and carefully separated material surfaces', 'subtle tonal variation and a defined focal point'])))


def choose_setting(topic, kind, rng):
    special = {'whale': ['in open ocean water', 'above a softly receding seabed'], 'submarine': ['beneath the ocean surface', 'in deep blue water'],
               'astronaut': ['on a rocky lunar plain', 'inside a space-station module'], 'spacecraft': ['in deep space', 'above a distant planetary horizon'],
               'boat': ['on calm coastal water', 'beside a sheltered harbour'], 'chef': ['in a working kitchen', 'beside a kitchen preparation counter'],
               'doctor': ['in a hospital consultation room', 'in a clinical workspace'], 'engineer': ['in an organised workshop', 'beside a workbench'],
               'dragon': ['in a rocky fantasy landscape', 'beside an ancient stone ruin'], 'snowman': ['in a snowy garden', 'in a winter park'],
               'train': ['on railway tracks', 'at a spacious railway platform'], 'aircraft': ['on an airfield', 'beside an open hangar'],
               'drink': ['on a simple cafe serving surface', 'against a restrained kitchen backdrop']}
    general = {'animal': ['in a natural woodland clearing', 'in a quiet garden'], 'bird': ['against a receding natural background', 'with an unobtrusive natural backdrop'],
               'aquatic': ['underwater with a softly receding background', 'beneath the water surface'],
               'person': ['against a restrained studio backdrop', 'beside an interior wall'], 'vehicle': ['in a spacious vehicle studio', 'on an open road'],
               'food': ['on a simple serving surface', 'on a ceramic plate'], 'plant': ['in a botanical setting', 'against separated foliage'],
               'building': ['beside a restrained open foreground', 'with a clearly defined surrounding landscape'],
               'object': ['against a neutral studio backdrop', 'on a simple display surface'], 'creature': ['in a quiet enchanted landscape', 'against an atmospheric fantasy backdrop'],
               'generic': ['against a restrained background', 'in a visually simple setting']}
    return rng.choice(special.get(topic, general.get(kind, [''])))


def choose_light(idea, context, rng):
    if re.search(LIGHT, idea, re.I): return ''
    night = re.search(r'\b(?:night|midnight|dusk|twilight|blue hour)\b', idea, re.I)
    if context == 'space': return 'directional illumination with deep shadow separation'
    if context == 'underwater': return 'soft underwater ambient light' if night else 'diffused underwater light with gentle depth falloff'
    if context == 'cave': return 'low ambient cave light with restrained edge highlights'
    if context == 'indoor': return 'subdued interior practical lighting with controlled shadows' if night else rng.choice(['soft diffused interior light', 'controlled studio illumination', 'gentle interior ambient light'])
    if night: return 'low ambient evening light with readable shadow detail'
    if re.search(r'\b(?:overcast|cloudy|rain|rainy|raining|fog|foggy|mist|misty|snow|snowy|snowing|storm)\b', idea, re.I): return 'soft overcast light with muted highlights'
    if re.search(r'\b(?:sunrise|dawn)\b', idea, re.I): return 'low warm dawn light with long soft shadows'
    if re.search(r'\b(?:sunset|golden hour)\b', idea, re.I): return 'warm low-angle light with gentle shadow transitions'
    return rng.choice(['soft natural light with restrained highlights', 'gentle diffused daylight', 'balanced daylight with clear shadow detail'])


def framing(kind, idea, rng):
    if re.search(FRAMING, idea, re.I): return ''
    if kind in ('place', 'building'): return rng.choice(['a wide establishing composition', 'an expansive view with foreground depth', 'a wide view with balanced visual layers'])
    if kind == 'graphic': return 'a balanced layout with clear negative space'
    if kind == 'person' and re.search(ACTION, idea, re.I): return rng.choice(['a medium environmental composition showing the action', 'an eye-level view keeping the action visible'])
    options = {'person': ['an eye-level portrait composition', 'a waist-up composition'], 'vehicle': ['a three-quarter view', 'a low viewpoint emphasising the silhouette'],
               'food': ['a carefully framed close-up', 'a slightly elevated tabletop view'], 'plant': ['a detailed botanical close-up', 'an eye-level botanical view'],
               'creature': ['a full-body composition with a readable silhouette', 'an environmental view with clear subject separation']}
    return rng.choice(options.get(kind, ['an eye-level composition', 'a balanced three-quarter composition', 'a clear composition with breathing room around the subject']))


def finish(style, kind, idea, rng, palette=''):
    if style == 'photo':
        parts = [rng.choice(['photographic rendering', 'photorealistic detail', 'a natural photographic look'])]
        if not re.search(r'\b\d{1,3}\s?mm\b', idea, re.I):
            parts.append(rng.choice(['a wide-angle lens', 'deep focus across the scene']) if kind in ('place', 'building')
                         else rng.choice(['a natural perspective', 'shallow depth of field', 'an 85mm portrait lens look' if kind == 'person' else 'a 50mm lens look']))
        parts.append(rng.choice(['careful exposure and realistic material response', 'controlled contrast and fine material detail', 'clear tonal separation and realistic surface detail']))
        if not re.search(MONO, idea, re.I): parts.append(palette or rng.choice(['a cohesive colour palette', 'natural, true-to-life colours', 'a harmonious muted palette']))
        return ', '.join(parts)
    choices = {
        'watercolor': ['transparent pigment washes and visible paper grain', 'soft pigment transitions and delicate dry-brush edges', 'layered washes and subtle paper texture'],
        'oil': ['layered brushwork and visible canvas texture', 'controlled impasto and rich tonal layering', 'expressive brushwork with carefully shaped edges'],
        'pixel': ['crisp pixel clusters and a consistent pixel grid', 'deliberate pixel placement and readable small-scale shapes', 'clean pixel silhouettes with controlled dithering'],
        'vector': ['clean vector paths and consistent shape language', 'precise contours and flat separated shapes', 'restrained vector geometry and clear edge definition'],
        'anime': ['clean line work and controlled cel shading', 'expressive drawn shapes and coherent cel-shaded lighting', 'precise line art with clean shadow shapes'],
        '3d': ['coherent geometry and physically based material response', 'carefully modelled surfaces and controlled global illumination', 'clean geometry with subtle material roughness'],
        'sketch': ['varied line weight and deliberate hatching', 'expressive strokes with controlled value groups', 'clear line hierarchy and tactile drawn marks'],
        'illustration': ['readable shape design and layered drawn detail', 'expressive contours and controlled tonal grouping', 'coherent drawn forms with a strong focal hierarchy'],
        'fantasy': ['layered painterly detail and atmospheric depth', 'coherent fantasy design with shaped silhouettes', 'painterly fantasy rendering with subtle atmospheric depth']}
    tail = style.replace('3d', '3D') + ' style, ' + rng.choice(choices[style])
    return tail + (', ' + palette if palette and not re.search(MONO, idea, re.I) else '')


def compose(brief, rng):
    idea = clean_brief(brief)
    if not idea: raise ValueError('Describe the subject or scene you want in the image prompt.')
    topic, kind = subject(idea)
    style = next((key for pattern, key in MEDIA if re.search(r'\b(?:' + pattern + r')\b', brief, re.I)), 'fantasy' if kind == 'creature' else 'photo')
    if style == 'photo' and re.match(r'(?i)\s*(?:draw|paint)\b', brief): style = 'illustration'
    found = themes_in(idea)
    additions = [subject_detail(topic, kind, style, rng)]
    for _, details, _, _ in found:          # details that belong to what the brief is about (neon for cyberpunk, canopy light for a forest)
        additions.append(rng.choice(details))
    mood = next((text for pattern, text in MOODS if re.search(r'\b(?:' + pattern + r')\b', idea, re.I)), '')
    if mood: additions.append(mood)
    context = scene_context(idea, topic)
    if (not re.search(SETTING, idea, re.I) and not re.search(SCENE_NOUNS, idea, re.I) and not found
            and not re.search(r'\bbackground\b|\bno props\b', idea, re.I) and kind not in ('place', 'graphic')):
        setting = choose_setting(topic, kind, rng)
        additions.append(setting)
        context = scene_context(setting, topic)
    if kind != 'graphic':
        themed = next((light for _, _, light, _ in found if light), '')
        # Place, weather and time of day decide the light first (a cave, snow, night); a theme's light fills in otherwise.
        cued = context in ('cave', 'underwater', 'space') or re.search(
            r'\b(?:night|midnight|dusk|twilight|blue hour|overcast|cloudy|rain|rainy|raining|fog|foggy|mist|misty|snow|snowy|snowing|storm|sunrise|dawn|sunset|golden hour)\b', idea, re.I)
        additions.append('' if re.search(LIGHT, idea, re.I) else choose_light(idea, context, rng) if cued or not themed else themed)
    palette = next((colours for _, _, _, colours in reversed(found) if colours), '')   # the later, more specific theme ("snowy" over "forest")
    additions += [framing(kind, idea, rng), finish(style, kind, idea, rng, palette)]
    # Explicit exclusions constrain additions too, not only the copied brief.
    exclusions = []
    for term in re.findall(r'(?i)\b(?:no|without)\s+([a-z]+)', idea):
        stem = term.rstrip('s')
        exclusions.append(r'\b' + re.escape(stem) + r'\w*\b')
    if re.search(r'\b(?:hairless|bald|no fur|without fur)\b', idea, re.I): exclusions += [r'\b(?:coat|fur|hair)\b']
    if re.search(r'\bfaceless\b', idea, re.I): exclusions += [r'\b(?:face|expression|gaze|eyes)\b']
    additions = [value for value in additions if value and not any(re.search(pattern, value, re.I) for pattern in exclusions)]
    avoid = ['unintentional blur', 'incoherent geometry', 'unwanted compression artifacts']
    if kind in ('person', 'animal', 'bird', 'aquatic', 'creature'): avoid += ['unintended anatomy distortions', 'unrequested duplicate limbs']
    if not re.search(r'\b(?:text|lettering|logo|typography|watermark)\b', idea, re.I): avoid.append('unrequested lettering or watermarks')
    additions = [value for value in additions if value]
    return ', '.join([idea] + additions), dict(subject_kind=kind, subject=topic, style=style, setting_context=context, additions=additions, avoid=', '.join(avoid))


def image_prompts(brief, count=1, seed=0):
    if type(count) is not int or not 1 <= count <= 5: raise ValueError('Choose between one and five prompt variants.')
    out, notes = [], None
    for i in range(count):
        for attempt in range(100):
            prompt, notes = compose(brief, random.Random(f'{seed}:{i}:{attempt}:{brief}'))
            if prompt not in out:
                out.append(prompt)
                break
        else: raise ValueError('Please loosen one visual constraint to allow more distinct prompt variants.')
    return out, notes
