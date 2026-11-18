"""Instruction -> shell steps, from authored recipes (no model).

A step is dict(kind, why, tries=[command, ...], check=command or None). The agent runs the tries in
order until one exits 0 and the check (if any) passes. Content is moved through base64, so quotes,
dollars and newlines in a task's text can't break the shell.
"""
import base64
import re
import shlex

EXT = r'(?:txt|py|json|csv|tsv|md|sh|c|h|cpp|js|ts|log|yaml|yml|toml|ini|cfg|conf|html|xml|sql|tar\.gz|tgz|tar|zip|gz|out|dat|env|rs|go|java|rb|pl)'
PATH = re.compile(r'`([^`\n]+)`|((?:~|\.{1,2})?/[\w.\-/]+[\w/]|(?<![\w/.])[\w.\-]+(?:/[\w.\-]+)+/?)|(?<![\w/])((?:[\w\-]+\.)+(?:' + EXT +
                  r'|[A-Za-z][A-Za-z0-9]{0,4}))\b')
NOT_FILE = re.compile(r'(?i)^(?:e\.g|i\.e|etc|vs|tar\.gz|zip|tgz|gz|tar|[\d.]+)$')
# "the directory old", "the proj folder", "a folder named output"
DIR_NAME = re.compile(r'(?i)\b(?:directory|folder|dir)\s+(?:called\s+|named\s+)?`?([\w.\-]+)`?|\bthe\s+`?([\w.\-]+)`?\s+(?:directory|folder)\b')
DIR_WORDS = {'a', 'an', 'the', 'this', 'that', 'it', 'is', 'and', 'to', 'in', 'into', 'with', 'from', 'of', 'here', 'current', 'new', 'empty',
             'same', 'called', 'named', 'which', 'where', 'containing', 'output'}
QUOTE = re.compile(r'```(?:\w+)?\n(.*?)```|"([^"\n]*)"|“([^”\n]*)”|(?<![\w])\'([^\'\n]+)\'(?![\w])', re.S)
WORD_NUM = dict(one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, twenty=20, fifty=50, hundred=100)


def q(text):
    return shlex.quote(text)


def put(path, content, append=False):
    """Write exact text (a trailing newline is added if missing) through base64."""
    if content and not content.endswith('\n'):
        content += '\n'
    blob = base64.b64encode(content.encode()).decode()
    arrow = '>>' if append else '>'
    folder = f'mkdir -p "$(dirname {q(path)})" && '
    return [folder + f"printf '%s' {blob} | base64 -d {arrow} {q(path)}",
            folder + f"python3 -c \"import base64,sys;open(sys.argv[1],'{'a' if append else 'w'}').write(base64.b64decode(sys.argv[2]).decode())\" {q(path)} {blob}"]


def paths(text, dirs=True):
    """Paths in order of appearance: absolute, relative with a slash, name.ext, and named directories."""
    found = []
    quoted_spans = [m.span() for m in QUOTE.finditer(text)]
    for m in PATH.finditer(text):
        p = (m[1] or m[2] or m[3]).strip().rstrip('.')
        if m[1] and (' ' in p or not re.search(r'[/.]', p)):
            continue          # `ls -la` and similar are commands, not paths
        if any(a <= m.start() < b for a, b in quoted_spans) and not m[1]:
            continue          # inside text to be written, not a path
        if NOT_FILE.match(p) or re.match(r'https?:', p) or '://' in text[max(0, m.start() - 8):m.start()]:
            continue
        found.append((m.start(), p))
    if dirs:
        for m in DIR_NAME.finditer(text):
            name = m[1] or m[2]
            if name and name.lower() not in DIR_WORDS and not any(name == p or p.startswith(name + '/') for _, p in found):
                found.append((m.start(1) if m[1] else m.start(2), name))
    out = []
    for _, p in sorted(found):
        if p not in out:
            out.append(p)
    return out


def quotes(text):
    return [next(g for g in m.groups() if g is not None) for m in QUOTE.finditer(text)]


def urls(text):
    return re.findall(r'https?://[^\s\'"`<>)]+[^\s\'"`<>).,]', text)


