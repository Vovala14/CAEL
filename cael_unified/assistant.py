"""Shared chat/helper/emoji/photo interface for one CAEL model bundle."""
import json
from pathlib import Path
import re
import secrets
import threading

from .bundle import ROOT, open_bundle
from .helper import calculate

IMAGE = re.compile(r'\b(?:draw|paint|sketch|render)\b|\b(?:make|create|generate|show|give)\b.{0,45}\b(?:image|picture|photo|portrait|pic|illustration)s?\b', re.I)
CODE = re.compile(r'\b(?:python|javascript|code|function|script|program|api|resize|crop|compress|matplotlib|pillow|opencv)\b', re.I)
HOWTO = re.compile(r'^\s*(?:how|why|what is|what are|explain)\b', re.I)


def route_request(text, mode='auto'):
    if mode not in ('auto', 'chat', 'emoji', 'image'):
        raise ValueError('Unknown assistant mode')
    if mode != 'auto':
        return mode
    if not CODE.search(text) and not HOWTO.search(text):
        if re.search(r'\bemojis?\b', text, re.I):
            return 'emoji'
        if IMAGE.search(text):
            return 'image'
        if re.search(r'\b(?:make|create|generate|show)\b', text, re.I):
            from cael_image.general_curriculum import SUBJECTS
            if any(re.search(r'\b' + re.escape(w) + r'\b', text, re.I) for _, words in SUBJECTS.values() for w in words):
                return 'image'
    return 'chat'


