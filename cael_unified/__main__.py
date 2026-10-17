"""Run the unified CAEL assistant, download its bundle, or open its local UI."""
import argparse
import json

from .bundle import VERSION, download_bundle, install_models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prompt', nargs='?')
    parser.add_argument('--bundle')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--ui', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--mode', choices=['auto', 'chat', 'emoji', 'image', 'prompt', 'story'], default='auto')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--n', type=int, default=2)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.download:
        bundle = download_bundle(args.bundle)
        print(bundle)
        print(json.dumps(install_models(bundle), indent=2))
        return
    from .assistant import Assistant
    assistant = Assistant(args.bundle)
    if args.ui:
        from .web import serve
        serve(assistant, args.port)
        return
    history = []

    def respond(prompt):
        history.append(dict(role='user', content=prompt))
        result = assistant.respond(history[-40:], n=args.n, seed=args.seed, mode=args.mode)
        history.append(dict(role='assistant', content=result['response']))
        print(json.dumps(result, indent=2) if args.json else result['response'])
        if not args.json:
            for path in result.get('paths', []):
                print(path)

    if args.prompt:
        respond(args.prompt)
    else:
        print(f'CAEL {VERSION}: chat, helper, emoji and small pictures. Type quit to exit.')
        while True:
            try:
                prompt = input('You: ').strip()
                if prompt.lower() in ('quit', 'exit'):
                    break
                if prompt:
                    respond(prompt)
            except (EOFError, KeyboardInterrupt):
                break
            except (ValueError, RuntimeError) as error:
                print(str(error))


if __name__ == '__main__':
    main()
