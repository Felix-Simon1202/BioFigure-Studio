"""Opaque local queue references; no server paths accepted from clients."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from backend.image.style_queue import style_queue
from backend.image.storage import require_disk_space
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, ConfigDict
from threading import Lock
from uuid import uuid4
import zipfile
import shutil

router=APIRouter(prefix='/api/image/style-queue',tags=['image-presentation-queue'])
_archive_gate=Lock()


class ArchiveRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    ids:list[str]=Field(min_length=1,max_length=100)


@router.post('/archive')
def download_archive(request:ArchiveRequest):
    if not _archive_gate.acquire(blocking=False):raise HTTPException(409,detail='Another queue archive is being downloaded.')
    target=None
    try:
        queue=style_queue();target=queue.root/('bundle-'+uuid4().hex+'.zip')
        if len(set(request.ids))!=len(request.ids):raise ValueError('Select each completed job once.')
        with queue.lock:
            jobs=[queue.get(identifier) for identifier in request.ids]
            if any(not job['download_available'] for job in jobs):raise ValueError('Select completed jobs only.')
            total=0
            for job in jobs:
                with zipfile.ZipFile(queue.path(job['id'],'.zip')) as archive:
                    total+=sum(info.file_size for info in archive.infolist())
            if total>512*1024*1024:raise ValueError('Choose a smaller archive group (512 MiB maximum).')
            require_disk_space([(queue.root,total+1024*1024)])
            with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as output:
                for index,job in enumerate(jobs):
                    with zipfile.ZipFile(queue.path(job['id'],'.zip')) as source:
                        for info in source.infolist():
                            if info.filename not in {'presentation.svg','manifest.json','source/original.png','source/original.jpg','source/original.tiff'}:raise ValueError('Unexpected result contents.')
                            with source.open(info) as stream,output.open(f'{index+1:03d}-{job["id"][:8]}/{info.filename}','w') as destination:
                                shutil.copyfileobj(stream,destination,1024*1024)
        def finish():
            try:target.unlink(missing_ok=True)
            finally:_archive_gate.release()
        return FileResponse(target,media_type='application/zip',filename='biofigure-presentations.zip',background=BackgroundTask(finish))
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as error:
        try:
            if target is not None:target.unlink(missing_ok=True)
        finally:_archive_gate.release()
        raise HTTPException(422,detail='Could not archive selected outputs. Select completed jobs within 512 MiB.') from error


@router.get('/jobs')
def list_jobs():
    return {'jobs':style_queue().list(),'limits':{'max_jobs':100,'workers':1,'max_image_bytes':64*1024*1024,'max_pixels':16_000_000,'disk_bytes':1024*1024*1024,'job_seconds':120}}


@router.post('/jobs',status_code=202)
async def submit_job(file:UploadFile=File(...),style:str=Form('clean')):
    try:
        return await run_in_threadpool(style_queue().submit,file.file,file.filename or 'image',style)
    except (ValueError,OSError) as error:
        raise HTTPException(422,detail='Could not submit image: check file size, queue capacity and disk space.') from error
    finally:await file.close()


@router.post('/jobs/{identifier}/{action}')
def control_job(identifier:str,action:str):
    try:
        if action=='retry':return style_queue().retry(identifier)
        if action=='cancel':return style_queue().cancel(identifier)
        raise ValueError('Unknown action.')
    except (ValueError,KeyError,OSError) as error:raise HTTPException(422,detail='Queue action unavailable; refresh and retry.') from error


@router.delete('/jobs/{identifier}')
def remove_job(identifier:str):
    try:style_queue().remove(identifier);return {'removed':True}
    except (ValueError,KeyError,OSError) as error:raise HTTPException(422,detail='Could not remove this queue copy. Finish downloads, refresh and retry.') from error


@router.get('/jobs/{identifier}/download')
def download_job(identifier:str):
    try:
        queue=style_queue();job=queue.get(identifier)
        if not job['download_available']:raise ValueError('Output is not ready.')
        return FileResponse(queue.path(identifier,'.zip'),media_type='application/zip',filename=f'biofigure-presentation-{identifier[:8]}.zip')
    except (ValueError,KeyError) as error:raise HTTPException(404,detail='Output is unavailable.') from error
