"""CAEL 0.4.4: non-neural conversation team with a think-first swarm (exact readers, checks and votes), a constraint solver and an extended ARC grid solver."""
__version__ = '0.4.4'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
