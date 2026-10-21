"""One public interface for the CAEL 0.2.7 model bundle."""
__version__ = '0.2.7'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
