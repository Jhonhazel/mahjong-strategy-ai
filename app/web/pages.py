import hashlib
import json
from functools import lru_cache
from pathlib import Path
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
from app.web.tile_catalog import TILE_CATALOG, WIND_NAMES

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT/'app/templates')
templates.env.globals.update(tile_catalog=TILE_CATALOG, wind_names=WIND_NAMES)

HOME_SUMMARY_SHA256='d84063a958f54f49548dd996955e69ebe8ce1b90585d96a0f3e0b4786d375a46'
# The shared five-area description applies only to this explicitly assigned scope.
GROUP_SCOPE_ROLE='Pengembangan bersama: dataset Mahjong, preprocessing & encoding, training/evaluasi AI, game & web FastAPI, testing, debugging, dokumentasi & presentasi UAS.'


@lru_cache(maxsize=1)
def read_home_summary(path):
    """One small public artifact; missing or damaged charts never prevent play."""
    try:
        if path.stat().st_size>65536:return None
        raw=path.read_bytes()
        if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=HOME_SUMMARY_SHA256:return None
        return json.loads(raw)
    except (OSError,ValueError):return None


def validate_home_summary(data,metadata):
    def require(condition):
        if not condition:raise ValueError('Public research summary mismatch')
    try:
        dataset=metadata['dataset'];development=metadata['development']
        cohort=metadata['training']['training_subset'];rows=data['class_counts']
        require(data['schema_version']==1)
        require(data['dataset_version']==dataset['dataset_version'] and data['dataset_id']==dataset['id'])
        require(data['dataset_revision']==dataset['revision'])
        require(data['contract_sha256']==dataset['contract_sha256'])
        require(data['model_checkpoint_sha256']==metadata['checkpoint_sha256'])
        require(data['training_history_sha256']==development['history_sha256'])
        require(data['training_cohort']=={'experiment':Path(development['history_reference']).parent.name,
            'fold':development['fold_id'],'samples':cohort['samples'],'matches':cohort['matches']})
        require(len(rows)==34)
        for index,row in enumerate(rows):
            require(type(row['class_index']) is int and row['class_index']==index)
            require(row['tile']==metadata['tile_order'][index])
            require(type(row['count']) is int and row['count']>=0)
        require(sum(row['count'] for row in rows)==cohort['samples'])
        corpus=data['corpus'];require(corpus['samples']==dataset['accepted_samples'])
        require(corpus['matches']==dataset['accepted_matches'] and corpus['json_games']==44420 and corpus['player_uids']==581)
        partitions=data['partitions'];require([p['id'] for p in partitions]==['train','validation','test','historical_test'])
        for row in partitions:
            require(all(type(row[key]) is int and row[key]>=0 for key in ('samples','matches')))
            if row['id'] in dataset['splits']:
                require({key:row[key] for key in ('samples','matches')}==dataset['splits'][row['id']])
        require(sum(p['samples'] for p in partitions)==corpus['samples'])
        require(sum(p['matches'] for p in partitions)==corpus['matches'])
    except (KeyError,TypeError,IndexError) as error:
        raise ValueError('Public research summary does not match the promoted model') from error

def chart_percentages(rows):
    """Largest remainder rounding keeps displayed percentages at exactly100%."""
    total=sum(row['count'] for row in rows)
    parts=[divmod(row['count']*100000,total) for row in rows]
    units=[p[0] for p in parts]
    for index in sorted(range(len(rows)),key=lambda i:(-parts[i][1],i))[:100000-sum(units)]:units[index]+=1
    offset=0
    for row,unit in zip(rows,units):
        share=row['count']*100/total
        row.update(percent_units=unit,percent=f'{unit/1000:.3f}%',share=f'{share:.8f}',offset=f'{-offset:.8f}')
        offset+=share
    return rows


def research_context(metadata,path=None):
    data=read_home_summary(path or ROOT/'config/home_research.public.json')
    try:validate_home_summary(data,metadata)
    except ValueError:return None
    classes=chart_percentages([{**row,'label':TILE_CATALOG[row['tile']].label} for row in data['class_counts']])
    maximum=max(row['count'] for row in classes)
    for index,row in enumerate(classes):row.update(width=round(row['count']/maximum*480,3),y=38+index*27)
    families=chart_percentages([{'label':label,'count':sum(row['count'] for row in classes[a:b])}
        for label,a,b in (('Karakter',0,9),('Bambu',9,18),('Lingkaran',18,27),('Angin',27,31),('Naga',31,34))])
    labels={'train':'Train','validation':'Validation','test':'Test retrospektif','historical_test':'Historical test lama'}
    partitions=chart_percentages([{**row,'label':labels[row['id']],'count':row['samples']} for row in data['partitions']])
    return {**data,'classes':classes,'families':families,'partitions':partitions,
            'dominant':max(classes,key=lambda r:r['count']),'minority':min(classes,key=lambda r:r['count'])}


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
                  top1=f"{metrics['top1']*100:.2f}%",top3=f"{metrics['top3']*100:.2f}%",
                  macro_f1=f"{metrics['macro_f1_34']:.3f}",nll=f"{metrics['nll']:.3f}",
                  legal_rate=f"{metrics['legal_rate']*100:.0f}%",metadata=metadata,research=research_context(metadata))


@router.get('/contact')
def contact(request: Request):
    visitor,new_cookie=page_visitor(request);roster=resources(request).contacts
    return render(request,'contact.html',visitor,new_cookie,verified=roster.verified,members=roster.members if roster.verified else [],
                  roles_complete=roster.verified and len(roster.members)==5 and all(member.role==GROUP_SCOPE_ROLE for member in roster.members))


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
