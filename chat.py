"""CAEL Story: constrained story generation and factual follow-up questions."""
import argparse
import json
from cael import CAEL, Unsupported

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prompt', nargs='?')
    p.add_argument('--model')
    p.add_argument('--ask', action='append', default=[])
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--json', action='store_true')
    p.add_argument('--image', action='store_true', help='Use the separately trained 64x64 CAEL image branch.')
    p.add_argument('--output', default='outputs/female-character.png')
    p.add_argument('--steps', type=int)
    p.add_argument('--noise', type=int)
    p.add_argument('--sampler', choices=['stable','legacy'], default='stable')
    a=p.parse_args()
    if a.image:
        if not a.prompt or a.ask:
            p.error('--image requires a prompt and does not accept --ask.')
        from pathlib import Path
        from cael_image.model import generate_file
        image_model=a.model or Path(__file__).resolve().parent/'models/cael-image-female-64-v2/model.npz'
        try:
            result=generate_file(image_model,a.prompt,a.output,a.seed,a.steps,a.noise,a.sampler)
        except (ValueError,OSError,ImportError) as exc:
            p.error(str(exc))
        print(json.dumps(result,indent=2) if a.json else 'Image saved: '+str(Path(a.output).resolve()))
        return
    model=CAEL(a.model) if a.model else CAEL()
    def respond(text):
        try:
            result=model.ask(text) if text.lower().strip().startswith(('who ','where ')) else model.story(text,a.seed)
            print(json.dumps(result,indent=2) if a.json else result['response'])
            return True
        except Unsupported as exc:
            print('Unsupported by CAEL Story 0.1: ' + str(exc))
            return False
    if a.prompt:
        if respond(a.prompt):
            for q in a.ask:
                respond(q)
    else:
        print('CAEL Story 0.1 — constrained stories and event-memory questions. Not general chat. Type quit to exit.')
        while True:
            try:
                text=input('You: ').strip()
            except (EOFError,KeyboardInterrupt):
                break
            if text.lower() in ('quit','exit'):
                break
            if text:
                respond(text)

if __name__=='__main__':
    main()