def sentences(text):
    """Split into sentences without breaking file names (a.txt) or code blocks."""
    parts, buf, fence = [], [], False
    for line in text.splitlines():
        if line.strip().startswith('```'):
            fence = not fence
        buf.append(line)
        if not fence and not line.strip():
            parts.append('\n'.join(buf)); buf = []
    parts.append('\n'.join(buf))
    out = []
    for part in parts:
        if '```' in part:
            out.append(part.strip()); continue
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])|\n(?=\s*(?:[-*]|\d+[.)])\s)', part):
            if s.strip():
                out += clauses(s.strip())
    return out


VERBS = (r'create|write|make|sort|count|replace|delete|remove|rename|move|copy|run|execute|commit|install|add|append|save|'
         r'initiali[sz]e|init|extract|unzip|find|list|download|build|compile|chmod|archive|compress')
JOIN = re.compile(r'(?i)(?:,\s*(?:and\s+)?|\s+and\s+|;\s*)(?:then\s+)?(?=(?:(?:inside it|in it|in there|there)\s+)?(?:' + VERBS + r')\b)')
INSIDE = re.compile(r'(?i)^(?:inside it|in it|in there|there)\s+')
GOES_ON = re.compile(r'(?i)^(?:save|write|store|output|put|redirect)\b.*\b(?:result|output|it|them|list|answer|number|count|total|sum|value)\b')
STARTS_WITH_VERB = re.compile(r'(?i)^(?:please\s+)?(?:then\s+)?(?:' + VERBS + r')\b')


def clauses(sentence):
    """'Create X, then commit it' -> two tasks; 'Sort X, remove duplicates and save the result to Y' stays one."""
    if QUOTE.search(sentence) and '```' in sentence:
        return [sentence]
    pieces, last = [], 0
    for m in JOIN.finditer(sentence):
        if any(a < m.start() < b for a, b in (x.span() for x in QUOTE.finditer(sentence))):
            continue
        pieces.append(sentence[last:m.start()]); last = m.end()
    pieces.append(sentence[last:])
    out, lead = [], ''
    for p in pieces:
        p = p.strip().rstrip(',;')
        merged = bool(lead)
        if lead:
            p, lead = lead + ', ' + p, ''
        if not merged and not out and not STARTS_WITH_VERB.match(p) and p != pieces[-1].strip().rstrip(',;'):
            lead = p                      # "In notes.md, replace ..." : the lead-in belongs to the next step
            continue
        if out and (GOES_ON.match(p) or not (paths(p) or quotes(p) or re.search(r'(?i)\b(?:git|repository|repo|commit)\b', p))):
            out[-1] += ', ' + p           # a step with nothing of its own continues the one before
        else:
            out.append(p)
    return out


def number(text, default=None):
    m = re.search(r'\b(\d+)\b', text)
    if m:
        return int(m[1])
    for w, n in WORD_NUM.items():
        if re.search(r'\b' + w + r'\b', text, re.I):
            return n
    return default


def content_of(sentence):
    """The text a sentence asks to write: a quote or code block, else the words after 'containing'."""
    if '```' in sentence:
        return max(quotes(sentence), key=len)
    m = re.search(r'(?i)\b(?:containing|contains|with the (?:text|content|contents|line|word|words)|with (?:text|content|contents))\s*:?\s*(?:the (?:text|line|word|words)\s+)?(.+?)\s*$', sentence)
    if m:
        text = m[1]
        text = re.sub(r'\s+(?:in it|inside|as (?:its|the) (?:content|contents|text))\.?$', '', text)
        if not re.search(r'[\]})"\']$', text):
            text = text.rstrip('.')
        whole = QUOTE.fullmatch(text.strip())
        return next(g for g in whole.groups() if g is not None) if whole else text
    found = quotes(sentence)
    if found:
        return found[0]
    return None


# ---------------------------------------------------------------- recipes
# Each recipe: (name, pattern, builder(sentence, match, ctx) -> list of steps or None)

def step(kind, why, tries, check=None):
    return dict(kind=kind, why=why, tries=[t for t in tries if t], check=check)


