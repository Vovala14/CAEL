"""CAEL assistant: v6.7 chat + image tool. Function API: Assistant().respond(messages) -> dict; REPL: python cael_assistant/chat.py
Emoji requests ("make an emoji of ...") go to emojigen (cael-emoji-64-v2).
Image requests (rule regex + optional v6.7 CA router veto) go to the prompt writer + i16 integer-CA image model.
Everything else falls through to the v6.7 chat pipeline (set CAEL_V67_DIR to the v6.7 code folder with its stores)."""
import os, sys, json, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import prompt_writer as pw

class Assistant:
    def __init__(s, image=True, v67_dir=None):
        s.image_on = image; s._img = None; s.v67 = None; s.v67_err = None
        d = v67_dir or os.environ.get('CAEL_V67_DIR')
        if d:
            try:
                os.environ.setdefault('WIKI_OFFLINE', '1'); sys.path.insert(0, d); os.chdir(d) if os.environ.get('CAEL_V67_CHDIR') else None
                from cael_v67 import V6; s.v67 = V6()
            except Exception as e: s.v67_err = f'{type(e).__name__}: {e}'
        else: s.v67_err = 'CAEL_V67_DIR not set'
    def img(s):
        if s._img is None:
            import imagegen; s._img = (imagegen, imagegen.ImageTool())
        return s._img
    def ca_typ(s, text):
        try:
            import cael_v66 as B6
            return B6.B.V4M.route([dict(role='user', content=text)])[0] if s.v67 is not None else None
        except Exception: return None
    def respond(s, messages, n=4, seed=None):
        text = messages[-1]['content']
        if pw.is_emoji_request(text): return s.emoji_reply(text, n, seed)
        if pw.is_image_request(text, s.ca_typ(text)): return s.image_reply(text, n, seed)
        if s.v67 is not None:
            out = s.v67.respond(messages); out['route'] = 'v6.7/' + str(out.get('route')); return out
        return dict(route='chat-unavailable', response="I can't answer chat questions in this setup: the v6.7 chat pipeline isn't loaded "
                    f"({s.v67_err}). I can still make images (64x64 portraits of women).")
    def emoji(s):
        if getattr(s, '_emo', None) is None:
            import emojigen; s._emo = emojigen.EmojiTool()
        return s._emo
    def emoji_reply(s, text, n=4, seed=None):
        subj = pw.emoji_subject(text).strip()
        if pw.is_unsafe(text):
            return dict(route='emoji/refused', response="I can't make adult-content emoji.", paths=[])
        if not s.image_on: return dict(route='emoji/disabled', response=f'Image generation is off here. Emoji subject: "{subj}"', paths=[])
        info = s.emoji().generate(subj, n=n, seed=seed)
        lim = ("Limits: 64x64 emoji from a learned integer cellular automaton (no neural net), trained on Noto Emoji and Blobmoji (Apache-2.0). "
               "Words steer colours and layout through learned counts per caption word (Unicode CLDR names and keywords), so results are rough "
               "and can mix up emoji that share words. Shown upscaled to 256x256; images alternate Noto-like and Blob-like style.")
        if not info['known_words']: lim += f" None of the words ({', '.join(info['words']) or 'none'}) are in its vocabulary, so these are unconditioned emoji."
        elif info['unknown_words']: lim += f" Ignored unknown words: {', '.join(info['unknown_words'])}."
        resp = f'Here are {len(info["paths"])} emoji for "{subj}":\n' + '\n'.join(info['paths']) + f"\nGrid: {info['grid']}\n{lim}"
        return dict(route='emoji/generated', response=resp, subject=subj, paths=info['paths'], grid=info['grid'], tool=info)
    def image_reply(s, text, n=4, seed=None):
        P = pw.parse(text); B = pw.build(P)
        if P['minor'] or P['unsafe'] or P['real_person']:
            why = 'images of minors' if P['minor'] else ('adult-content images' if P['unsafe'] else 'images of real people')
            return dict(route='image/refused', response=f"I can't make {why}. I can make a clothed head-and-shoulders portrait of an adult woman instead.",
                        prompt=None, caption=None, paths=[])
        head = f"Prompt: {B['rich']}\nCaption for the model: \"{B['caption']}\""
        if P['other'] and not P['woman']:
            return dict(route='image/unsupported', prompt=B['rich'], caption=None, paths=[],
                        response=f"My image model can only make small 64x64 head-and-shoulders portraits of women, so I can't draw {pw._join(P['other'])}. "
                                 f"Here is a full prompt you could use with another image tool:\n{B['rich']}")
        if not s.image_on:
            return dict(route='image/disabled', prompt=B['rich'], caption=B['caption'], paths=[], response='Image generation is off here.\n' + head)
        ig, tool = s.img(); m = tool.ensure(); notes = []
        targets = []
        for reg, col in B['targets']:
            d = float((m.pal - ig.torch.tensor(ig.COLOR_LAB.get(col, (0, 0, 0)), dtype=ig.torch.float32, device=m.dev)).norm(dim=1).min()) if col in ig.COLOR_LAB else 99
            (targets.append((reg, col)) if d <= 25 else notes.append(f"the model's 48-colour palette has no {col}, so the {reg} colour isn't steered"))
        info, _ = ig.generate2(tool, targets, n=n, oversample=3, seed=seed, strength=0.3 if targets else 0.0, tag='woman')
        ign = ['style' if P['style'] else None, 'accessories' if P['accessories'] else None, 'expression' if P['expr'] else None, 'setting, pose, lighting, mood and camera']; ign = [x for x in ign if x]
        honest = ("Limits: the model makes 64x64 head-and-shoulders portraits of women only (shown here upscaled to 256x256). It was trained without captions, so it "
                  "does not understand the prompt. ")
        if targets: honest += (f"I steered the colour with a hand-written rule ({', '.join(f'{c} {r}' for r, c in targets)}): it pushes the "
                               f"{' and '.join(r for r, _ in targets)} area toward that colour while sampling, then I keep the {n} closest of {info['sampled']} samples. "
                               + (f"The model doesn't know what {_a(P['garments'][0])} is. " if P['garments'] else "The model has no idea of hair or clothing; only colours in those areas change. "))
        if P['garments'] and not any(r == 'clothing' for r, _ in targets): honest += 'Clothing type is not controllable. '
        honest += f"Ignored by the model: {', '.join(ign)}. " + (' '.join(n_.capitalize() + '.' for n_ in notes))
        resp = f"Here are {len(info['paths'])} images:\n" + '\n'.join(info['paths']) + f"\nGrid: {info['grid']}\n{head}\n{honest.strip()}"
        return dict(route='image/generated', response=resp, prompt=B['rich'], caption=B['caption'], paths=info['paths'], grid=info['grid'], tool=info)

def _a(g): return pw._art(g) + g

def main():
    a = Assistant(); print('CAEL assistant. Type a message (blank line or "quit" to exit).', ('' if a.v67 else f'[chat backend off: {a.v67_err}]'))
    hist = []
    while True:
        try: t = input('you> ').strip()
        except EOFError: break
        if not t or t.lower() in ('quit', 'exit'): break
        hist.append(dict(role='user', content=t)); out = a.respond(hist[-6:])
        print('cael>', out['response'], f"\n   [{out['route']}]"); hist.append(dict(role='assistant', content=out['response']))
if __name__ == '__main__': main()


