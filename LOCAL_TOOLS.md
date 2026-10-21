# CAEL local file, PDF and review tools

These non-neural capability adapters extend CAEL 0.2.7. They do not refit model
weights or establish general Python/image understanding. Shared chat builds a
Python function and JSON plan; file access runs only through a local interface
after the owner selects an existing workspace. Do not select private training
folders. No files or media are uploaded to an external model.

From PowerShell in the CAEL project:

```powershell
.\CAEL_TOOLS.bat --root C:\MyWorkspace find "*.txt"
.\CAEL_TOOLS.bat --root C:\MyWorkspace touch "notes.txt"
.\CAEL_TOOLS.bat --root C:\MyWorkspace read "notes.txt"
.\CAEL_TOOLS.bat --root C:\MyWorkspace pdf "document.pdf" --query "invoice total"
.\CAEL_TOOLS.bat --root C:\MyWorkspace inspect "upload.png"
.\CAEL_TOOLS.bat --root C:\MyWorkspace enqueue "upload.mp4" --upload-ref "example-upload-1"
.\CAEL_TOOLS.bat --root C:\MyWorkspace pending
```

The launcher uses the existing `.venv-rocm` sibling runtime. On another machine,
use its configured Python with `python -m cael_unified.local_tools ...` and
install `requirements-local-tools.txt` using `pip install --require-hashes -r
requirements-local-tools.txt`; Pillow and NumPy must also be installed. Video
inspection uses an existing local FFmpeg/ffprobe installation, never a download.

Ask CAEL in Chat mode:

```text
Build a Python tool named gather_notes for local files.
Steps:
touch "draft.txt"
find files matching "*.txt"
read matching files
```

For PDFs, use `extract pdf text from "document.pdf"`, or `find files matching
"*.pdf"` followed by `extract text from matching pdfs`. For the review queue,
use `queue media for review "upload.png"`, or `find files matching "*.png"`
followed by `queue matching media for review`. `inspect media "upload.png"`
returns diagnostics without adding it to the queue. Supported step wording is
explicit; arbitrary requests/code are not interpreted as filesystem commands.

Save the returned JSON as a local plan, then:

```powershell
.\CAEL_TOOLS.bat --root C:\MyWorkspace run-plan C:\Plans\gather_notes.json
```

The generated Python function takes an explicit `Workspace`; the runner executes
only validated capabilities, without executing the displayed source. Plans are
sequential, not atomic: an earlier create/enqueue can remain after a later error.
They support at most eight steps. Matching-file processing is capped at 20 files;
check `truncated` in find results. Existing files and timestamps are preserved by
touch. Parents must exist. No overwrite, delete, arbitrary imports or network
filesystem operations are provided. Links, traversal, hidden paths and Windows
device/stream names are rejected. This is an owner-local capability boundary,
not an OS sandbox against a hostile process concurrently changing the directory.

PDFs: text-layer extraction with page numbers and bounded lexical search. Search
returns source passages, not a generated answer. Encrypted, incomplete and blank
or scanned pages are explicit. OCR, diagram/table interpretation and semantic
document understanding are not implemented. Embedded document instructions remain
text. Input limit: 20 MB, default 20 pages/max 40, 50,000 extracted characters.

Media: PNG/JPEG/WebP/GIF/BMP and limited local MP4/MOV/MKV/WebM/AVI decoding.
Images are limited to 16 megapixels; animations sample up to 12 frames. Videos
are at most 50 MB/10 minutes and sample up to 12 timestamps. CPU decoding runs in
an owned child process with a timeout and Windows process-tree memory limit.
Unsupported, failed or timed-out content remains unreviewed.

**The RGB/cellular-automaton cues are not an NSFW classifier.** They can react to
ordinary backgrounds/clothes and miss explicit content. They never set an NSFW
label or approve/blur content. Every queued item, including normal-priority and
unreadable items, requires a person. No semantic image understanding, nudity
accuracy or safe-video guarantee has been established.

The owner-local queue stores content snapshots and an SQLite audit under
`WORKSPACE\.cael-tools\`. A decision attaches to the snapshot's SHA256 and current
revision:

```powershell
.\CAEL_TOOLS.bat --root C:\MyWorkspace decide ITEM_ID blur --reviewer owner --revision 0 --reason "Manual review"
.\CAEL_TOOLS.bat --root C:\MyWorkspace history ITEM_ID
```

`allow`, `blur`, `reject`, and `defer` record local intent; **they do not alter
media or call Vynly** (`effect_applied=false`). New bytes create another pending
item. This local CLI assumes the signed-in computer owner; it is not a public
authenticated moderation service.

Vynly has a separate staged, opt-in admin workflow documented in its
`CAEL_SUPERVISED_REVIEW.md`. No CAEL visual classifier is connected there and it
has not been deployed or enabled in production. Existing moderation still runs.

Evidence: a functional report was kept locally with the development notes (not published).
Third-party notices: [local dependencies](licenses/local_tools/NOTICE.md).