def r_write(s, m, ctx):
    ps = paths(s)
    text = content_of(s)
    if text is None:
        bare = re.search(r'(?i)\b(?:the\s+)?(?:word|text|string|number|value)\s+`?([^\s`]+?)`?\s+(?:in|into|to)\b', s)
        text = bare[1] if bare else None
    if not ps or text is None:
        return None
    if INSIDE.match(s) and ctx.get('last_dir') and '/' not in ps[0]:
        ps = [ctx['last_dir'].rstrip('/') + '/' + p for p in ps]    # "... and inside it create notes.txt"
    target = ps[-1] if re.search(r'(?i)\b(?:to|into|in)\s+(?:a |the )?(?:new )?(?:file )?(?:called |named )?`?' + re.escape(ps[-1]), s) else ps[0]
    append = bool(re.search(r'(?i)\bappend|\badd (?:a |the )?line\b|\bat the end\b', s))
    return [step('write', f'write the given text to {target}', put(target, text, append),
                 f'grep -qF -- {q(text.splitlines()[0] if text.strip() else text)} {q(target)}' if text.strip() else f'test -e {q(target)}')]


def r_mkdir(s, m, ctx):
    named = [x for pair in DIR_NAME.findall(s) for x in pair if x and x.lower() not in DIR_WORDS]
    ps = named or [p for p in paths(s) if not re.search(r'\.\w{1,5}$', p)]
    if not ps:
        return None
    ctx['last_dir'] = ps[-1]
    return [step('mkdir', f'create directory {p}', [f'mkdir -p {q(p)}'], f'test -d {q(p)}') for p in ps]


def r_copy_move(s, m, ctx):
    ps = paths(s)
    if len(ps) < 2:
        bare = re.search(r'(?i)\b(?:copy|move|rename)\s+(?:the\s+)?(?:file|directory|folder|dir)?\s*`?([\w./\-]+)`?\s+(?:to|as|into)\s+`?([\w./\-]+?)`?\.?$', s)
        if not bare:
            return None
        ps = [bare[1], bare[2]]
    verb = m[1].lower()
    src, dst = ps[0], ps[1]
    if re.search(r'(?i)\binto\s+(?:a\s+|the\s+)?(?:new\s+)?(?:folder|directory|dir)\b', s) or dst.endswith('/'):
        dst = dst.rstrip('/') + '/' + src.rstrip('/').rsplit('/', 1)[-1]     # "move X into a folder called final"
    if verb == 'copy':
        return [step('copy', f'copy {src} to {dst}', [f'mkdir -p "$(dirname {q(dst)})" && cp -r {q(src)} {q(dst)}'], f'test -e {q(dst)}')]
    return [step('move', f'move {src} to {dst}', [f'mkdir -p "$(dirname {q(dst)})" && mv {q(src)} {q(dst)}'], f'test -e {q(dst)} && test ! -e {q(src)}')]


def r_delete(s, m, ctx):
    ps = paths(s)
    if not ps:
        return None
    return [step('delete', f'delete {p}', [f'rm -rf -- {q(p)}'], f'test ! -e {q(p)}') for p in ps if p not in ('/', '.', '~')]


def r_chmod(s, m, ctx):
    ps = paths(s)
    return [step('chmod', f'make {p} executable', [f'chmod +x {q(p)}'], f'test -x {q(p)}') for p in ps] or None


def r_pip(s, m, ctx):
    names = [n for n in re.split(r'[,\s]+(?:and\s+)?', m[2]) if re.fullmatch(r'[A-Za-z0-9_.\-\[\]=<>]+', n) and n.lower() not in ('and', 'the', 'package', 'packages', 'library', 'python')]
    if not names:
        return None
    pkgs = ' '.join(q(n) for n in names)
    module = re.split(r'[\[=<>]', names[0])[0].replace('-', '_')
    return [step('pip', f'install python packages {", ".join(names)}',
                 [f'pip install {pkgs}', f'pip3 install {pkgs}', f'python3 -m pip install {pkgs}',
                  f'python3 -m pip install --break-system-packages {pkgs}', f'uv pip install --system {pkgs}'],
                 f'python3 -c "import {module}" || pip show {q(names[0])}')]


