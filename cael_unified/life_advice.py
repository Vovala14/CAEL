"""Everyday life knowledge CAEL reasons from: well-established advice for common goals, written for CAEL.

Each topic lists the words that identify it and pieces of advice as (action, reason). These are facts the thinker
(thinking.py) combines with what downloaded discussions agree on; it then writes the answer itself. They are not
answers: there is no introduction, order or wording here beyond the single advice phrases.
General wellbeing advice only; nothing here replaces a doctor, lawyer or therapist, and the thinker says so where
it matters.
"""

TOPICS = [
    (('sleep',), [
        ('keep the same bedtime and wake-up time every day', 'a regular rhythm sets your body clock'),
        ('put screens away for the last hour before bed', 'bright light and scrolling keep your brain alert'),
        ('avoid caffeine after early afternoon', 'it stays in your system for many hours'),
        ('keep your bedroom dark, quiet and cool', ''),
        ('get daylight and some exercise during the day', 'both make it easier to fall asleep at night'),
        ('get up and do something calm if you cannot sleep after twenty minutes', 'lying awake in bed trains the brain to stay awake')]),
    (('stress',), [
        ('take a few slow, deep breaths when you feel tense', 'slow breathing calms the body\'s stress response'),
        ('move your body every day, even a short walk', 'exercise burns off stress hormones'),
        ('write down what is worrying you and the next small step for each', 'it turns a cloud of worry into a plan'),
        ('talk to someone you trust', ''),
        ('protect your sleep', 'tiredness makes everything feel harder'),
        ('cut back on caffeine and alcohol', 'both can make anxiety worse')]),
    (('procrastinat', 'putting off', 'motivat'), [
        ('break the task into small steps and start with the smallest one', 'starting is the hardest part'),
        ('work in short timed blocks, like 25 minutes, then take a break', ''),
        ('remove distractions such as your phone while you work', ''),
        ('decide exactly when and where you will do the task', 'a fixed plan beats waiting for motivation'),
        ('reward yourself when you finish a step', ''),
        ('be kind to yourself about past delays', 'guilt tends to cause more avoidance')]),
    (('confiden', 'self esteem', 'self-esteem'), [
        ('set small goals and notice when you reach them', 'every success is evidence that you can do it'),
        ('practise the things that make you nervous', 'skill and familiarity build confidence'),
        ('stand tall and make eye contact', ''),
        ('talk to yourself the way you would talk to a good friend', ''),
        ('prepare well for important moments', ''),
        ('spend time with people who support you', '')]),
    (('friend',), [
        ('join a club, class or group around something you enjoy', 'shared activities make conversation easy'),
        ('say yes to invitations, even small ones', ''),
        ('take the first step and suggest meeting up', 'most people are waiting for someone else to ask'),
        ('see the same people regularly', 'friendships grow from repeated time together'),
        ('ask questions and listen', 'people warm to those who are interested in them'),
        ('volunteer for a cause you care about', '')]),
    (('raise', 'pay rise', 'salary increase'), [
        ('collect evidence of your results and the value you add', 'a raise is easier to agree to when it is clearly earned'),
        ('research what your role is paid elsewhere', ''),
        ('ask your manager for a meeting about your pay, not a quick chat in passing', ''),
        ('choose a good moment, such as after a success or at review time', ''),
        ('name a specific figure or range', ''),
        ('ask what you would need to achieve if the answer is no', 'it turns a no into a plan')]),
    (('negotiat',), [
        ('research the market rate first', ''), ('let the other side name a number first if you can', ''),
        ('ask for a little more than you expect to get', 'it leaves room to meet in the middle'),
        ('negotiate the whole package, not only the main number', ''), ('stay polite and calm', ''),
        ('get the final agreement in writing', '')]),
    (('breakup', 'break up', 'heartbreak', 'get over'), [
        ('give yourself time and permission to feel sad', 'grief after a breakup is normal'),
        ('lean on friends and family', ''),
        ('limit contact with your ex and their social media for a while', 'it gives you space to heal'),
        ('look after the basics: sleep, food and exercise', ''),
        ('do things you enjoy or have always wanted to try', ''),
        ('talk to a counsellor if the sadness does not lift', '')]),
    (('houseplant', 'indoor plant', 'plants alive'), [
        ('check the soil before watering and water only when the top few centimetres are dry', 'overwatering kills more houseplants than anything'),
        ('use pots with drainage holes', 'standing water rots roots'),
        ('put each plant in the light it likes', ''),
        ('keep plants away from heaters and cold draughts', ''),
        ('feed them lightly in spring and summer', ''),
        ('wipe dust off the leaves', 'clean leaves take in more light')]),
    (('puppy', 'train my dog', 'dog training'), [
        ('reward good behaviour straight away with a treat or praise', 'dogs learn from what happens right after'),
        ('keep training sessions short and fun', ''),
        ('be consistent: everyone in the house should use the same words and rules', ''),
        ('take the puppy outside often, especially after eating and sleeping', ''),
        ('socialise your puppy gently with new people, dogs and places', ''),
        ('ignore unwanted behaviour rather than shouting', 'attention, even angry attention, can reward it')]),
    (('interview',), [
        ('research the company and the role', ''),
        ('prepare short stories that show your skills', 'specific examples are more convincing than claims'),
        ('practise answering common questions out loud', ''),
        ('prepare a few questions to ask them', ''),
        ('plan your route and arrive a little early', ''),
        ('send a short thank-you message afterwards', '')]),
    (('squeak',), [
        ('find exactly where the squeak comes from', ''),
        ('lubricate the hinge with oil or silicone spray', ''),
        ('lift the hinge pin out, clean it and grease it if oil alone does not work', ''),
        ('tighten any loose hinge screws', '')]),
    (('pack', 'packing'), [
        ('make a list before you start', ''), ('pack clothes you can mix and match', ''),
        ('roll clothes instead of folding them', 'it saves space'),
        ('keep medicine, documents and chargers in your carry-on', ''),
        ('check the weather where you are going', ''), ('leave some room for things you bring back', '')]),
    (('beach',), [
        ('pack high-factor sunscreen and reapply it after swimming', 'sunburn is the most common way to ruin a beach day'),
        ('bring swimwear and a quick-drying towel', ''), ('take a hat and sunglasses', ''),
        ('carry plenty of water', 'sun and salt make you thirsty faster'), ('wear sandals or flip-flops', 'hot sand burns feet'),
        ('keep your phone and money in a waterproof pouch', '')]),
    (('handwriting',), [
        ('slow down', 'speed is the main cause of messy writing'), ('hold the pen loosely', ''),
        ('practise the letters you find hardest', ''), ('use lined paper to keep letters an even size', ''),
        ('write a little every day', '')]),
    (('focus', 'concentrat'), [
        ('put your phone in another room', ''), ('work on one task at a time', ''),
        ('use short timed work sessions with breaks', ''), ('decide your top task for the day before you start', ''),
        ('take short movement breaks', ''), ('get enough sleep', 'tiredness is the enemy of focus')]),
    (('study', 'exam', 'revis'), [
        ('test yourself instead of rereading', 'recalling information strengthens memory'),
        ('spread your study over several days', ''), ('study in focused blocks with short breaks', ''),
        ('explain the topic out loud as if teaching someone', ''), ('sleep well, especially before the exam', '')]),
    (('public speaking', 'presentation', 'speech'), [
        ('practise out loud several times', ''), ('know your opening by heart', 'a strong start calms the nerves'),
        ('slow down and pause', ''), ('look at a few friendly faces', ''),
        ('use stories and examples', 'they are easier to remember than facts')]),
    (('save money', 'saving money', 'budget'), [
        ('track what you spend for a month', 'you cannot cut what you cannot see'),
        ('set up an automatic transfer to savings on payday', ''), ('cancel subscriptions you rarely use', ''),
        ('cook at home more often', ''), ('wait a day before unplanned purchases', ''),
        ('set a clear savings goal', '')]),
    (('lose weight', 'weight loss'), [
        ('eat mostly whole foods with plenty of vegetables and protein', ''),
        ('watch portion sizes', ''), ('cut back on sugary drinks', 'they add calories without filling you up'),
        ('move more every day', ''), ('get enough sleep', 'poor sleep increases hunger'),
        ('aim for slow, steady progress', 'it is easier to keep the weight off')]),
    (('running', 'start running', 'jogging'), [
        ('start with run-walk intervals', ''), ('go slowly enough that you can still talk', ''),
        ('increase your weekly distance gradually', 'too much too soon leads to injury'),
        ('get comfortable running shoes', ''), ('rest between runs', '')]),
    (('anxi', 'anxious', 'nervous'), [
        ('slow your breathing: breathe out longer than you breathe in', ''),
        ('notice and name the worry instead of fighting it', ''),
        ('keep moving and get outside', ''), ('limit caffeine', ''),
        ('talk to someone you trust', ''), ('see a doctor or therapist if it is affecting your daily life', '')]),
    (('lonely', 'loneliness'), [
        ('reach out to one person today, even with a short message', ''), ('join a group around an interest', ''),
        ('volunteer', 'helping others connects you with people'), ('make small talk with people you see regularly', ''),
        ('be patient with yourself', 'new connections take time')]),
    (('productiv',), [
        ('plan your day the evening before', ''), ('do the most important task first', ''),
        ('batch small tasks such as emails together', ''), ('take regular breaks', ''),
        ('say no to things that do not matter', '')]),
    (('motivat',), [
        ('start with a tiny step', 'action often comes before motivation'), ('remind yourself why the goal matters to you', ''),
        ('track your progress', ''), ('reward yourself for effort', ''), ('find someone to do it with', '')]),
    (('habit',), [
        ('start very small', ''), ('attach the new habit to something you already do', ''),
        ('make it easy and obvious', ''), ('track it every day', ''), ('do not miss twice in a row', '')]),
    (('cast iron',), [
        ('scrub with hot water and a brush or coarse salt', ''), ('dry it completely straight away', 'water causes rust'),
        ('rub in a thin layer of oil after drying', 'it keeps the seasoning'), ('avoid soaking it', '')]),
    (('bread fresh', 'keep bread'), [
        ('store bread in a bread box or paper bag at room temperature', ''), ('avoid the fridge', 'it makes bread stale faster'),
        ('freeze what you will not eat in a few days', ''), ('keep it cut side down', '')]),
]


import re as _re


def _all_topics():
    from .life_knowledge import MORE_TOPICS
    return TOPICS + MORE_TOPICS


def _matches(token, word):
    """A topic token matches a question word: the same word, a plural, or (for longer tokens) the start of it."""
    if word == token or word in (token + 's', token + 'es', token + 'ing', token + 'ed') or (token.endswith('y') and word == token[:-1] + 'ies'):
        return True                                       # "falling" matches "fall", "worried" matches "worry"...
    return len(token) >= 5 and word.startswith(token)


def topic_for(text):
    """The advice for the most specific topic a request is about, or None.
    Every word of a topic phrase must appear in the request; longer, multi-word phrases win ("wine stain" over "stain")."""
    words = _re.findall(r"[a-z0-9\-']+", text.lower())
    best, score = None, 0
    for phrases, advice in _all_topics():
        for phrase in phrases:
            tokens = phrase.split()
            positions = []
            for token in tokens:
                found = next((i for i, w in enumerate(words) if _matches(token, w)), None)
                if found is None:
                    break
                positions.append(found)
            else:
                value = sum(len(t) for t in tokens) + 4 * (len(tokens) - 1)
                if value > score:
                    best, score = advice, value
    return best
