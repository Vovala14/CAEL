# Local capability dependencies

The optional PDF parser is pypdf 6.21.2, BSD-3-Clause. Its wheel SHA256 is pinned
in requirements-local-tools.txt. Existing Pillow 12.3.0 (HPND/Pillow licence)
and NumPy 2.5.3 (BSD and included third-party notices) provide decoding and pixel
arithmetic. Retained installed-distribution notices are under the versioned
directories here. Their source paths and hashes are recorded in
research/compare_qwen/local_capabilities_20261021/dependencies.json.

No new image model, external LM, NSFW training dataset or paid service is used.
All new test data is locally authored text, PDF fixtures and solid-colour media.
Earlier copies with shortened basenames are retained as development evidence;
the versioned directory hierarchy and dependencies.json identify authoritative
copies without basename collisions.

Video decoding invokes the owner's already installed FFmpeg/ffprobe executable;
it is not bundled, installed or redistributed by this change. The detected
FFmpeg 8.0 gyan full build enables GPL and version3. FFmpeg licences and any
redistribution obligations apply independently to that executable. No neural
filters or downloaded weights are invoked.

These dependency permissions do not relicense CAEL. The project's existing
noncommercial LICENSE remains unchanged, as the owner requested earlier.
