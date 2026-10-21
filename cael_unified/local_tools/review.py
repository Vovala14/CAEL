"""Owner-local, hash-bound manual review queue. Decisions never alter media."""
from datetime import datetime,timezone
import hashlib
import json
import os
import sqlite3
import uuid

from .workspace import Workspace,ToolError,reparse


def now():return datetime.now(timezone.utc).isoformat()


class ReviewQueue:
    def __init__(self,workspace):
        self.workspace=workspace;self.directory=workspace.root/'.cael-tools'
        if self.directory.exists() and (reparse(self.directory) or not self.directory.is_dir()):raise ToolError('Invalid owner state directory')
        self.directory.mkdir(mode=0o700,exist_ok=True);self.assets=self.directory/'assets'
        if self.assets.exists() and (reparse(self.assets) or not self.assets.is_dir()):raise ToolError('Invalid asset store')
        self.assets.mkdir(mode=0o700,exist_ok=True);self.database=self.directory/'review.sqlite'
        if self.database.exists() and (reparse(self.database) or not self.database.is_file()):raise ToolError('Invalid review database')
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS assets (
              id TEXT PRIMARY KEY, upload_ref TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
              bytes INTEGER NOT NULL, assessment TEXT NOT NULL, priority INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending', action TEXT, revision INTEGER NOT NULL DEFAULT 0,
              created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(upload_ref,sha256));
              CREATE TABLE IF NOT EXISTS decisions (
              id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, sha256 TEXT NOT NULL, action TEXT NOT NULL,
              reviewer TEXT NOT NULL, reason TEXT NOT NULL, revision INTEGER NOT NULL, created TEXT NOT NULL);''')

    def connect(self):
        db=sqlite3.connect(self.database,timeout=10);db.row_factory=sqlite3.Row;return db

    def enqueue(self,name,upload_ref=None):
        blob=self.workspace.bytes(name,50_000_000);sha=hashlib.sha256(blob).hexdigest();upload_ref=upload_ref or name
        if not isinstance(upload_ref,str) or not 1<=len(upload_ref)<=200:raise ToolError('Upload reference must be 1..200 characters')
        # Snapshot before decoding: decisions attach to these immutable bytes.
        snapshot=self.assets/sha
        try:
            fd=os.open(snapshot,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(blob)
        except FileExistsError:
            if reparse(snapshot) or hashlib.sha256(snapshot.read_bytes()).hexdigest()!=sha:raise ToolError('Asset snapshot integrity mismatch')
        with self.connect() as db:
            existing=db.execute('SELECT id FROM assets WHERE upload_ref=? AND sha256=?',(upload_ref,sha)).fetchone()
        if existing:return self.get(existing['id'])
        try:
            from .process import analyze
            suffix=self.workspace.path(name).suffix.lower();kind='video' if suffix in {'.mp4','.mov','.mkv','.webm','.avi'} else 'image'
            assessed=analyze(kind,blob,{})
        except (ToolError,OSError,ValueError) as error:
            assessed=dict(status='unreadable',error=str(error)[:300],priority='unknown',requires_human_review=True,
                          suspected_nsfw=None,auto_approved=False,auto_blurred=False,moderation_complete=False)
        identity=uuid.uuid4().hex;stamp=now();priority={'elevated':2,'unknown':1,'normal':0}.get(assessed.get('priority'),1)
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO assets (id,upload_ref,path,sha256,bytes,assessment,priority,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                       (identity,upload_ref,name,sha,len(blob),json.dumps(assessed),priority,stamp,stamp))
            row=db.execute('SELECT id FROM assets WHERE upload_ref=? AND sha256=?',(upload_ref,sha)).fetchone()
        return self.get(row['id'])

    def get(self,identity):
        if not isinstance(identity,str) or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):raise ToolError('Invalid review item ID')
        with self.connect() as db:row=db.execute('SELECT * FROM assets WHERE id=?',(identity,)).fetchone()
        if row is None:raise ToolError('Review item not found')
        result=dict(row);result['assessment']=json.loads(result['assessment']);result['effect_applied']=False
        result['requires_human_review']=result['status']=='pending';return result

    def pending(self,limit=100):
        if type(limit) is not int or not 1<=limit<=200:raise ToolError('Queue limit must be 1..200')
        with self.connect() as db:rows=db.execute("SELECT id FROM assets WHERE status='pending' ORDER BY priority DESC,created,id LIMIT ?",(limit,)).fetchall()
        return [self.get(row['id']) for row in rows]

    def decide(self,identity,action,reviewer,expected_revision,reason=''):
        if action not in {'allow','blur','reject','defer'}:raise ToolError('Choose allow, blur, reject or defer')
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>100:raise ToolError('A reviewer identity is required')
        if type(expected_revision) is not int or expected_revision<0:raise ToolError('Use the current integer revision')
        if not isinstance(reason,str) or len(reason)>1000:raise ToolError('Review reason too long')
        current=self.get(identity);snapshot=self.assets/current['sha256']
        if reparse(snapshot) or hashlib.sha256(snapshot.read_bytes()).hexdigest()!=current['sha256']:raise ToolError('Asset changed; do not apply a stale decision')
        revision=expected_revision+1;stamp=now()
        with self.connect() as db:
            cursor=db.execute('UPDATE assets SET status=?,action=?,revision=?,updated=? WHERE id=? AND revision=?',
                              ('pending' if action=='defer' else 'reviewed',None if action=='defer' else action,revision,stamp,identity,expected_revision))
            if cursor.rowcount!=1:raise ToolError('Review revision changed; reload before deciding')
            db.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,identity,current['sha256'],action,reviewer,reason,revision,stamp))
        return self.get(identity)

    def history(self,identity):
        self.get(identity)
        with self.connect() as db:return [dict(row) for row in db.execute('SELECT * FROM decisions WHERE asset_id=? ORDER BY revision',(identity,))]
