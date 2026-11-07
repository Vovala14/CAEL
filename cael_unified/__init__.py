"""CAEL 0.4.0: non-neural symbolic, count and automaton core engines."""
__version__ = '0.4.0'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
