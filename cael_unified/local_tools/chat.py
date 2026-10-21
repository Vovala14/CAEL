"""Build local capability plans in chat without giving public chat host access."""
import ast
import json
import re

from .plans import emit,validate
from .workspace import ToolError


def parse(text):
    head=text.split('```',1)[0]
    if not re.search(r'(?i)\b(?:build|write|create|make)\b.{0,60}\b(?:tool|helper|workflow)\b',head):return None
    marker=re.search(r'(?im)^\s*steps?\s*:\s*',text)
    if marker is None:return None
    heading=text[:marker.start()]
    if not re.search(r'(?i)\b(?:local files?|file management|pdfs?|media review|moderation)\b',heading):return None
    if len(text)>5000 or '```' in text:raise ToolError('Use a short local capability specification without executable code')
    match=re.search(r'(?i)\b(?:named|called)\s+`?([A-Za-z_]\w*)',heading);name=match[1] if match else 'local_tool'
    steps=[]
    def string(raw):
        try:value=ast.literal_eval(raw)
        except (SyntaxError,ValueError):raise ToolError('Use quoted literal relative paths/globs')
        if not isinstance(value,str) or not 1<=len(value)<=500:raise ToolError('Use a short literal string')
        return value
    for line in text[marker.end():].splitlines():
        line=re.sub(r'^\s*(?:[-*]|\d+[.)])\s*','',line).strip().rstrip('.')
        if not line:continue
        match=re.fullmatch(r'find files matching (.+)',line,re.I)
        if match:steps.append(dict(op='find',pattern=string(match[1])));continue
        if line.lower() in {'read matching files','extract text from matching pdfs','queue matching media for review'}:
            steps.append(dict(op={'read matching files':'read_found','extract text from matching pdfs':'pdf_found','queue matching media for review':'enqueue_found'}[line.lower()]));continue
        match=re.fullmatch(r'(touch|read|extract pdf text from|inspect media|queue media for review) (.+)',line,re.I)
        if match:steps.append(dict(op={'touch':'touch','read':'read','extract pdf text from':'pdf','inspect media':'inspect','queue media for review':'enqueue'}[match[1].lower()],path=string(match[2])));continue
        raise ToolError('Unknown local capability step; no filesystem operation was executed')
    return validate(dict(name=name,steps=steps))


def reply(text):
    try:plan=parse(text)
    except ToolError as error:return dict(route='chat/code-local-tool-clarify',response=str(error),sources=[],details='No host-file access from chat. Local owner-selected workspace required.')
    if plan is None:return None
    source=emit(plan)
    return dict(route='chat/code-local-tool-built',sources=[],response='Built local capability tool `'+plan['name']+'`:\n\n```python\n'+source+'```\n\nCapability plan:\n```json\n'+json.dumps(plan,indent=2)+'\n```\n\n'
                'No local files were opened or changed by this chat. Save the JSON plan and run it locally with:\n'
                '```text\npython -m cael_unified.local_tools --root YOUR_WORKSPACE run-plan PLAN.json\n```\n'
                'The owner chooses the workspace. Find/read stay inside it; touch creates an empty file only when absent. '
                'PDFs use text-layer extraction with page references; scans may need OCR. Media cues only prioritize manual review, never approve or blur content.',
                details='Non-neural composition of explicit file/PDF/media capabilities. No exec of generated code, arbitrary imports, automatic moderation decision, or anonymous host-file API. '
                        'This is a local capability plan, not evidence of general Python or semantic image understanding.')
