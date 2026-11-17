"""CAEL 0.4.2: non-neural conversation team with fielded retrieval, conversation coherence and the Supporter."""
__version__ = '0.4.2'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
