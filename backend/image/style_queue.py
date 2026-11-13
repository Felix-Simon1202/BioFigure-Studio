"""Durable, bounded local presentation jobs; source data and labels stay intact."""
from __future__ import annotations
import atexit
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import multiprocessing as mp
import os
import subprocess
import sys
from pathlib import Path
import sqlite3
from threading import Event, RLock, Thread
from time import time, monotonic
from uuid import uuid4
import zipfile
from xml.sax.saxutils import escape

from backend.image.paths import image_work_dir
from backend.image.storage import require_disk_space

MAX_ITEMS=100
MAX_INPUT_BYTES=64*1024*1024
MAX_DISK_BYTES=1024*1024*1024
MAX_PIXELS=16_000_000
JOB_SECONDS=120
STYLES={
    'clean':{'background':'#ffffff','border':'#dce1e8','ink':'#253247','margin':32,'font_size':20},
    'soft':{'background':'#f6f7fa','border':'#d2d9e6','ink':'#45516a','margin':48,'font_size':20},
    'contrast':{'background':'#ffffff','border':'#374151','ink':'#17202e','margin':32,'font_size':22},
}


def digest_file(path:Path)->str:
    value=sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


class QueueInputError(ValueError):pass


def frozen_worker():
    """Fixed local worker protocol; no inherited Python process handles required."""
    payload=json.loads(sys.stdin.buffer.read(8193))
    if set(payload)!={'id','sha256','label','style','parameters'}:raise ValueError('Invalid worker payload')
    identifier=payload['id']
    if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid worker id')
    if payload['style'] not in STYLES:raise ValueError('Invalid worker style')
    parameters=payload['parameters']
    import re
    if set(parameters)!={'background','border','ink','margin','font_size'}:raise ValueError('Invalid style snapshot')
    if any(not isinstance(parameters[k],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',parameters[k]) for k in ('background','border','ink')):raise ValueError('Invalid style color')
    if any(type(parameters[k]) is not int or not 1<=parameters[k]<=128 for k in ('margin','font_size')):raise ValueError('Invalid style dimensions')
    if not isinstance(payload['label'],str) or len(payload['label'])>200:raise ValueError('Invalid worker label')
    if not isinstance(payload['sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',payload['sha256']):raise ValueError('Invalid source digest')
    root=image_work_dir('image-style-queue')
    render_presentation(str(root/(identifier+'.source')),str(root/(identifier+'.zip')),str(root/(identifier+'.report')),
                        payload['sha256'],payload['label'],payload['style'],parameters)


class FrozenPresentationProcess:
    """Expose the small worker lifecycle used by the existing bounded coordinator."""
    def __init__(self,payload):self.payload=payload;self.process=None
    def start(self):
        self.process=subprocess.Popen([sys.executable,'--image-presentation-worker'],stdin=subprocess.PIPE,
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            self.process.stdin.write(json.dumps(self.payload,ensure_ascii=False).encode('utf-8'))
            self.process.stdin.close()
        except BaseException:
            self.terminate();self.process.wait(timeout=5);raise
    def is_alive(self):return self.process is not None and self.process.poll() is None
    def join(self,timeout):
        if self.process is not None:
            try:self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:pass
    def terminate(self):
        if self.is_alive():self.process.terminate()
    def close(self):
        if self.process is not None:self.process.wait(timeout=5)


def render_presentation(source:str,output:str,report:str,expected:str,label:str,style_id:str,parameters=None):
    """One isolated process, no filesystem input provided by a model or HTTP path."""
    import base64
    import warnings
    from PIL import Image
    source_path=Path(source);target=Path(output);part=target.with_suffix('.part')
    try:
        if digest_file(source_path)!=expected:raise QueueInputError('Source integrity check failed.')
        Image.MAX_IMAGE_PIXELS=MAX_PIXELS
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(source_path) as image:
            width,height=image.size
            if width*height>MAX_PIXELS or max(width,height)>20000:raise QueueInputError('Image exceeds the presentation pixel limit.')
            if getattr(image,'n_frames',1)!=1:raise QueueInputError('Select a single image plane; stacks and animations are not flattened.')
            if image.getexif().get(274,1)!=1:raise QueueInputError('Resolve image orientation explicitly before queue submission.')
            if image.format not in {'PNG','JPEG','TIFF'} or image.mode not in {'L','RGB','RGBA','P'}:
                raise QueueInputError('Use PNG, RGB JPEG, or a single-plane 8-bit TIFF.')
            image.load()
            source_format=image.format
            if image.format=='TIFF':
                bits=image.tag_v2.get(258,(8,))
                if isinstance(bits,int):bits=(bits,)
                if any(bit>8 for bit in bits):raise QueueInputError('High-bit-depth TIFF is retained as source only; no automatic display conversion.')
                converted=BytesIO();image.save(converted,format='PNG');embedded=converted.getvalue()
                with Image.open(BytesIO(embedded)) as check:
                    if check.convert('RGBA').tobytes()!=image.convert('RGBA').tobytes():
                        raise QueueInputError('Lossless TIFF display verification failed.')
                media='image/png';conversion='8-bit TIFF to PNG; decoded RGBA pixels verified'
            else:
                embedded=source_path.read_bytes();media='image/png' if image.format=='PNG' else 'image/jpeg';conversion='original encoded image bytes'
        style=parameters or STYLES[style_id];margin=style['margin'];font=style['font_size']
        # Caption is separate from the embedded pixels. Existing raster labels are never edited.
        # Long original filenames wrap without truncation or textual replacement.
        line_length=max(1,int(width/(font*.65)))
        lines=[label[i:i+line_length] for i in range(0,len(label),line_length)] or ['']
        caption_height=(len(lines)+1)*(font+6)
        out_width=width+2*margin;out_height=height+2*margin+caption_height
        caption=''.join(f'<text x="{margin}" y="{height+margin+font+12+i*(font+6)}" font-size="{font}" fill="{style["ink"]}">{escape(line)}</text>' for i,line in enumerate(lines))
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_width}" height="{out_height}" viewBox="0 0 {out_width} {out_height}"><title>{escape(label)}</title>'
             f'<rect width="100%" height="100%" fill="{style["background"]}"/>'
             f'<image x="{margin}" y="{margin}" width="{width}" height="{height}" href="data:{media};base64,{base64.b64encode(embedded).decode()}"/>'
             f'<rect x="{margin}" y="{margin}" width="{width}" height="{height}" fill="none" stroke="{style["border"]}" stroke-width="1"/>'
             f'<g font-family="Noto Sans SC,Arial,sans-serif">{caption}</g></svg>')
        manifest={'version':'1.0','style':style_id,'style_parameters':style,'source_name':label,
                  'source_sha256':expected,'source_format':source_format,'source_pixels':[width,height],
                  'source_data_changed':False,'embedded_labels_changed':False,'display_conversion':conversion,
                  'embedded_sha256':sha256(embedded).hexdigest(),'operations':['separate presentation background','separate border','separate filename caption'],
                  'scope':'Presentation wrapper only; measured image content and existing labels are not beautified or regenerated.'}
        if digest_file(source_path)!=expected:raise QueueInputError('Source integrity check failed.')
        with zipfile.ZipFile(part,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            archive.write(source_path,'source/original.'+{'PNG':'png','JPEG':'jpg','TIFF':'tiff'}[source_format],compress_type=zipfile.ZIP_STORED)
            archive.writestr('presentation.svg',svg)
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        if part.stat().st_size>192*1024*1024:raise QueueInputError('Derived output exceeds its bounded size limit.')
        part.replace(target)
        Path(report).write_text(json.dumps({'ok':True,'output_sha256':digest_file(target),'manifest':manifest}),encoding='utf-8')
    except BaseException as error:
        part.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        message=str(error) if isinstance(error,QueueInputError) else 'Image presentation failed; verify the format and retry.'
        Path(report).write_text(json.dumps({'ok':False,'error':message}),encoding='utf-8')


class StyleQueue:
    def __init__(self,root:Path,start=True):
        self.root=root.resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'queue.sqlite3';self.lock=RLock();self.stop=Event();self.wake=Event();self.thread=None;self._lease=None
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,name TEXT NOT NULL,style TEXT NOT NULL,style_json TEXT NOT NULL,state TEXT NOT NULL,source_sha256 TEXT NOT NULL,source_bytes INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,error TEXT,output_sha256 TEXT,created REAL NOT NULL,updated REAL NOT NULL)')
        if start:self.ensure_started()
        else:self._recover()

    def _recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state=CASE WHEN attempts<5 THEN 'queued' ELSE 'failed' END,error='Interrupted job recovered',updated=? WHERE state='running'",(time(),))
            db.execute("UPDATE jobs SET state='cancelled' WHERE state='cancel_requested'")
            known={row['id']:row['state'] for row in db.execute('SELECT id,state FROM jobs')}
        # Only queue-owned UUID files are cleaned, never caller filesystem paths.
        for item in self.root.iterdir():
            if not item.is_file():continue
            stem=item.stem
            if item.name.startswith('bundle-') and item.suffix=='.zip':
                candidate=stem[7:]
                if len(candidate)==32 and all(c in '0123456789abcdef' for c in candidate):item.unlink(missing_ok=True)
            elif len(stem)==32 and all(c in '0123456789abcdef' for c in stem):
                if item.suffix in {'.upload','.part','.report'} or item.suffix=='.source' and stem not in known or item.suffix=='.zip' and known.get(stem)!='done':
                    item.unlink(missing_ok=True)

    def ensure_started(self):
        with self.lock:
            if self.thread is not None or self.stop.is_set():return
            lease=(self.root/'coordinator.lock').open('a+b')
            try:
                if lease.seek(0,2)==0:lease.write(b'0');lease.flush()
                lease.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:
                lease.close();return # Another local app instance owns the single worker.
            self._lease=lease
            self._recover()
            self.thread=Thread(target=self._loop,name='image-style-queue',daemon=True);self.thread.start()
            atexit.register(self.close)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=5);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def path(self,identifier:str,suffix:str)->Path:
        if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid job identifier.')
        return self.root/(identifier+suffix)

    def _public(self,row):
        value=dict(row)
        value['style_parameters']=json.loads(value.pop('style_json'))
        value['download_available']=value['state']=='done' and self.path(value['id'],'.zip').is_file()
        return value

    def list(self):
        with self.connect() as db:return [self._public(row) for row in db.execute('SELECT * FROM jobs ORDER BY created')]

    def get(self,identifier):
        self.path(identifier,'.source')
        with self.connect() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()
        if row is None:raise KeyError('Job not found.')
        return self._public(row)

    def submit(self,stream,name,style):
        if style not in STYLES:raise ValueError('Unknown presentation style.')
        # Only a basename is kept; no local device path enters reports or outputs.
        name=name.replace('\\','/').split('/')[-1].strip()
        if not name or len(name)>200 or any(ord(c)<32 for c in name):raise ValueError('Invalid image name.')
        identifier=uuid4().hex;target=self.path(identifier,'.source');temp=self.path(identifier,'.upload')
        with self.lock:
            with self.connect() as db:
                if db.execute('SELECT count(*) FROM jobs').fetchone()[0]>=MAX_ITEMS:raise ValueError('The queue holds at most 100 jobs; remove completed jobs first.')
            if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())>=MAX_DISK_BYTES:raise ValueError('Queue disk budget reached; download and remove completed jobs.')
            require_disk_space([(self.root,MAX_INPUT_BYTES*4)])
            size=0;digest=sha256()
            try:
                with temp.open('xb') as output:
                    while chunk:=stream.read(1024*1024):
                        size+=len(chunk)
                        if size>MAX_INPUT_BYTES:raise ValueError('Use images no larger than 64 MiB.')
                        digest.update(chunk);output.write(chunk)
                if not size:raise ValueError('Empty image file.')
                if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())+size*3>=MAX_DISK_BYTES:
                    raise ValueError('Queue disk budget reached.')
                temp.replace(target)
                now=time()
                with self.connect() as db:
                    db.execute('INSERT INTO jobs(id,name,style,style_json,state,source_sha256,source_bytes,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                               (identifier,name,style,json.dumps(STYLES[style]),'queued',digest.hexdigest(),size,now,now))
            except BaseException:
                temp.unlink(missing_ok=True);target.unlink(missing_ok=True);raise
        self.wake.set();return self.get(identifier)

    def cancel(self,identifier):
        with self.lock,self.connect() as db:
            current=self.get(identifier)
            if current['state'] in {'queued','running'}:
                db.execute('UPDATE jobs SET state=?,updated=? WHERE id=?',('cancelled' if current['state']=='queued' else 'cancel_requested',time(),identifier))
        return self.get(identifier)

    def retry(self,identifier):
        with self.lock,self.connect() as db:
            current=self.get(identifier)
            if current['state'] not in {'failed','cancelled'} or current['attempts']>=5:raise ValueError('Only failed/cancelled jobs below five attempts can be retried.')
            db.execute("UPDATE jobs SET state='queued',error=NULL,updated=? WHERE id=?",(time(),identifier))
        self.wake.set();return self.get(identifier)

    def remove(self,identifier):
        with self.lock,self.connect() as db:
            if self.get(identifier)['state'] not in {'done','failed','cancelled'}:raise ValueError('Cancel or finish the job before removing it.')
            for suffix in ('.source','.zip','.report','.part','.upload'):self.path(identifier,suffix).unlink(missing_ok=True)
            db.execute('DELETE FROM jobs WHERE id=?',(identifier,))

    def run_one(self):
        with self.lock,self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:return False
            job=dict(row);identifier=job['id']
            db.execute("UPDATE jobs SET state='running',attempts=attempts+1,error=NULL,updated=? WHERE id=?",(time(),identifier))
        source=self.path(identifier,'.source');output=self.path(identifier,'.zip');report=self.path(identifier,'.report')
        report.unlink(missing_ok=True)
        process=None;state='failed';error='Image presentation failed; retry the job.';output_hash=None
        try:
            require_disk_space([(self.root,192*1024*1024)])
            if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())+192*1024*1024>MAX_DISK_BYTES:
                raise ValueError('Queue disk budget reached.')
            if getattr(sys,'frozen',False):
                process=FrozenPresentationProcess({'id':identifier,'sha256':job['source_sha256'],'label':job['name'],
                                                  'style':job['style'],'parameters':json.loads(job['style_json'])})
            else:
                process=mp.get_context('spawn').Process(target=render_presentation,args=(str(source),str(output),str(report),job['source_sha256'],job['name'],job['style'],json.loads(job['style_json'])),daemon=True)
            process.start();deadline=monotonic()+JOB_SECONDS
            while process.is_alive():
                process.join(.1)
                current=self.get(identifier)['state']
                if self.stop.is_set() or current=='cancel_requested' or monotonic()>deadline:
                    process.terminate();process.join(5)
                    state='queued' if self.stop.is_set() else 'cancelled' if current=='cancel_requested' else 'failed'
                    error='Interrupted; ready to resume.' if state=='queued' else 'Cancelled.' if state=='cancelled' else 'Time limit reached.'
                    break
            else:
                proof=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {'ok':False,'error':'Worker stopped before producing a result.'}
                if proof['ok'] and output.is_file() and digest_file(source)==job['source_sha256'] and digest_file(output)==proof['output_sha256']:
                    state='done';error=None;output_hash=proof['output_sha256']
                else:error=proof.get('error','Integrity check failed.')
        except BaseException:
            error='Image presentation failed; check disk space, format and source integrity.'
        finally:
            if process is not None:
                if process.is_alive():process.terminate();process.join(5)
                process.close()
            if state!='done':output.unlink(missing_ok=True)
            report.unlink(missing_ok=True);self.path(identifier,'.part').unlink(missing_ok=True)
            with self.lock,self.connect() as db:
                # A cancellation arriving just as the process finishes still wins.
                current=db.execute('SELECT state FROM jobs WHERE id=?',(identifier,)).fetchone()
                if current and current[0]=='cancel_requested':state='cancelled';error='Cancelled.';output_hash=None;output.unlink(missing_ok=True)
                db.execute('UPDATE jobs SET state=?,error=?,output_sha256=?,updated=? WHERE id=?',(state,error,output_hash,time(),identifier))
        return True

    def _loop(self):
        while not self.stop.is_set():
            try:
                if self.run_one():continue
            except Exception:pass # Remain available; interrupted state is recovered on next startup.
            self.wake.wait(.5);self.wake.clear()

    def close(self):
        self.stop.set();self.wake.set()
        if self.thread is not None:self.thread.join(6)
        if self._lease is not None and (self.thread is None or not self.thread.is_alive()):
            self._lease.close();self._lease=None


_manager=None
_manager_lock=RLock()
def close_style_queue():
    with _manager_lock:
        if _manager is not None:_manager.close()

def style_queue()->StyleQueue:
    global _manager
    with _manager_lock:
        if _manager is None:_manager=StyleQueue(image_work_dir('image-style-queue'))
        _manager.ensure_started()
        return _manager
