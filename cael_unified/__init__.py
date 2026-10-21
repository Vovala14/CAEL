"""One public interface for the CAEL 0.2.8 model bundle."""
__version__ = '0.2.8'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
