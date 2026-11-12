"""Local figure styling and reviewed editing proposal endpoints."""
from fastapi import APIRouter, HTTPException
from backend.core.figure_consistency import FigureStyleRequest, preview_figure_style
from backend.core.reviewed_edits import EditRequest, preview_edit
from backend.core.workbench import LocalModelUnavailable, MODEL_ADMISSION
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix='/api/figure-workflow/v1', tags=['figure-workflow'])
_edit_model_lock = MODEL_ADMISSION


@router.post('/style-preview')
def style_preview(request: FigureStyleRequest):
    try:
        return preview_figure_style(request)
    except (ValueError, KeyError) as error:
        raise HTTPException(422, detail=str(error)) from error


@router.post('/edit-preview')
async def edit_preview(request: EditRequest):
    locked = request.provider=='local'
    if locked and not _edit_model_lock.acquire(blocking=False):
        raise HTTPException(409,detail='The local editing model is busy.')
    try:
        return await run_in_threadpool(preview_edit,request)
    except (LocalModelUnavailable,TimeoutError) as error:
        raise HTTPException(503,detail=str(error)) from error
    except (ValueError,KeyError) as error:
        raise HTTPException(422,detail=str(error)) from error
    finally:
        if locked: _edit_model_lock.release()
