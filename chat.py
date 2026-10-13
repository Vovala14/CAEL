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
    a=p.parse_args()
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
