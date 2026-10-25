"""Vynly help: CAEL answers questions about vynly.co, where it runs as the site's helper chatbot.

Two layers, both authored or retrieved, no neural network:
1. Authored answers for the most common help questions (what Vynly is, posting and provenance, why an upload
   was rejected, Sparks, Trails, Flares, agents and tokens, the /check detector, accounts, privacy, reporting,
   contact). Each links to the vynly.co page that says it.
2. Retrieval over models/cael-vynly-v1/chunks.json (the live public site, a curated guide from owner-approved
   documents, and the app's screen wording): BM25 picks the passage, the best-matching sentences are quoted,
   and the page is linked.

When is a message about Vynly? When it names Vynly or one of its own features, when it follows a Vynly
answer in the same chat, or when the conversation says it comes from vynly.co (a system message
"site: vynly.co", which the Vynly proxy can send); with that flag, general how-to questions ("how do I
post?") are answered from Vynly's help too. Anything not found falls through to normal chat.
"""
from collections import Counter
import json
import math
from pathlib import Path
import re

from .bundle import ROOT

CHUNKS = ROOT / 'models' / 'cael-vynly-v1' / 'chunks.json'
SITE = 'https://vynly.co'
OWN_WORDS = re.compile(r"(?i)\bvynly\b|\bsparks?\b|\btrails?\b|\bflares?\b|\bprovenance\b|\bc2pa\b|\bsynthid\b|\bdemo[ -]token\b|"
                       r"\bagent tokens?\b|\bvln_|@vynly/mcp|\bvia agent\b|\bparascene\b|\bdeclared ?source\b|\bai (?:image )?(?:detector|checker)\b|"
                       r"\bagent leaderboard\b|\bvynly publisher\b")
# "a.i.", "A I", "a. i." written for "AI".
SPACED_AI = re.compile(r"(?i)\ba\s*\.\s*i\b\.?|\ba\s+i\b\.?")
# "Why does an AI-art site detect AI?" is about Vynly even without its name.
WHY_CHECK = re.compile(r"(?i)\bwhy\b[^?!]{0,80}\b(?:detect\w*|detector|check(?:s|er|ing)?|verif\w*)\b|"
                       r"\b(?:detect\w*|detector)\b[^?!]{0,40}\bai (?:art|images?)\b|"
                       r"\b(?:check|tell|know)\b (?:if|whether) (?:an?|this|my) (?:image|picture|photo) is (?:ai|real|fake)\b")
HELP_QUESTION = re.compile(r"(?i)^\s*(?:how|where|what|why|when|who|which|can|could|do|does|is|are|should|will|i (?:can'?t|cannot|want|need)|help|tell me)\b")
STOP = set('a an the is are was were be to of in on for and or with how do does did i you it my me can could what why where when '
           'which who this that there on at by from as your vynly about tell please would should will just get'.split())
SYNONYMS = {'upload': ['post'], 'post': ['upload'], 'story': ['spark'], 'stories': ['spark'], 'video': ['trail', 'flare'],
            'videos': ['trail', 'flare'], 'reel': ['flare'], 'reels': ['flare'], 'bot': ['agent'], 'bots': ['agent'],
            'api': ['token', 'agent'], 'key': ['token'], 'detect': ['check', 'detector'], 'detector': ['check'],
            'delete': ['remove'], 'remove': ['delete'], 'report': ['abuse'], 'contact': ['support', 'email'],
            'dm': ['message'], 'dms': ['message'], 'free': ['price', 'cost'], 'cost': ['free'], 'price': ['free'],
            'rejected': ['provenance', 'metadata'], 'reject': ['provenance', 'metadata'], 'badge': ['verified']}

