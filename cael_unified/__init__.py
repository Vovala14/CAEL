"""CAEL 0.3.9: non-neural conversation runtime with the unchanged 0.3.7 resource bundle."""
__version__ = '0.3.9'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
