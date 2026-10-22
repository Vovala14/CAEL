"""Release guards using synthetic messages; no image data or private chats."""
from threading import RLock
from unittest.mock import Mock, patch

from cael_unified import __version__
from cael_unified.assistant import Assistant
from cael_unified.bundle import VERSION


def test_release_version_agrees():
    assert VERSION == __version__ == '0.2.9'


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