def r_apt(s, m, ctx):
    names = [n for n in re.split(r'[,\s]+(?:and\s+)?', m[1]) if re.fullmatch(r'[a-z0-9][a-z0-9+.\-]+', n) and n not in ('and', 'the', 'tool', 'tools', 'package', 'packages', 'program', 'system')]
    if not names:
        return None
    pkgs = ' '.join(names)
    return [step('apt', f'install system packages {pkgs}',
                 [f'(apt-get update && apt-get install -y {pkgs})', f'(sudo apt-get update && sudo apt-get install -y {pkgs})',
                  f'apk add --no-cache {pkgs}', f'(yum install -y {pkgs})', f'(dnf install -y {pkgs})'],
                 f'command -v {q(names[0])} || dpkg -s {q(names[0])}')]


def r_replace(s, m, ctx):
    qs, ps = quotes(s), paths(s)
    if len(qs) < 2 or not ps:
        return None
    old, new = qs[0], qs[1]
    out = []
    for p in ps:
        code = ("import sys;p=sys.argv[1];t=open(p).read();open(p,'w').write(t.replace(sys.argv[2],sys.argv[3]))")
        out.append(step('replace', f'replace {old!r} with {new!r} in {p}', [f'python3 -c {q(code)} {q(p)} {q(old)} {q(new)}',
                                                                              f"perl -0pi -e 's/\\Q'{q(old)}'\\E/'{q(new)}'/g' {q(p)}"],
                        f'! grep -qF -- {q(old)} {q(p)}' if old not in new else None))
    return out


def r_count(s, m, ctx):
    ps = paths(s)
    if len(ps) < 2:
        return None
    flag = {'line': '-l', 'word': '-w', 'character': '-m', 'char': '-m', 'byte': '-c'}[m[1].lower().rstrip('s')]
    src, dst = ps[0], ps[-1]
    return [step('count', f'count {m[1]} in {src} into {dst}', [f'wc {flag} < {q(src)} | tr -d " " > {q(dst)}'], f'test -s {q(dst)}')]


def r_sort(s, m, ctx):
    ps = paths(s)
    if not ps:
        return None
    flags = ''
    if re.search(r'(?i)numeric|numerical|by number|as numbers', s):
        flags += 'n'
    if re.search(r'(?i)reverse|descending|largest first|highest first', s):
        flags += 'r'
    if re.search(r'(?i)unique|duplicates?|distinct', s):
        flags += 'u'
    src, dst = ps[0], ps[-1]
    return [step('sort', f'sort {src} into {dst}', [f'sort {"-" + flags if flags else ""} {q(src)} -o {q(dst)}'], f'test -e {q(dst)}')]


def r_dedupe(s, m, ctx):
    ps = paths(s)
    if not ps:
        return None
    src, dst = ps[0], ps[-1]
    code = "import sys;s=set();o=[l for l in open(sys.argv[1],'rb') if not (l in s or s.add(l))];open(sys.argv[2],'wb').writelines(o)"
    return [step('dedupe', f'remove duplicate lines of {src} into {dst}', [f'python3 -c {q(code)} {q(src)} {q(dst)}', f"awk '!seen[$0]++' {q(src)} > {q(dst)}.tmp && mv {q(dst)}.tmp {q(dst)}"], f'test -e {q(dst)}')]


def r_head_tail(s, m, ctx):
    ps = paths(s)
    n = number(s, 10)
    if len(ps) < 2:
        return None
    tool = 'head' if m[1].lower() == 'first' else 'tail'
    return [step(tool, f'{m[1]} {n} lines of {ps[0]} into {ps[-1]}', [f'{tool} -n {n} {q(ps[0])} > {q(ps[-1])}'], f'test -e {q(ps[-1])}')]


def r_extract(s, m, ctx):
    ps = paths(s)
    if not ps:
        return None
    src = ps[0]
    dst = ps[1] if len(ps) > 1 else '.'
    return [step('extract', f'extract {src} into {dst}',
                 [f'mkdir -p {q(dst)} && tar -xf {q(src)} -C {q(dst)}', f'mkdir -p {q(dst)} && unzip -o {q(src)} -d {q(dst)}',
                  f'mkdir -p {q(dst)} && python3 -c "import shutil,sys;shutil.unpack_archive(sys.argv[1],sys.argv[2])" {q(src)} {q(dst)}',
                  f'gunzip -k {q(src)}'], None)]


