# Legacy CAEL 0.2 assistant source

For 0.2.1 use `python -m cael_unified --ui` and the single model bundle. The
following documents the preserved older interface and its v0.2 asset paths.

# CAEL assistant (v6.7 chat + image and emoji tools)
Run: `python cael_assistant/chat.py` (REPL) or `from chat import Assistant; Assistant().respond([{'role':'user','content':'make an emoji of fire'}])`.
- Emoji route: "make an emoji of ...", "make a pizza emoji", "emoji for ..." -> emojigen.py with models/cael-emoji-64-v2 (caption-conditioned integer CA).
- Image route: regex image-request detector with code/how-to vetoes -> imagegen.py with models/cael-image-portrait-64-i16 (unconditional integer CA, 64x64 head-and-shoulders portraits). Colour words act only through a hand-written colour rule.
- Prompt writer: rule parser + hand-written scene vocabulary; blocked terms are stored as hashes.
- Chat: set CAEL_V67_DIR to chat_v6_7/rs/v67 after building its stores (see chat_v6_7/STORES.md). Without it chat replies "chat-unavailable".
- No neural networks anywhere; torch is used as a tensor engine (CPU or ROCm/CUDA).