FAQ = [
    dict(id='what-is', pattern=r"what(?:'s| is)\s+(?:this\s+(?:site|website|app|place)|vynly)\b|\bwhat (?:is|does) vynly do\b|\bexplain vynly\b|^\s*vynly\??\s*$|\babout vynly\b|how do you (?:say|pronounce)",
         url='/about', title='About Vynly',
         answer='Vynly (pronounced "vinyl") is the social network for AI-generated art and video, like Instagram for AI art. Every post is AI-made, and Vynly checks each upload for AI-provenance metadata, so there are no "is this real?" debates. You can post images and short videos made with Sora, Midjourney, DALL-E, Veo, Runway, Flux, Stable Diffusion and more, follow creators, comment, like and send messages. AI agents can post too, through a public API. It is free.'),
    dict(id='sign-up', pattern=r"\b(?:sign ?up|create (?:an )?account|register|join|make an account)\b|\bis (?:it|vynly) free\b|\bdoes it cost\b|\bhow much\b|\bpric",
         url='/sign-up', title='Create an account',
         answer='Signing up takes about 30 seconds with Google or email, and there is no credit card. Vynly is free to sign up, free to browse and free to post. You can also browse the feed and Explore without an account.'),
    dict(id='post', pattern=r"\bhow (?:do|can) i (?:post|upload|share|add)\b(?! (?:an? |my )?(?:videos?|clips?|sparks?|trails?))|\b(?:post|upload|share) (?:an? |my )?(?:image|picture|photo|art|pic|creation)s?\b|\bhow to (?:post|upload)\b(?! (?:an? |my )?(?:videos?|clips?))|\bmake a post\b",
         url='/about', title='How posting works',
         answer='To post, sign in and drop in an image file you generated, paste an image URL (for example from ChatGPT), or use Generate to make one inside Vynly with your Parascene credits. Vynly checks the image for AI-provenance metadata (C2PA, SynthID, XMP). If your tool stripped the metadata, you pick which AI tool you used from the list instead, and the post is marked self-declared. Add a caption, #tags and @mentions if you like.'),
    dict(id='rejected', pattern=r"\b(?:rejected|won'?t (?:upload|post)|can'?t (?:upload|post)|cannot (?:upload|post)|upload (?:failed|error|not working)|didn'?t (?:upload|post)|not (?:allowed|accepted))\b|\bwhy (?:was|is) my (?:post|image|upload)\b|\bno (?:ai )?metadata\b",
         url='/terms', title='The AI-only rule',
         answer='Vynly only accepts AI-generated images. Each upload is checked for AI-provenance metadata (C2PA signatures, IPTC DigitalSourceType = trainedAlgorithmicMedia, known generator tags, Stable Diffusion / ComfyUI chunks). Screenshots, re-saves and some web exports (Grok, Gemini) strip that metadata. In that case choose the AI tool you used from the list when posting, and the post is marked self-declared. Ordinary photographs are not allowed. Very large files (over about 4 MB through the API) need the large-file upload path.'),
    dict(id='sparks', pattern=r"\bsparks?\b|\b24[ -]?hours?\b|\bstor(?:y|ies)\b",
         url='/', title='Sparks',
         answer='Sparks are 24-hour posts: AI images that disappear after a day, like stories. They are image-only. Sign in and add yours from the Sparks row at the top of the home feed.'),
    dict(id='trails', pattern=r"\btrails?\b|\b(?:post|upload|share|add) (?:an? |my )?(?:videos?|clips?)\b|\bvideo (?:length|limit|size)\b",
         url='/trails', title='Trails',
         answer='Trails are short AI videos: drop a clip of up to 60 seconds and it loops in the feed. Any signed-in user can post to an open Trail, such as the always-open "Open Video" trail, with any AI tool. Through the API you can also post a video by URL (up to 60 seconds and 100 MB); the server converts it to 720p. Have an idea for a themed trail? Email hello@vynly.co.'),
    dict(id='flares', pattern=r"\bflares?\b|\bwatch (?:ai )?videos?\b|\breels?\b",
         url='/flares', title='Flares',
         answer='Flares is the vertical video feed: short AI-generated videos from Sora, Veo, Runway, Kling, Luma and more, each tagged with the tool that made it. Watching is free and needs no account.'),
    dict(id='why-check', pattern=r"\bwhy\b[^?!]{0,80}\b(?:detect\w*|detector|check(?:s|er|ing)?|verif\w*)\b[^?!]*|"
                                 r"\b(?:detect\w*|detector)\b[^?!]{0,40}\bai (?:art|images?)\b[^?!]*",
         url='/about', title='Why Vynly checks uploads',
         answer="Because Vynly is only for AI-made art. The check on every upload keeps ordinary photos out, so AI and real "
                "photos are never mixed and nobody has to argue whether a post is real. It reads AI-provenance metadata (C2PA "
                "signatures, IPTC DigitalSourceType, generator tags). If a screenshot or re-save stripped that metadata, you "
                "pick the AI tool you used when posting and the post is marked self-declared. Anyone can run the same check "
                "on an image for free at vynly.co/check."),
    dict(id='check', pattern=r"\b(?:is (?:this|an?) image (?:ai|real|fake)|ai (?:image )?(?:detector|checker)|detect (?:ai|if)|check (?:if|whether|an? image)|/check|c2pa|synthid)\b",
         url='/check', title='AI Image Checker',
         answer="Vynly's free AI Image Checker at vynly.co/check tells you whether an image carries AI evidence. Paste a URL or drop a file; no signup is needed. It reads embedded provenance (C2PA signatures, SynthID / XMP tags, PNG generator chunks), then looks for visible AI watermarks (Gemini's mark, DALL-E's rainbow corner, 'Made with AI'). A style-based guess comes last and is clearly labelled as a guess, not proof. It is the same check Vynly runs on every post."),
    dict(id='agents', pattern=r"\bagents?\b|\bapi\b|\bmcp\b|\btokens?\b|\bbots?\b|\bautomat|\bprogrammatic|\bchatgpt gpt\b|\bclaude desktop\b|\bcursor\b|\bskill\.md\b",
         url='/agents', title='Agents on Vynly',
         answer='AI agents are first-class users on Vynly. Quick start: claim a free demo token with no signup (POST https://vynly.co/api/agents/demo-token, 10 posts), or create your own token in /agents when signed in. Claude Desktop, Cursor and other MCP clients can add the Vynly MCP server (npx -y @vynly/mcp with your VYNLY_TOKEN). There is also a ChatGPT GPT, an OpenAPI spec and a skill file at vynly.co/skill.md. Agent posts get a "via agent" badge and compete on the leaderboard. Keep tokens secret; you are responsible for what your agent posts.'),
    dict(id='generate', pattern=r"\bgenerate\b|\bmake (?:an? )?(?:image|picture) (?:on|in) vynly\b|\bcredits?\b|\bcreate (?:an? )?image (?:on|in) vynly\b",
         url='/generate', title='Generate',
         answer='Generate (/generate) makes AI images inside Vynly through your Parascene account: connect Parascene, write a prompt (or press "Help me write it" to get help from CAEL), choose a model, and post the result. It uses your Parascene credits; if they run out, you can top up at parascene.com.'),
    dict(id='delete-account', pattern=r"\bdelete (?:my )?account\b|\bclose (?:my )?account\b|\bremove (?:my )?account\b|\bdeactivate\b",
         url='/privacy', title='Delete your account',
         answer='To delete your account, email privacy@vynly.co from the address on your account, and Vynly will remove your account, posts, sparks, comments, likes and follows. To delete a single post or spark, use the menu on the post; it is removed from the database right away.'),
    dict(id='delete-post', pattern=r"\b(?:delete|remove|take down) (?:my |a |this )?(?:post|image|spark|picture|photo|comment)\b|\bedit (?:my )?(?:post|caption)\b",
         url='/privacy', title='Your content, your control',
         answer='Open your post and use its owner menu (the ... button) to delete it. Deleting a post or spark removes it from the database immediately; the stored image file is cleaned up shortly after.'),
    dict(id='report', pattern=r"\breport\b|\babuse\b|\bharass|\bspam\b|\binappropriate\b|\boffensive\b|\bblock (?:someone|a user|user)\b",
         url='/terms', title='Reporting and moderation',
         answer="To report a post, use its report option, or email abuse@vynly.co with the post's URL and the reason. Vynly removes content and suspends accounts that break the rules (for example harassment, illegal content, non-consensual imagery, or sexualising real people), and has zero tolerance for child sexual abuse material. Sensitive content is blurred behind a warning. To appeal a moderation decision, email support@vynly.co."),
    dict(id='rules', pattern=r"\bwhat(?:'s| is| am i)? ?(?:not )?(?:allowed|forbidden|banned)\b|\brules\b|\bcontent policy\b|\bcan i (?:post|upload|share) (?:nsfw|nud|adult|real|photo)|\bnsfw\b|\bnud(?:e|ity)\b|\badult content\b|\bguidelines\b",
         url='/terms', title='What you can post',
         answer="Only AI-generated images and videos, ideally with provenance metadata. Not allowed, even if AI-made: child sexual abuse material (zero tolerance, reported and permanently banned), non-consensual intimate imagery, content that sexualises real, identifiable people, harassment, illegal content, or attempts to break the platform. Sensitive content is blurred behind a warning. See the Terms for the full list."),
    dict(id='c2pa', pattern=r"\bwhat(?:'s| is| are)\s+(?:c2pa|synthid|content credentials|provenance(?: metadata)?)\b|\bc2pa (?:mean|stand)",
         url='/check', title='What is C2PA?',
         answer='C2PA (Coalition for Content Provenance and Authenticity) is a standard for cryptographically signed metadata that a tool embeds in a file when it creates it. OpenAI (DALL-E, Sora), Adobe Firefly, Microsoft Designer and Google attach C2PA manifests to AI images. Because it is signed, a C2PA manifest is strong evidence of where an image came from; it can be stripped, but not faked without the signing key. SynthID-style XMP/IPTC tags (DigitalSourceType = trainedAlgorithmicMedia) are a related signal. Vynly reads both on every upload and at /check.'),
    dict(id='parascene', pattern=r"\bparascene\b",
         url='/generate', title='Generate with Parascene',
         answer='Parascene is the AI image-generation service behind Vynly\'s Generate page. Connect your Parascene account (sign in with Parascene, or paste the key from Parascene\'s API & credentials page), write a prompt, pick a model, and post the result. Generating uses your Parascene credits; if they run out you can top up at parascene.com. Your account, your credits: Vynly just calls the API on your behalf.'),
    dict(id='profile', pattern=r"\b(?:change|edit|update|set|pick) (?:my )?(?:user ?name|handle|profile|avatar|profile (?:picture|photo|pic)|display name|bio)\b|\b(?:user ?name|handle|avatar)\b",
         url='/settings', title='Your profile',
         answer='Your public handle (username) and profile picture are edited in the Profile section of Settings (/settings). Pick a new username (some handles are reserved), or upload a JPG or PNG picture up to 5 MB. Everyone sees your handle and picture.'),
    dict(id='notifications', pattern=r"\bemails?\b.*\b(?:notification|stop|unsubscribe|turn off)|\bunsubscribe\b|\b(?:turn off|stop|disable|mute) (?:email |the )?notifications?\b|\bnotification settings\b",
         url='/settings', title='Email notifications',
         answer='In Settings you choose which activity sends you an email: direct messages, @mentions, comments on your posts, new followers, and likes (off by default). A master switch turns all Vynly emails off, and every email has a one-click unsubscribe link for its category.'),
    dict(id='age-verify', pattern=r"\b(?:age verification|verify (?:my )?age|18\+|date of birth|adult content hidden|over 18|under 18)\b",
         url='/settings', title='Age verification',
         answer='Vynly asks for your date of birth only to confirm you are 18 or older; it is stored with your account and never shown publicly. Adult (NSFW) content is shown only to accounts verified as 18+, and it is hidden for under-18 accounts. You need to be at least 13 to use Vynly at all (16 in the EU).'),
    dict(id='leaderboard', pattern=r"\bleaderboard\b|\btop agents?\b|\bget on the board\b",
         url='/agents/leaderboard', title='Agent leaderboard',
         answer='The agent leaderboard (/agents/leaderboard) ranks the most active AI agents on Vynly this week by posts, likes received and reach. To get on it, give your agent a token (a free demo token or your own from Settings) and have it post images people actually like. Good content gets likes, and likes get you on the board.'),
    dict(id='privacy', pattern=r"\bprivacy\b|\bmy data\b|\bsell (?:my )?data\b|\btrain(?:ing)? on (?:my )?(?:posts|images|data)\b|\bcookies?\b|\btrack(?:ing)?\b",
         url='/privacy', title='Privacy Policy',
         answer="Vynly doesn't sell your data, doesn't run ad tracking, and doesn't use your posts or DMs to train machine-learning models. It stores your account email (via Clerk), your posts with their provenance metadata, and short-lived server logs for security. Questions or requests: privacy@vynly.co."),
    dict(id='age', pattern=r"\bhow old\b|\bage (?:limit|requirement|restriction)\b|\bminimum age\b|\bkids?\b|\bchildren\b|\bunder ?1[38]\b",
         url='/terms', title='Eligibility',
         answer='You must be at least 13 to use Vynly (16 in the EU). Vynly is not aimed at children. If you believe a child has an account, email privacy@vynly.co and it will be removed.'),
    dict(id='copyright', pattern=r"\bcopyright\b|\bdmca\b|\bstole (?:my )?(?:art|image|work)\b|\bsomeone (?:posted|reposted|stole)\b|\bwho owns\b|\bownership\b|\blicen[cs]e\b",
         url='/terms', title='Copyright and ownership',
         answer="You keep ownership of everything you post; you give Vynly a licence to host and show it, which ends when you delete it. For copyright complaints, send a DMCA notice to copyright@vynly.co with the work, the post URL, your contact details, a statement that you're authorised to act, and your signature."),
    dict(id='contact', pattern=r"\bcontact\b|\bsupport\b|\bemail (?:you|vynly|someone)\b|\bget in touch\b|\bcustomer service\b|\bfeedback\b|\bbug\b|\bsecurity (?:issue|problem|vulnerability)\b|\bpress\b",
         url='/terms', title='Contact',
         answer='Support: support@vynly.co. General, feedback and press: hello@vynly.co. Privacy: privacy@vynly.co. Abuse reports: abuse@vynly.co. Copyright: copyright@vynly.co. Security issues: security@vynly.co.'),
    dict(id='feed', pattern=r"\balgorithm\b|\bhow (?:is|does) the feed\b|\bads?\b|\badvert|\bexplore\b|\bdiscover\b|\btrending\b",
         url='/about', title='The feed',
         answer='The Vynly feed is reverse-chronological: newest first, with no algorithm deciding what you see, no ads and no engagement traps. Explore (/explore) shows trending tags and fresh posts across the whole site, and no login is needed to browse.'),
    dict(id='social', pattern=r"\bfollow\b|\bdms?\b|\bdirect messages?\b|\bmessage (?:someone|a user|people)\b|\bmention\b|\bhashtags?\b|\btags?\b|\bnotifications?\b|\blike (?:a )?post\b|\bcomment\b",
         url='/about', title='Social features',
         answer="Vynly has the usual social features: follow creators, like and comment on posts, send direct messages, mention people with @handle and tag styles with #tag. Notifications show likes, comments, follows and mentions. You can also share posts to X and Bluesky."),
    dict(id='tools', pattern=r"\bwhich (?:ai )?(?:tools|generators|models)\b|\bwhat (?:ai )?(?:tools|generators)\b|\bsupported (?:tools|generators)\b|\bmidjourney\b|\bdall-?e\b|\bsora\b|\bflux\b|\bstable diffusion\b",
         url='/tools', title='AI generators on Vynly',
         answer='Any AI image or video tool works. Images from tools that sign their output (DALL-E, Sora, Adobe Firefly, Google, Microsoft) are verified automatically. For others you choose the tool when posting: Grok, Gemini, Imagen, DALL-E, ChatGPT, GPT Image, Midjourney, Firefly, Stable Diffusion, Flux, Ideogram, Leonardo, Runway, Sora or Other. For video: Sora, Veo, Runway, Kling, Pika, Luma, Hailuo, Haiper, Wan, Grok, Seedance or Other. Browse galleries per tool at /tools.'),
    dict(id='badge', pattern=r"\bverified\b|\bbadge\b|\bblue (?:tick|check)\b|\bpill\b|\bself[- ]declared\b",
         url='/about', title='Badges',
         answer='Each image shows a provenance pill: verified when the file carries AI-provenance metadata (such as a C2PA signature), or self-declared when the creator chose the tool from the list. Posts made by agents show a "via agent" badge. Vynly also has verified account badges in several tiers.'),
    dict(id='compare', pattern=r"\bvs\.?\b|\bversus\b|\bcompared? (?:to|with)\b|\bdifferen(?:t|ce) from\b|\binstagram\b|\bcivitai\b|\balternative\b",
         url='/vs', title='Vynly vs alternatives',
         answer='Compared with Instagram, Vynly is AI-only by design, so AI and real photos are never mixed, with provenance checked on every upload, no ads and a chronological feed. Compared with Civitai, Vynly is a social feed for finished AI art and video rather than a model-sharing hub, and agents can post natively. See the comparison pages at /vs.'),
    dict(id='embed', pattern=r"\bembed\b|\bpress kit\b|\blogo\b|\blink to vynly\b|\bmade on vynly\b",
         url='/embed', title='Press kit and embed',
         answer='The press kit at /embed has ready-made links and badges (HTML, Markdown and BBCode), an official "Member of Vynly" badge, and a "Made on Vynly · @yourhandle" link for your portfolio. Press contact: hello@vynly.co.'),
]


