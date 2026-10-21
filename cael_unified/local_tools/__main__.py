"""Local CLI; deliberately no shared web endpoints or arbitrary code execution."""
import argparse
import json
from pathlib import Path

from .workspace import Workspace,ToolError


def main():
    parser=argparse.ArgumentParser(description='Owner-local CAEL file/PDF/manual media tools')
    parser.add_argument('--root',required=True,help='Existing ordinary workspace directory; never point at private training data')
    sub=parser.add_subparsers(dest='command',required=True)
    find=sub.add_parser('find');find.add_argument('pattern');find.add_argument('--limit',type=int,default=100)
    for command in ('touch','read','pdf','inspect','enqueue'):
        p=sub.add_parser(command);p.add_argument('path')
        if command=='pdf':p.add_argument('--query');p.add_argument('--pages',type=int,default=20)
        if command=='enqueue':p.add_argument('--upload-ref')
    sub.add_parser('pending')
    decision=sub.add_parser('decide');decision.add_argument('id');decision.add_argument('action',choices=['allow','blur','reject','defer']);decision.add_argument('--reviewer',required=True);decision.add_argument('--revision',required=True,type=int);decision.add_argument('--reason',default='')
    history=sub.add_parser('history');history.add_argument('id')
    run=sub.add_parser('run-plan');run.add_argument('plan',help='Explicit local JSON plan filename')
    args=parser.parse_args()
    try:
        workspace=Workspace(args.root)
        if args.command=='find':result=workspace.find(args.pattern,limit=args.limit)
        elif args.command=='touch':result=workspace.touch(args.path)
        elif args.command=='read':result=workspace.read(args.path)
        elif args.command=='pdf':
            result=workspace.pdf(args.path,pages=args.pages)
            if args.query:
                from .pdf_tools import search
                result=dict(document=result,evidence=search(result,args.query))
        elif args.command=='inspect':result=workspace.inspect_media(args.path)
        elif args.command=='run-plan':
            path=Path(args.plan)
            if path.stat().st_size>20000:raise ToolError('Plan file byte limit')
            result=workspace.run_plan(json.loads(path.read_text(encoding='utf-8')))
        else:
            from .review import ReviewQueue
            queue=ReviewQueue(workspace)
            if args.command=='enqueue':result=queue.enqueue(args.path,args.upload_ref)
            elif args.command=='pending':result=queue.pending()
            elif args.command=='history':result=queue.history(args.id)
            else:result=queue.decide(args.id,args.action,args.reviewer,args.revision,args.reason)
        print(json.dumps(result,ensure_ascii=True,indent=2));return 0
    except (ToolError,ValueError,OSError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=True));return 2


if __name__=='__main__':raise SystemExit(main())
