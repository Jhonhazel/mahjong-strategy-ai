import uuid

from fastapi import APIRouter, Query, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates

from app.settings import ROOT
from app.web.api import current_visitor, resources
from app.web.errors import WebError
from app.web.security import COOKIE_NAME
from app.web.views import history_summary, history_detail

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT/'app/templates')


def page_visitor(request):
    sessions=resources(request).visitors
    try:return sessions.load(request.cookies.get(COOKIE_NAME)),False
    except WebError:
        if request.headers.get('sec-fetch-site')=='cross-site' and request.headers.get('sec-fetch-dest')!='document':
            raise WebError(403,'origin_rejected','Open this website directly to initialize a session')
        return sessions.create(),True


def render(request,name,visitor,new_cookie,**context):
    response=templates.TemplateResponse(request=request,name=name,context={'csrf_token':visitor.csrf_token,**context})
    if new_cookie:resources(request).visitors.set_cookie(response,visitor)
    return response


@router.get('/')
def home(request: Request):
    visitor,new_cookie=page_visitor(request);runtime=resources(request).runtime
    metadata=runtime.metadata;architecture=metadata['architecture']
    dimensions=[architecture['input_dim'],*architecture['hidden_dims'],architecture['output_dim']]
    metrics=metadata['test_evaluation']['metrics']
    return render(request,'home.html',visitor,new_cookie,model_version=runtime.ai.model_version,
                  architecture=' → '.join(map(str,dimensions)),dataset_id=metadata['dataset']['id'],
                  samples=f"{metadata['dataset']['accepted_samples']:,}",
                  top1=f"{metrics['top1']*100:.2f}%",top3=f"{metrics['top3']*100:.2f}%")


@router.get('/contact')
def contact(request: Request):
    visitor,new_cookie=page_visitor(request);roster=resources(request).contacts
    return render(request,'contact.html',visitor,new_cookie,verified=roster.verified,members=roster.members if roster.verified else [])


@router.get('/game')
def game_page(request: Request,game_id: uuid.UUID | None=None):
    visitor,new_cookie=page_visitor(request)
    return render(request,'game.html',visitor,new_cookie,game_id='' if game_id is None else str(game_id))


@router.get('/history')
def history_page(request: Request,limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0,le=100000)):
    visitor,new_cookie=page_visitor(request)
    records,total=resources(request).history.list(visitor.owner_key,limit,offset)
    return render(request,'history.html',visitor,new_cookie,records=[history_summary(r) for r in records],
                  total=total,limit=limit,offset=offset)


@router.get('/history/{prediction_id}')
def history_detail_page(prediction_id: uuid.UUID,request: Request):
    visitor,new_cookie=page_visitor(request)
    record=resources(request).history.get(visitor.owner_key,prediction_id)
    if record is None:raise WebError(404,'not_found','Prediction not found')
    return render(request,'history_detail.html',visitor,new_cookie,record=history_detail(record),
                  snapshot=record.input_snapshot,output=record.output_snapshot)


@router.post('/history/{prediction_id}/delete')
async def delete_history_form(prediction_id: uuid.UUID,request: Request):
    visitor=current_visitor(request)
    form=await request.form(max_files=0,max_fields=2,max_part_size=1024)
    resources(request).visitors.check_csrf(visitor,form.get('csrf_token'),request.headers.get('origin'),
                                          f'{request.url.scheme}://{request.headers.get("host","")}')
    removed=await run_in_threadpool(resources(request).history.delete,visitor.owner_key,prediction_id)
    if not removed:raise WebError(404,'not_found','Prediction not found')
    return RedirectResponse('/history',status_code=303)