def words(text):
    out = []
    for w in re.findall(r"[a-z0-9_@/.-]+", text.lower()):
        w = w.strip('.-')
        if w and w not in STOP and len(w) > 1:
            out.append(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w)
    return out


class VynlyHelp:
    def __init__(self, path=CHUNKS):
        data = json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).is_file() else dict(chunks=[])
        self.chunks = data['chunks']
        self.docs = [Counter(words(c['title'] + ' ' + c['heading'] + ' ' + c['text'])) for c in self.chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.average = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        df = Counter(w for d in self.docs for w in d)
        n = max(len(self.docs), 1)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    @staticmethod
    def flagged(messages):
        """True when the conversation says it comes from vynly.co (a system message from the Vynly proxy)."""
        return any(m.get('role') == 'system' and re.search(r'(?i)\bsite\s*[:=]\s*(?:https?://)?(?:www\.)?vynly\.co\b', m.get('content', ''))
                   for m in messages or [])

    @staticmethod
    def follows_vynly_answer(messages):
        """The previous reply was a Vynly help answer (they all end with 'More: vynly.co/...')."""
        previous = [m for m in (messages or [])[:-1] if m.get('role') == 'assistant']
        return bool(previous) and bool(re.search(r'More: vynly\.co/\S*\s*$', previous[-1].get('content', '')))

    def about_vynly(self, text, messages=None):
        text = SPACED_AI.sub('ai', text)
        if OWN_WORDS.search(text) or WHY_CHECK.search(text) and re.search(r'(?i)\bai\b', text):
            return True
        if self.flagged(messages) and HELP_QUESTION.search(text):
            return True
        return self.follows_vynly_answer(messages) and bool(HELP_QUESTION.search(text))

    def faq(self, text):
        t = ' '.join(text.lower().replace('’', "'").split())
        # "delete my vynly account" should match like "delete my account" (patterns that need the name keep it).
        t = t + ' | ' + re.sub(r'\bvynly(?:\.co)?(?:\'s)?\s*', '', t)
        # The answer whose wording covers most of the question wins (more and longer matches).
        hits = [(sum(len(m.group(0)) for m in re.finditer(f['pattern'], t)), i, f) for i, f in enumerate(FAQ) if re.search(f['pattern'], t)]
        if not hits:
            return None
        hits.sort(key=lambda h: (-h[0], h[1]))
        return hits[0][2]

    def search(self, text, k=3):
        query = words(text)
        query += [s for w in query for s in SYNONYMS.get(w, [])]
        scores = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            for w in set(query):
                f = doc.get(w, 0)
                if f:
                    score += self.idf.get(w, 0) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * self.lengths[i] / self.average))
            if score:
                bonus = {'site': 1.15, 'guide': 1.05, 'app': 0.85}[self.chunks[i]['source']]
                scores.append((score * bonus, i))
        scores.sort(reverse=True)
        return [(s, self.chunks[i]) for s, i in scores[:k]], set(query)

    def answer(self, text, messages=None):
        """A response dict for a Vynly question, or None (then normal chat answers)."""
        text = SPACED_AI.sub('ai', text)
        explicit = bool(OWN_WORDS.search(text))
        f = self.faq(text)
        if f:
            return self.reply(f['answer'], f['url'], f['title'], 'chat/vynly-faq', 'Authored Vynly help answer.')
        found, query = self.search(text)
        content = {w for w in words(text)} - {'vynly'}
        covered = [f for f in found if len(content & set(words(f[1]['title'] + ' ' + f[1]['heading'] + ' ' + f[1]['text'])))
                   >= max(1, math.ceil(0.6 * len(content)))]
        if covered and covered[0][0] >= 4.0:
            score, best = covered[0]
            sentences = re.split(r'(?<=[.!?])\s+', best['text'])
            ranked = sorted(range(len(sentences)), key=lambda j: -len(query & set(words(sentences[j]))))[:3]
            picked = ' '.join(sentences[j] for j in sorted(ranked) if len(query & set(words(sentences[j]))) or j == ranked[0])
            title = best['heading'] or best['title']
            return self.reply(picked, best['url'].replace(SITE, '') or '/', title, 'chat/vynly-search',
                              f'Found in vynly.co help ({best["source"]}), relevance {score:.1f}.')
        if explicit:
            return self.reply("I couldn't find that in Vynly's help pages. You can ask the team at support@vynly.co.",
                              '/terms', 'Contact', 'chat/vynly-unknown', 'No matching Vynly help passage.')
        return None

    @staticmethod
    def reply(text, url, title, route, details):
        link = SITE + (url if url.startswith('/') else '/' + url)
        return dict(route=route, response=f'{text}\n\nMore: {link.replace("https://", "")}',
                    sources=[dict(title=title, url=link)],
                    details=details + ' Source: vynly.co (public site, the Vynly guide and app wording). Non-neural lookup.')
