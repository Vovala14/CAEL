"""Preserve a narrow output-format request around the existing exact helper."""
import re
from .helper import calculate


def reply(text):
    match = re.fullmatch(r'(?is)(.{1,240}?[?.!])\s+(?:please )?(answer briefly|keep (?:the answer |it )?brief|(?:give|return|reply with) (?:only )?(?:the )?(?:number|answer) only)[.!]*\s*', text)
    if not match:
        return None
    result = calculate(match[1].rstrip('?.! '))
    if result is None:
        return None
    result = dict(result, details='Standalone brevity instruction preserved around the existing bounded exact arithmetic helper.')
    if 'only' in match[2].lower():
        result['response'] = result['response'].rsplit(' = ', 1)[-1]
    return result
