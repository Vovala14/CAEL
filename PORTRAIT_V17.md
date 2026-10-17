# v17: more fitting alignments, mixed generation results

Checkpoint: `models/cael-portrait-64-v17-alignment/model_v17.pt`.

Blind preprocessing increased accepted fitting alignments from 76 to 125,
recovering 49 additional eye pairs from the existing 470 fitting photos. The
previous 76 alignments and their framing targets were retained exactly. New
alignments require agreement between two classical eye detectors and between
the original and horizontally flipped input. All 52 held-out photos remained
excluded. No private source photos or crops were displayed.

The v15 non-neural statistical appearance/deformation model was refitted on
these 125 alignments. Its two population templates initialized the fit; the
result contains populations of 56 and 69. A first, separate population-fit
attempt lost too much diversity and was not selected. This architecture is
still a statistical appearance model with continuous rendering, not a neural
generator or an improvement to the pixel CA alone.

After selection, 32 further fixed-seed draws compared v15 and v17. Pairwise
RGB L1 diversity was 48.9822 versus 47.0075, edge density 0.1033 versus 0.0778,
and minimum nearest-fitting RMS 0.165293 versus 0.148274. No similarity-guard
replacement was needed. These diagnostics passed the frozen numerical checks;
they do not measure facial realism. The earlier review of generated outputs
found smoother faces in some cases, but mixed results overall, with blur,
averaged appearance and shape artifacts remaining. There is no demonstrated
dramatic quality gain. v17 remains a separate candidate; v15 remains the CLI
default and the live UI remains on i16.

Checkpoint reload reproduced the seed-42 CLI pixels. All 522 current source
file hashes and the prior v15 checkpoint remained unchanged. All 45 software
tests passed. Verification and fixed generated comparisons are stored beside
the checkpoint. The v17 verification records code hashes from that run;
subsequent optional detector-resolution handling for older copies preserves
the default detector behavior used by v17.

Generate using a new output directory:

```powershell
& ..\.venv-rocm\Scripts\python.exe cael_assistant\portrait_appearance_cli.py --model models\cael-portrait-64-v17-alignment\model_v17.pt --out outputs\portrait_v17_example --seed 42 --n 4
```

The later blind run on older source copies is documented in
`research/portrait_older_alignment_20261016/README.md`. Its 38 accepted
alignments have not yet been included in a trained checkpoint.
