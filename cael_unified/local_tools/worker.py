"""Parser child: waits for bounded input until parent assigns the resource job."""
import base64
import json
import os
import sys
import logging


def main():
    logging.disable(logging.CRITICAL)
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(25,25))
    try:
        raw=sys.stdin.buffer.read(70_000_001)
        if len(raw)>70_000_000:raise ValueError('Parser request byte limit')
        request=json.loads(raw);blob=base64.b64decode(request['blob'],validate=True)
        if request['kind']=='pdf':
            from .pdf_tools import extract
            result=extract(blob,request.get('options',{}))
        elif request['kind'] in {'image','video'}:
            from . import media
            result=(media.image if request['kind']=='image' else media.video)(blob)
        else:raise ValueError('Unknown parser operation')
    except Exception as error:result=dict(status='error',error=type(error).__name__+': '+str(error)[:300])
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=True).encode('ascii'))


if __name__=='__main__':main()
