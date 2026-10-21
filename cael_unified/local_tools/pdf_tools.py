"""Text-layer extraction and lexical evidence, with explicit partial/OCR states."""
from collections import Counter
import io
import re


def extract(blob,options):
    from pypdf import PdfReader
    maximum=options.get('pages',20)
    if type(maximum) is not int or not 1<=maximum<=40:raise ValueError('PDF page limit must be 1..40')
    if not blob.startswith(b'%PDF-'):raise ValueError('Expected a PDF header')
    reader=PdfReader(io.BytesIO(blob),strict=False)
    if reader.is_encrypted:return dict(status='encrypted',pages=[],needs_password=True,complete=False,text='',warnings=['Encrypted PDF was not decrypted'])
    total=len(reader.pages);pages=[];warnings=[];remaining=50000
    for index in range(min(total,maximum)):
        page=reader.pages[index]
        try:
            stream=page.get_contents()
            if stream and len(stream.get_data())>4_000_000:
                pages.append(dict(page=index+1,status='content_limit',text=''));continue
            text=page.extract_text() or '';clipped=len(text)>remaining
            text=text[:remaining];remaining-=len(text)
            pages.append(dict(page=index+1,status='text_truncated' if clipped else 'text' if text.strip() else 'no_text_layer',text=text))
        except Exception:
            pages.append(dict(page=index+1,status='extraction_failed',text=''))
        if remaining<=0:break
    no_text=[p['page'] for p in pages if p['status']=='no_text_layer']
    if no_text:warnings.append('Pages without extractable text may be scans or blank; non-neural OCR is not installed')
    if len(pages)<total:warnings.append('Not all PDF pages were extracted')
    complete=len(pages)==total and all(p['status']=='text' for p in pages)
    return dict(status='ok' if complete else 'partial',page_count=total,pages=pages,complete=complete,needs_ocr=bool(no_text),
                text='\n\n'.join(p['text'] for p in pages),warnings=warnings,semantic_understanding=False)


def search(document,query,limit=5):
    if not isinstance(query,str) or not 1<=len(query)<=500:raise ValueError('Use a query of 1..500 characters')
    if type(limit) is not int or not 1<=limit<=10:raise ValueError('Evidence limit must be 1..10')
    stop={'the','a','an','is','are','what','when','where','how','of','to','in','and','does','this','document','pdf'}
    terms=set(re.findall(r'\w+',query.casefold()))-stop
    if not terms:return dict(status='no_evidence',passages=[],answer=None,grounded=True)
    found=[]
    for page in document.get('pages',[]):
        for passage in re.split(r'\n\s*\n|(?<=[.!?])\s+',page.get('text','')):
            counts=Counter(re.findall(r'\w+',passage.casefold()));matched=terms&counts.keys()
            if matched:found.append(dict(page=page['page'],quote=passage[:1200],matched_terms=sorted(matched),score=sum(min(counts[t],3) for t in matched)))
    found=sorted(found,key=lambda p:(-p['score'],p['page']))[:limit]
    return dict(status='evidence' if found else 'no_evidence',passages=found,answer=None,grounded=True,
                limitation='Lexical passages with page references; no inferred answer or guarantee that the passage answers the question')
