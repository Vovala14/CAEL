"""CAEL 0.4.1: non-neural core engines with checked conversation skills, chat memory and web answers."""
__version__ = '0.4.1'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
