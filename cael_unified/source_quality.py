"""Known text-loss markers only; legitimate Unicode is never guessed away."""
import re

LOSS = re.compile(r'[\ufffd\ud800-\udfff\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def intact_text(text):
    return isinstance(text, str) and not LOSS.search(text)