def r_archive(s, m, ctx):
    ps = paths(s)
    if len(ps) < 2:
        return None
    dst = next((p for p in ps if re.search(r'\.(?:tar\.gz|tgz|zip|tar)$', p)), ps[-1])
    srcs = [p for p in ps if p != dst]
    if dst.endswith('.zip'):
        tries = [f'zip -r {q(dst)} ' + ' '.join(q(p) for p in srcs),
                 'python3 -c "import zipfile,sys,os\nz=zipfile.ZipFile(sys.argv[1],\'w\')\nfor p in sys.argv[2:]:\n for r,_,fs in (os.walk(p) if os.path.isdir(p) else [(os.path.dirname(p) or \'.\',0,[os.path.basename(p)])]):\n  [z.write(os.path.join(r,f)) for f in fs]" ' + q(dst) + ' ' + ' '.join(q(p) for p in srcs)]
    else:
        mode = 'czf' if dst.endswith(('gz', 'tgz')) else 'cf'
        tries = [f'tar -{mode} {q(dst)} ' + ' '.join(q(p) for p in srcs)]
    return [step('archive', f'archive {", ".join(srcs)} into {dst}', tries, f'test -s {q(dst)}')]


def r_run(s, m, ctx):
    ps = paths(s)
    script = next((p for p in ps if re.search(r'\.(?:py|sh|js|rb|pl)$', p)), None)
    if script is None:
        return None
    runner = {'.py': 'python3', '.sh': 'bash', '.js': 'node', '.rb': 'ruby', '.pl': 'perl'}[re.search(r'\.\w+$', script)[0]]
    out = next((p for p in ps if p != script), None)
    save = out and re.search(r'(?i)\b(?:save|write|redirect|store|put)\b.*\boutput\b|\boutput\b.*\b(?:to|into|in)\b', s)
    cmd = f'{runner} {q(script)}' + (f' > {q(out)}' if save else '')
    alt = cmd.replace('python3 ', 'python ', 1) if runner == 'python3' else None
    return [step('run', f'run {script}' + (f' saving output to {out}' if save else ''), [cmd, alt], f'test -e {q(out)}' if save else None)]


def r_download(s, m, ctx):
    found, ps = urls(s), [p for p in paths(s) if not p.startswith('//')]
    if not found:
        return None
    dst = next((p for p in ps if p not in found[0]), None) or found[0].rstrip('/').rsplit('/', 1)[-1] or 'download'
    return [step('download', f'download {found[0]} to {dst}',
                 [f'curl -fsSL -o {q(dst)} {q(found[0])}', f'wget -q -O {q(dst)} {q(found[0])}',
                  f'python3 -c "import urllib.request,sys;urllib.request.urlretrieve(sys.argv[1],sys.argv[2])" {q(found[0])} {q(dst)}'],
                 f'test -s {q(dst)}')]


def r_find(s, m, ctx):
    ps = paths(s)
    ext = re.search(r'(?i)(?:\.|extension\s+\.?)(\w{1,5})\b(?:\s+files?)?', s.split(' to ')[0])
    dst = ps[-1] if ps else None
    where = next((p for p in ps[:-1] if not re.search(r'\.\w+$', p)), '.')
    if not ext or not dst:
        return None
    return [step('find', f'list *.{ext[1]} files under {where} into {dst}', [f'find {q(where)} -type f -name {q("*." + ext[1])} | sort > {q(dst)}'], f'test -e {q(dst)}')]


def r_git(s, m, ctx):
    low = s.lower()
    out = []
    if re.search(r'\binit(?:iali[sz]e)?\b', low):
        out.append(step('git', 'initialise a git repository', ['git init'], 'git rev-parse --git-dir'))
    br = re.search(r'(?i)\bbranch\s+(?:called |named )?`?([\w./\-]+)', s)
    if br:
        out.append(step('git', f'create branch {br[1]}', [f'git checkout -b {q(br[1])}', f'git switch -c {q(br[1])}', f'git checkout {q(br[1])}'],
                        f'git rev-parse --verify {q(br[1])}'))
    if re.search(r'\bcommit\b', low):
        msg = (quotes(s) or ['Commit by CAEL'])[0]
        out.append(step('git', f'commit with message {msg!r}', [f'git add -A && git -c user.name=cael -c user.email=cael@localhost commit -m {q(msg)}'],
                        'git log -1 --oneline'))
    return out or None


