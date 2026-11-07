"""CAEL 0.4.0 core-engine candidate; not a published or deployed release."""
__version__ = '0.4.0'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
