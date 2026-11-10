"""Real HTTPS acceptance using system trust or one explicitly supplied local CA."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def validate_origin(value):
    parsed=urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Supply an HTTPS origin without credentials, path or query')
    return value.rstrip('/')


class Client:
    def __init__(self,base,ca=None):
        self.base=validate_origin(base);self.csrf=None;self.cookies=http.cookiejar.CookieJar()
        self.context=ssl.create_default_context(cafile=str(ca) if ca else None)
        self.opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.context),
                                               urllib.request.HTTPCookieProcessor(self.cookies))
        self.responses=[]

    def request(self,path,data=None,method='GET',origin=None,csrf=True):
        headers={'Content-Type':'application/json','Origin':origin or self.base}
        if self.csrf and csrf:headers['X-CSRF-Token']=self.csrf
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,
                                       method=method,headers=headers)
        try:
            with self.opener.open(request,timeout=20) as response:
                status=response.status;body=response.read();response_headers=response.headers
        except urllib.error.HTTPError as response:
            status=response.code;body=response.read();response_headers=response.headers
        try:value=json.loads(body)
        except ValueError:value=body.decode('utf-8')
        self.responses.append({'method':method,'path':path,'status':status})
        return status,value,response_headers

    def session(self):
        status,data,headers=self.request('/api/session');assert status==200
        self.csrf=data['csrf_token'];cookie=headers.get('Set-Cookie','').lower()
        assert 'secure' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie


def acceptance(base,ca=None):
    client=Client(base,ca);client.session();pages={}
    for path in ('/','/game','/contact','/history','/docs','/redoc','/openapi.json','/static/tiles.svg','/static/phase4/playback.mjs'):
        status,body,headers=client.request(path);assert status==200,(path,status);pages[path]=status
        assert headers.get('Content-Security-Policy') and headers.get('X-Content-Type-Options')=='nosniff'
        if path=='/contact':assert body.count('class="member-card"')==5 and 'Pembagian Tugas Kelompok 1' in body and 'belum dikonfirmasi' not in body
    assert client.request('/health/ready')[1]=={'status':'ready','model':'ready','database':'ready'}
    assert client.request('/api/games',{},'POST',csrf=False)[0]==403
    assert client.request('/api/games',{},'POST',origin='https://other.invalid')[0]==403
    status,view,_=client.request('/api/games',{'seed':42,'human_seat':1},'POST');assert status==201
    game='/api/games/'+view['game_id'];other=Client(base,ca);other.session()
    assert other.request(game)[0]==404
    saved=[];kinds={};steps=0;latencies=[]
    while view['status']!='FINISHED' and steps<400:
        if view['can_request_ai_prediction'] and (len(saved)<2 or not any(p['turn_phase']=='POST_MELD_DISCARD' for p in saved)):
            before=view;started=time.monotonic()
            status,prediction,_=client.request(game+'/predict',{'expected_turn_number':view['turn_number']},'POST')
            latencies.append(time.monotonic()-started);assert status==201
            assert prediction['model_version']=='discard_mlp_flexible_v1:ad05a5b2ce37'
            assert [x['score'] for x in prediction['top3']]==sorted((x['score'] for x in prediction['top3']),reverse=True)
            assert all(x['action_id']==x['class_index']+2 and any(a['action_id']==x['action_id'] for a in view['legal_actions']) for x in prediction['top3'])
            assert client.request(game)[1]==before
            status,detail,_=client.request('/api/predictions/'+prediction['prediction_id']);assert status==200
            assert detail['checkpoint_sha256']=='ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720'
            assert other.request('/api/predictions/'+prediction['prediction_id'])[0]==404
            assert other.request('/api/predictions/'+prediction['prediction_id'],method='DELETE')[0]==404
            assert client.request(game+'/predict',{'expected_turn_number':view['turn_number']},'POST')[1]['reused']
            saved.append(prediction)
        actions=view['legal_actions']
        action=next((a for a in actions if a['action_type']=='Hu'),None) or next((a for a in actions if a['action_type'] in ('Chi','Peng','Gang','AnGang','BuGang')),None) or actions[0]
        status,view,_=client.request(game+'/actions',{'action_id':action['action_id'],'expected_turn_number':view['turn_number']},'POST')
        assert status==200;kinds[action['action_type']]=kinds.get(action['action_type'],0)+1;steps+=1
    assert view['status']=='FINISHED' and len(saved)>=2 and 'Chi' in kinds
    assert sum(view['round_result']['score_deltas'])==0
    status,history,_=client.request('/history');assert status==200
    status,detail,_=client.request('/history/'+saved[0]['prediction_id']);assert status==200 and '<table' in detail
    assert client.request('/api/predictions/'+saved[0]['prediction_id'],method='DELETE')[0]==204
    assert client.request('/api/predictions/'+saved[0]['prediction_id'])[0]==404
    result={'status':'PASS','origin':client.base,'tls_verified':True,'secure_httponly_samesite_cookie':True,
            'pages':pages,'csrf_wrong_origin_missing_token_403':True,'foreign_game_prediction_404':True,
            'real_v3':True,'prediction_readonly_and_reused':True,'actions':steps,'action_kinds':kinds,
            'round_result':view['round_result'],'saved_predictions':len(saved),'history_detail_table':True,
            'deletion_204_then_404':True,'prediction_seconds':latencies,'remaining_prediction':saved[1]['prediction_id']}
    return client,result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--origin',required=True)
    parser.add_argument('--ca',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();_,result=acceptance(args.origin,args.ca)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'status':result['status'],'tls_verified':True,'actions':result['actions']}))


if __name__=='__main__':main()
