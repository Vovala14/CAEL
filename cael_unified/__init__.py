"""CAEL 0.4.3: non-neural conversation team with authored Programmer, Explainer, Coach and Supporter desks, fielded retrieval and an ARC grid solver."""
__version__ = '0.4.3'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
