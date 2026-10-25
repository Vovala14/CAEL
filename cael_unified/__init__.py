"""One public interface for the CAEL 0.3.3 model bundle."""
__version__ = '0.3.3'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