def r_build(s, m, ctx):
    return [step('build', 'build the project with what is there',
                 ['test -f Makefile && make', 'test -f CMakeLists.txt && mkdir -p build && cd build && cmake .. && make',
                  'test -f package.json && (npm install && npm run build)', 'test -f Cargo.toml && cargo build --release',
                  'test -f setup.py && pip install -e .', 'test -f pyproject.toml && pip install -e .', 'test -f go.mod && go build ./...'], None)]


RECIPES = [
    ('download', re.compile(r'(?i)\b(?:download|fetch|retrieve)\b.*https?://'), r_download),
    ('pip', re.compile(r'(?i)\binstall\b(?:\s+the)?\s+(python\s+(?:packages?|librar(?:y|ies)|modules?)|pip\s+packages?|packages?|librar(?:y|ies))\s+([\w.\-\[\]=<>, ]+?)(?:\s+(?:using|with|via|for|so|in)\b|[.;]|$)'), r_pip),
    ('apt', re.compile(r'(?i)\binstall\b(?:\s+the)?\s+(?:system\s+packages?|apt\s+packages?|tools?|programs?|utilit(?:y|ies))\s+([\w.+\-, ]+?)(?:\s+(?:using|with|via|so)\b|[.;]|$)'), r_apt),
    ('extract', re.compile(r'(?i)\b(?:extract|unzip|untar|decompress|unpack)\b'), r_extract),
    ('archive', re.compile(r'(?i)\b(?:compress|archive|tar up|zip up|create (?:an? )?(?:archive|tarball|zip))\b'), r_archive),
    ('count', re.compile(r'(?i)\bcount\b.*?\b(lines|words|characters|chars|bytes)\b'), r_count),
    ('dedupe', re.compile(r'(?i)\bremove\b.*\bduplicate\b(?!.*\bsort)'), r_dedupe),
    ('sort', re.compile(r'(?i)\bsort\b'), r_sort),
    ('head_tail', re.compile(r'(?i)\b(first|last)\s+(?:\d+|\w+)\s+lines\b'), r_head_tail),
    ('replace', re.compile(r'(?i)\breplac(?:e|es|ing)\b|\bsubstitut(?:e|ing)\b'), r_replace),
    ('find', re.compile(r'(?i)\b(?:find|list|locate)\b.*\bfiles?\b.*\b(?:write|save|output|list)\b'), r_find),
    ('git', re.compile(r'(?i)\bgit\b|\bcommit\b|\brepository\b|\brepo\b'), r_git),
    ('chmod', re.compile(r'(?i)\bmake\b.*\bexecutable\b|\bchmod\b'), r_chmod),
    ('copy_move', re.compile(r'(?i)\b(copy|move|rename)\b'), r_copy_move),
    ('delete', re.compile(r'(?i)\b(?:delete|remove)\b(?!.*\bduplicate)'), r_delete),
    ('mkdir', re.compile(r'(?i)\b(?:create|make)\b\s+(?:a\s+|the\s+|an\s+empty\s+|empty\s+)?(?:new\s+)?(?:directory|folder|dir)\b'), r_mkdir),
    ('run', re.compile(r'(?i)\b(?:run|execute)\b'), r_run),
    ('build', re.compile(r'(?i)\b(?:build|compile)\b\s+(?:the\s+)?(?:project|code|program|repo|repository)\b'), r_build),
    ('write', re.compile(r'(?i)\b(?:create|write|make|save|put|append|add|generate)\b'), r_write),
]


def plan(instruction, ctx=None):
    """Steps for the whole instruction, in order, with the recipe each came from."""
    ctx = ctx or {}
    steps, carried = [], ''
    for s in sentences(instruction):
        if carried:
            s, carried = carried + ' ' + s, ''
        if s.endswith('?') and not any(p.search(s) and b(s, p.search(s), dict(ctx)) for _, p, b in RECIPES):
            carried = s                   # "How many words are in a.txt? Count them and ..." : the question sets the scene
            continue
        for name, pattern, build in RECIPES:
            m = pattern.search(s)
            if not m:
                continue
            got = build(s, m, ctx)
            if got:
                for st in got:
                    st['recipe'], st['sentence'] = name, s
                steps += got
                break
    return steps