class Assistant:
    def __init__(self, bundle=None, output_root=None):
        self.root, self.manifest = open_bundle(bundle)
        self.output_root = Path(output_root or ROOT / 'outputs' / 'unified').resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._emoji = self._image = self._chat = self._portrait = None
        self._lock = threading.RLock()

    def respond(self, messages, n=2, seed=None, mode='auto'):
        if not isinstance(messages, list) or not messages or not all(isinstance(m, dict) and m.get('role') in ('user', 'assistant', 'system') and isinstance(m.get('content'), str) for m in messages):
            raise ValueError('Invalid message format')
        if messages[-1]['role'] != 'user':
            raise ValueError('Messages must end with a user request')
        if len(messages) > 80 or sum(len(m['content']) for m in messages) > 32000:
            raise ValueError('Conversation exceeds the local context limit')
        if type(n) is not int or not 1 <= n <= 8:
            raise ValueError('Choose between 1 and 8 outputs')
        seed = secrets.randbelow(2 ** 31) if seed is None else int(seed)
        if not 0 <= seed < 2 ** 31:
            raise ValueError('Seed must be between 0 and 2147483647')
        text = messages[-1]['content'].strip()
        if not text:
            raise ValueError('Request is empty')
        route = route_request(text, mode)
        with self._lock:
            if route == 'image':
                return self.image_reply(text, n, seed)
            if route == 'emoji':
                return self.emoji_reply(text, n, seed)
            answer = calculate(text)
            if answer:
                return answer
            # Preserve the released constrained story engine and reconstruct its
            # world per conversation; never share mutable story state across users.
            if re.search(r'\bstory\b', text, re.I) or text.lower().startswith(('who ', 'where ')):
                from cael import CAEL, Unsupported
                story = CAEL(self.root / 'story' / 'model.json')
                try:
                    if text.lower().startswith(('who ', 'where ')):
                        previous = next((m['content'] for m in reversed(messages[:-1]) if m['role'] == 'user' and 'story' in m['content'].lower()), None)
                        if previous:
                            story.story(previous, seed)
                            result = story.ask(text)
                        else:
                            raise Unsupported('No prior story in this conversation')
                    else:
                        result = story.story(text, seed)
                    return dict(result, route='chat/story')
                except Unsupported:
                    pass
            if self._chat is None:
                from .legacy_chat.cael_v4 import V4, load_v2
                self._chat = V4(load_v2(self.root / 'chat'))
            result = dict(self._chat.respond(messages))
            result['route'] = 'chat/local-' + result.get('route', 'unknown')
            return result

    def emoji_reply(self, text, n, seed):
        import torch
        torch.set_num_threads(4)
        if self._emoji is None:
            from .emoji import EmojiTool
            self._emoji = EmojiTool(self.root / 'emoji' / 'model.pt', self.root / 'emoji' / 'references.pt')
        subject = re.sub(r'(?i)^\s*(?:please\s+)?(?:make|create|generate|draw|show|give)(?:\s+me)?\s+(?:an?\s+)?', '', text)
        subject = re.sub(r'(?i)\bemojis?\s*(?:of|for)?\b', '', subject).strip(' .!?')
        original_subject = subject
        self._emoji.ensure()
        phrase_key = re.sub(r'[^a-z0-9]+', '', subject.lower())
        if phrase_key in self._emoji.learned:
            subject = phrase_key
        folder = self.output_root / ('emoji_' + secrets.token_hex(8))
        info = self._emoji.generate(subject, n=n, seed=seed, outdir=folder)
        details = 'Offline 64x64 integer CA emoji; unfamiliar words may be ignored.'
        if info.get('fetched'):
            sources = info['fetched']
            shared = any('BY-SA' in item['licence'] for item in sources)
            attribution = dict(sources=sources, modification='Source shapes normalized to 64x64 and used through learned cellular counts.',
                               output_terms='CC BY-SA 4.0; retain attribution' if shared else 'Retain source attribution and the recorded source-license terms')
            (folder / 'attribution.json').write_text(json.dumps(attribution, indent=2), encoding='utf-8')
            details += ' Public reference sources: ' + '; '.join(item['source'] + ' (' + item['licence'] + ')' for item in sources)
            details += '. ' + attribution['output_terms'] + '; full source URLs are in attribution.json beside the images.'
        return dict(route='emoji/generated', response=f'Created {n} emoji for {original_subject}.',
                    paths=info['paths'], grid=info['grid'], seed=seed,
                    details=details, tool=info)

    def image_reply(self, text, n, seed):
        import torch
        from PIL import Image
        from cael_image.general_appearance import GeneralAppearance
        torch.set_num_threads(4)
        if self._image is None:
            checkpoint = torch.load(self.root / 'image' / 'model.pt', map_location='cpu', weights_only=True)
            self._image = GeneralAppearance(checkpoint)
        portrait = bool(re.search(r'\bportrait\b|head.and.shoulders', text, re.I)) and not re.search(r'\b(man|men|male|boy)\b', text, re.I)
        try:
            if portrait:
                from cael_image.portrait_deformation import DeformationPrior
                from cael_image.portrait_appearance import sample_guarded_appearance
                if self._portrait is None:
                    self._portrait = torch.load(self.root / 'portrait' / 'model.pt', map_location='cpu', weights_only=True)
                settings = self._portrait['settings']
                prior = DeformationPrior(self._portrait['prior'], warp_strength=settings['warp_strength'])
                images, checks = sample_guarded_appearance(prior, n, seed, self._image.checkpoint['guard_references'],
                                                          variation=settings['variation'], sharpen=settings['sharpen'])
                info = dict(subject='adult woman portrait', seed=seed, checks=checks,
                            limitation='Unconditional 64x64 portraits of adult women; caption attributes are not learned controls.',
                            guard_limit=self._portrait['guard_limit'])
            else:
                images, info = self._image.generate(text, n=n, seed=seed)
        except ValueError as exc:
            return dict(route='image/unsupported', response=str(exc) + '. Available subjects: ' + ', '.join(self._image.checkpoint['priors']), paths=[])
        folder = self.output_root / ('image_' + secrets.token_hex(8))
        folder.mkdir(parents=True, exist_ok=False)
        paths = []
        for i, pixels in enumerate(images.numpy()):
            path = folder / f'image_{i:02d}_64.png'
            Image.fromarray(pixels).save(path)
            paths.append(str(path))
        grid = folder / 'grid.png'
        canvas = Image.new('RGB', (128 * n, 128))
        for i, pixels in enumerate(images.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (128 * i, 0))
        canvas.save(grid)
        (folder / 'generation.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
        return dict(route='image/generated', response=f'Created {n} small images of {info["subject"]}.',
                    paths=paths, grid=str(grid), seed=seed, details=info['limitation'], tool=info)
