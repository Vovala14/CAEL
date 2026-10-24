# Local chat upgrade, 2026-10-22

This is a local upgrade of 0.2.8, not a new published GitHub release. It retains
chat, story, prompt, reasoning, math, Python and emoji engines. Picture/portrait
generation checkpoints and image selections are omitted. Image prompts remain
available. Picture requests return a prompt rather than loading a local picture
checkpoint. Existing image models on the development machine are untouched.

Changes: retain exact fractions between plan steps; preserve decimal source
digits in arithmetic and symbolic parsing; handle chained percentage changes
and tripling; ask which equation solution to use rather than choosing a root.
The CA kernels and non-neural language architecture are unchanged.

After installing the existing requirements, from the extracted folder:

```powershell
python -c "from cael_unified.bundle import install_models; print(install_models())"
python -m cael_unified --ui
```

The model is included at `models/cael-0.2.8.cael`. No download is required.
On an existing development checkout, model installation preserves local
selections and different local files. Use a separate extracted folder to test
the packaged configuration. No live server is restarted by installation.

The separate 20261022 continuation candidate is experimental and not selected
or included. Its protocol, hashes, scores and limitations are retained under
`research/upgrade_20261022/` on the development machine. No private images or
user chat histories were read for this experiment. No benchmark rows trained
the candidate. A small repeated HellaSwag diagnostic is not a leaderboard claim.
