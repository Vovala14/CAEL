"""Explicit-root file capabilities, bounded traversal/read, exclusive creation."""
import fnmatch
import hashlib
import os
from pathlib import Path,PureWindowsPath
import stat


class ToolError(ValueError): pass


def reparse(path):
    info=path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&0x400)


class Workspace:
    def __init__(self,root):
        given=Path(root).absolute()
        if not given.is_dir() or reparse(given):raise ToolError('Workspace must be an existing ordinary directory')
        # A linked ancestor is also an ambiguous authority boundary.
        if any(reparse(p) for p in given.parents):raise ToolError('Linked workspace ancestors are not allowed')
        self.root=given.resolve()

    @staticmethod
    def relative(name):
        if not isinstance(name,str) or not name or len(name)>500 or '\x00' in name:raise ToolError('Use a nonempty relative workspace path')
        normalized=name.replace('\\','/');win=PureWindowsPath(name)
        if win.is_absolute() or win.drive or normalized.startswith('/') or ':' in normalized:raise ToolError('Absolute, device, network and stream paths are forbidden')
        parts=normalized.split('/')
        reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
        if any(not p or p in {'.','..'} or p.startswith('.') or p.rstrip(' .')!=p or p.split('.')[0].upper() in reserved for p in parts):raise ToolError('Hidden, traversal or reserved path component')
        return parts

    def path(self,name,existing=True):
        parts=self.relative(name);candidate=self.root.joinpath(*parts)
        current=self.root
        for part in parts:
            current=current/part
            if current.exists() or current.is_symlink():
                if reparse(current):raise ToolError('Links/reparse points are forbidden')
        resolved=candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):raise ToolError('Path escaped the workspace')
        if existing and not candidate.is_file():raise ToolError('Workspace file not found')
        return candidate

    def bytes(self,name,limit=2_000_000):
        path=self.path(name)
        if path.stat().st_size>limit:raise ToolError('File exceeds the operation byte limit')
        flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
        fd=os.open(path,flags)
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ToolError('Expected an ordinary file')
            if os.name=='nt':
                import ctypes,msvcrt
                from ctypes import wintypes
                fn=ctypes.windll.kernel32.GetFinalPathNameByHandleW
                fn.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD];fn.restype=wintypes.DWORD
                buffer=ctypes.create_unicode_buffer(32768);length=fn(msvcrt.get_osfhandle(stream.fileno()),buffer,len(buffer),0)
                if not length or length>=len(buffer):raise ToolError('Cannot verify opened file authority')
                final=buffer.value.removeprefix('\\\\?\\')
                if not Path(final).resolve().is_relative_to(self.root):raise ToolError('Opened file escaped workspace')
            blob=stream.read(limit+1)
        if len(blob)>limit:raise ToolError('File grew beyond byte limit')
        return blob

    def read(self,name,max_bytes=131072):
        if type(max_bytes) is not int or not 1<=max_bytes<=1_000_000:raise ToolError('Read limit must be 1..1000000 bytes')
        blob=self.bytes(name,max_bytes)
        try:text=blob.decode('utf-8-sig')
        except UnicodeDecodeError:raise ToolError('File is not UTF-8 text; binary content was not returned')
        if '\x00' in text:raise ToolError('Binary content is not a text document')
        return dict(path=name,text=text,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),truncated=False)

    def touch(self,name):
        path=self.path(name,existing=False)
        if not path.parent.is_dir():raise ToolError('Parent directory must already exist')
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600);os.close(fd)
            created=True
        except FileExistsError:
            self.path(name);created=False
        return dict(path=name,created=created,existing_content_unchanged=not created,timestamps_changed=created)

    @staticmethod
    def pattern(pattern):
        if not isinstance(pattern,str) or len(pattern)>200 or not pattern or '\\' in pattern or ':' in pattern or pattern.startswith('/') or any(p.startswith('.') for p in pattern.split('/')):raise ToolError('Use a relative glob without hidden/traversal components')
        return pattern

    def find(self,pattern='*',limit=100,max_visited=2000):
        self.pattern(pattern)
        if type(limit) is not int or not 1<=limit<=200:raise ToolError('Find result limit must be 1..200')
        if type(max_visited) is not int or not 1<=max_visited<=10000:raise ToolError('Find visit limit must be 1..10000')
        pending=[(self.root,0)];found=[];visited=0;truncated=False
        while pending:
            directory,depth=pending.pop()
            if reparse(directory) or not directory.resolve().is_relative_to(self.root):continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited+=1
                    if visited>max_visited:truncated=True;break
                    if entry.name.startswith('.') or reparse(Path(entry.path)):continue
                    if entry.is_dir(follow_symlinks=False):
                        if depth<12:pending.append((Path(entry.path),depth+1))
                        else:truncated=True
                    elif entry.is_file(follow_symlinks=False):
                        relative=Path(entry.path).relative_to(self.root).as_posix()
                        try:self.path(relative)
                        except ToolError:continue
                        match=fnmatch.fnmatchcase(relative,pattern) if '/' in pattern else fnmatch.fnmatchcase(entry.name,pattern)
                        if match:
                            found.append(dict(path=relative,bytes=entry.stat(follow_symlinks=False).st_size))
                            if len(found)>=limit:truncated=True;break
            if visited>max_visited or len(found)>=limit:break
        return dict(files=sorted(found,key=lambda r:r['path']),truncated=truncated,visited=min(visited,max_visited),links_and_hidden_skipped=True)

    def pdf(self,name,pages=20):
        from .process import analyze
        return analyze('pdf',self.bytes(name,20_000_000),dict(pages=pages))

    def inspect_media(self,name):
        from .process import analyze
        path=self.path(name);video=path.suffix.lower() in {'.mp4','.mov','.mkv','.webm','.avi'}
        return analyze('video' if video else 'image',self.bytes(name,50_000_000 if video else 20_000_000),{})

    def run_plan(self,plan):
        from .plans import execute
        return execute(self,plan)
