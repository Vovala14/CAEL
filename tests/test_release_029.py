"""Release guards using synthetic messages; no image data or private chats."""
from threading import RLock
from unittest.mock import Mock, patch

from cael_unified import __version__
from cael_unified.assistant import Assistant
from cael_unified.bundle import BUNDLE_VERSION, DEFAULT_BUNDLE, VERSION


def test_release_version_agrees():
    import json
    from cael_unified.bundle import ROOT
    configured = json.loads((ROOT / 'bundle_config.json').read_text(encoding='utf-8'))['version']
    # 0.3.8 is code-only: the code version is 0.3.8, the pinned model bundle stays the published 0.3.7 one.
    assert VERSION == __version__ == '0.3.8'
    assert configured == BUNDLE_VERSION and DEFAULT_BUNDLE.name == f'cael-{BUNDLE_VERSION}.cael'


def test_picture_follow_up_cannot_load_weights_in_no_images_profile():
    engine = Assistant.__new__(Assistant)
    engine.manifest = {'profile': 'no-images'}
    engine._lock = RLock()
    engine.picture_in_chat = Mock(return_value={'route': 'prompt-only'})
    engine.image_reply = Mock(side_effect=AssertionError('Image weights must stay unused'))
    messages = [dict(role='user', content='draw a car'),
                dict(role='assistant', content='Created 1 image of a car'),
                dict(role='user', content='make it blue')]
    with patch('cael_unified.chat_extra.rewrite', return_value=None), \
            patch('cael_unified.orchestrator.plan', return_value=None):
        assert engine._respond(messages, seed=1)['route'] == 'prompt-only'
    engine.picture_in_chat.assert_called_once()
