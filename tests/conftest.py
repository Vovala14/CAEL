"""Tests never touch the real long-term memory file (state/ltm.json)."""
import os
import tempfile

os.environ.setdefault('CAEL_LTM', os.path.join(tempfile.mkdtemp(prefix='cael-ltm-'), 'ltm.json'))
