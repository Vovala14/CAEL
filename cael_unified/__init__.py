"""CAEL 0.4.5: non-neural conversation team with exact skills first (story world model, question-guided word-problem arithmetic, chess against its own engine), a think-first swarm and an ARC grid solver with a program search and cell-rule learner."""
__version__ = '0.4.5'


def __getattr__(name):
    if name == 'Assistant':
        from .assistant import Assistant
        return Assistant
    raise AttributeError(name)
