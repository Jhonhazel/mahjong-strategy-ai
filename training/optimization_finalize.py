"""Development-only promotion, frozen retrospective reporting and live safety."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

from app.model_checkpoint import load_checkpoint
from app.services.ai_prediction_service import AIDiscardPredictionService
from app.services.game_service import GameSessionService
from scripts.demo_ai_prediction import run_demo
from training.dataset_loader import file_sha256
from training.expanded_dataset import canonical_hash
from training.optimization_data import DevelopmentCorpus,development_splits,validate_optimization_output
from training.optimization_evaluation import prepare_candidate,verify_candidate,compare_models,check,METRICS
from training.optimization_runner import promotion_decision
from training.reporting import write_json_report
from training.train_mlp import weights_sha256


def collect_regression_cases():
    environment=os.environ.copy();environment.pop('PYTEST_ADDOPTS',None)
    result=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q','-p','no:cacheprovider','-o','addopts='],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30,env=environment)
    check(result.returncode==0,'Complete regression test collection failed')
    identities=[]
    for line in result.stdout.splitlines():
        parts=line.strip().split('::')
        if len(parts)>1 and parts[0].endswith('.py'):
            module=parts[0][:-3].replace('\\','.').replace('/','.')
            identities.append(('.'.join([module,*parts[1:-1]]),parts[-1]))
    check(len(identities)>=218 and len(set(identities))==len(identities),'Collected regression inventory is empty, incomplete or duplicated')
    return set(identities)


def regression_evidence(path):
    path=Path(path);root=ET.parse(path).getroot();counts={key:0 for key in ('tests','failures','errors','skipped')}
    for suite in root.iter('testsuite'):
        for key in counts:counts[key]+=int(suite.attrib.get(key,0))
    cases=list(root.iter('testcase'));classes={c.attrib.get('classname','') for c in cases}
    required=('test_mcr_engine_playthrough','test_phase2_model','test_phase2_1_training','test_phase2_2_models','test_phase2_2_data_analysis','test_phase2_2_registry','test_phase2_2_evaluation')
    check(counts['tests']==len(cases) and counts['tests']>=218 and not any(counts[k] for k in ('failures','errors','skipped')),'Regression suite is incomplete or not green')
    check(all(any(name in value for value in classes) for name in required),'Required old/new regression families missing')
    check(not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases),'Regression XML contains failed/skipped cases')
    observed=[(c.attrib.get('classname',''),c.attrib.get('name','')) for c in cases]
    expected=collect_regression_cases()
    check(len(observed)==len(set(observed)) and set(observed)==expected,'Regression suite inventory is incomplete, missing or duplicated')
    return {'status':'PASS','counts':counts,'junit_path':str(path),'junit_sha256':file_sha256(path),'collected_cases':len(expected),'case_inventory_sha256':canonical_hash(sorted(expected))}


def verify_live_and_latency(corpus,output,checkpoint,seeds=(42,43),repetitions=200):
    output=Path(output);checkpoint=Path(checkpoint);before=file_sha256(checkpoint)
    contract_path=corpus.root/'data_contract.json'
    rounds=[]
    for seed in seeds:
        result=run_demo(checkpoint,seed,1,True,contract_path=contract_path)
        check(result['status']=='FINISHED' and all(p['state_unchanged'] and p['all_suggestions_legal'] for p in result['predictions']),'Live game safety failed')
        rounds.append(result);write_json_report(output/f'live_demo_seed_{seed}.json',result)
    check({'SELF_TURN','POST_MELD_DISCARD'}.issubset({p['turn_phase'] for r in rounds for p in r['predictions']}),'Both discard contexts were not exercised')
    service=AIDiscardPredictionService(checkpoint,expected_contract=corpus.contract)
    weights_before=weights_sha256(service._model.state_dict())
    games=GameSessionService()
    try:
        view=games.create_game(seed=42,human_seat=0)
        state=games.get_human_encoded_turn(view.game_id)
        snapshots=(state.obs.copy(),state.legal_mask.copy(),state.legal_discard_mask.copy())
        for _ in range(20):service.predict(state)
        latencies=[]
        for _ in range(repetitions):
            start=time.perf_counter();prediction=service.predict(state);latencies.append((time.perf_counter()-start)*1000)
            check(all(state.legal_mask[item.action_id] for item in prediction.top3),'Latency probe suggested illegal action')
        check(games.get_player_view(view.game_id)==view and all(np.array_equal(a,b) for a,b in zip(snapshots,(state.obs,state.legal_mask,state.legal_discard_mask))),'Latency probe mutated game state')
    finally:games.shutdown()
    check(weights_sha256(service._model.state_dict())==weights_before and file_sha256(checkpoint)==before,'Inference changed model weights')
    latency={'samples':repetitions,'warmup':20,'median_ms':float(np.median(latencies)),'p95_ms':float(np.quantile(latencies,.95)),'maximum_ms':float(max(latencies)),'device':'cpu','includes':'Cached service preprocessing/masking/ranking; excludes model load and game creation'}
    result={'status':'PASS','rounds':rounds,'latency':latency,'weights_unchanged':True,'checkpoint_sha256':before}
    write_json_report(output/'live_demo.json',result);write_json_report(output/'latency.json',latency)
    return result


def _comparison(corpus,split,models,output,kind,verify=False,resume=False,freeze_path=None):
    path=output/'metrics.json';old=json.loads(path.read_text()) if path.exists() else None
    return compare_models(corpus,split,models,output,kind,verify_existing=bool(old and old['status']=='PASS'),resume=bool(old and old['status'] in ('FAIL','RUNNING') and resume),freeze_path=freeze_path)


def finish_optimization(dataset,output,checkpoint,tests_xml,verify_existing=False,resume=False):
    output=Path(output);validate_optimization_output(output);output.mkdir(parents=True,exist_ok=True)
    status_path=output/('reverification.json' if verify_existing else 'final_evaluation.json')
    try:
        if not verify_existing and status_path.exists() and json.loads(status_path.read_text()).get('status')=='PASS':status_path=output/'attempt_status.json'
        if verify_existing:write_json_report(status_path,{'status':'RUNNING'})
        return _finish_optimization(dataset,output,checkpoint,tests_xml,verify_existing,resume)
    except BaseException as exc:
        write_json_report(status_path,{'status':'FAIL','reason':repr(exc),'recovery':'Resume only the same frozen model/protocol/data'})
        raise


def _finish_optimization(dataset,output,checkpoint,tests_xml,verify_existing=False,resume=False):
    output,checkpoint=Path(output),Path(checkpoint)
    report_path=output/'final_evaluation.json'
    old=json.loads(report_path.read_text()) if report_path.exists() else None
    if old and old['status']=='PASS':check(verify_existing,'Existing final result requires --verify-existing; no further tuning')
    elif old:check(resume and old['status'] in ('FAIL','RUNNING'),'Incomplete final result requires same-frozen --resume')
    else:check(not verify_existing,'No final result to verify')
    if verify_existing:
        for name,digest in old['artifact_sha256'].items():check((output/name).is_file() and file_sha256(output/name)==digest,f'Final evidence changed: {name}')
        check(file_sha256(checkpoint.with_suffix('.metadata.json'))==old['metadata_sha256'],'Final checkpoint metadata changed')
    grouping=json.loads((output/'trajectory_groups.json').read_text());corpus=DevelopmentCorpus(dataset,group_keys=grouping['group_keys'])
    candidate=prepare_candidate(corpus,output,checkpoint)
    freeze_path=output/'model_freeze.json'
    if not verify_existing:write_json_report(report_path,{'status':'RUNNING','new_blind_test_available':False})
    try:
        if freeze_path.exists():
            frozen=json.loads(freeze_path.read_text());verify_candidate(corpus,output,checkpoint)
            for name,digest in frozen['selection_evidence_sha256'].items():check(file_sha256(output/name)==digest,f'Frozen selection evidence changed: {name}')
            regression=json.loads((output/'regression_evidence.json').read_text());junit=Path(regression['junit_path'])
            check(junit.is_file() and file_sha256(junit)==regression['junit_sha256'],'Frozen regression XML evidence changed')
            selection=json.loads((output/'model_selection.json').read_text())
            development=development_splits(corpus,0)[1]
            dev_models={'reference_E0':Path(candidate['reference_checkpoint']),'candidate_v3':checkpoint}
            _comparison(corpus,development,dev_models,output/'development','internal_group_development',resume=resume)
        else:
            check(not verify_existing,'Final selection freeze missing')
            development=development_splits(corpus,0)[1]
            dev_models={'reference_E0':Path(candidate['reference_checkpoint']),'candidate_v3':checkpoint}
            dev=_comparison(corpus,development,dev_models,output/'development','internal_group_development',resume=resume)
            live=verify_live_and_latency(corpus,output,checkpoint)
            tests=regression_evidence(tests_xml);write_json_report(output/'regression_evidence.json',tests)
            # Explicitly load both older models; neither metadata file is updated.
            for name in ('mahjong_discard_mlp','mahjong_discard_mlp_v2'):load_checkpoint(Path('artifacts/models')/(name+'.pt'))
            comparison=json.loads((output/'experiment_comparison.json').read_text())
            selection=promotion_decision(comparison['paired_development'],live['latency'],safety_pass=True,uid_safety=not dev['severe_uid_degradations'])
            selection.update(candidate_checkpoint=str(checkpoint),candidate_sha256=file_sha256(checkpoint),recommended_checkpoint=str(checkpoint) if selection['decision']=='PROMOTE_V3' else 'artifacts/models/mahjong_discard_mlp_v2.pt',development_metrics_sha256=file_sha256(output/'development/metrics.json'),regression_evidence_sha256=file_sha256(output/'regression_evidence.json'))
            write_json_report(output/'model_selection.json',selection)
            evidence=['candidate_freeze.json','model_selection.json','protocol.json','experiment_registry.json','experiment_comparison.json','trajectory_groups.json','evaluation_lineage.json','development/metrics.json','regression_evidence.json','live_demo.json','latency.json']
            frozen={'status':'FROZEN','checkpoint_sha256':file_sha256(checkpoint),'dataset_contract_sha256':corpus.contract_sha256,'selection_evidence_sha256':{name:file_sha256(output/name) for name in evidence},'historical_test_used_for_selection':False,'new_blind_test_available':False,'selection_decision':selection['decision']}
            write_json_report(freeze_path,frozen)
        check(frozen['status']=='FROZEN' and frozen['checkpoint_sha256']==file_sha256(checkpoint) and frozen['dataset_contract_sha256']==corpus.contract_sha256 and frozen['historical_test_used_for_selection'] is False,'Final model/data freeze changed')
        # Only after development promotion/safety is frozen may known test be read.
        corpus.allow_test=True;retrospective=corpus.split('test')
        models={'reference_E0':Path(candidate['reference_checkpoint']),'candidate_v3':checkpoint,'saved_v2':Path('artifacts/models/mahjong_discard_mlp_v2.pt')}
        retro=_comparison(corpus,retrospective,models,output/'retrospective','retrospective_known_test',verify_existing,resume,freeze_path)
        _,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
        test_summary={'kind':'retrospective_known_test','new_blind_test_available':False,'selection_already_frozen':True,'samples':retro['samples'],'matches':retro['matches'],'checkpoint_sha256':file_sha256(checkpoint),'metrics':{key:retro['models']['candidate_v3'][key] for key in METRICS},'report':'phase2_2/final_evaluation.json'}
        if verify_existing:
            check(metadata.get('test_evaluation')==test_summary,'Final retrospective metadata inconsistent')
            write_json_report(output/'reverification.json',{'status':'PASS','selection_unchanged':True,'actual_retrospective_inference_repeated':True,'independent_recalculation':True})
            return old
        metadata['test_evaluation']=test_summary
        write_json_report(checkpoint.with_suffix('.metadata.json'),metadata)
        shutil.copyfile(output/'retrospective/per_class_metrics.csv',output/'per_class_metrics.csv');shutil.copyfile(output/'retrospective/confusion_matrix.csv',output/'confusion_matrix.csv')
        evidence=['model_freeze.json','model_selection.json','candidate_freeze.json','protocol.json','experiment_registry.json','experiment_comparison.json','training_history.json','trajectory_groups.json','evaluation_lineage.json','development/metrics.json','retrospective/metrics.json','per_class_metrics.csv','confusion_matrix.csv','regression_evidence.json','live_demo.json','latency.json']
        result={'status':'PASS','new_blind_test_available':False,'evaluation_kind':'Internal grouped development plus retrospective known historical test, never new independent blind evaluation','promotion_decision':selection['decision'],'recommended_checkpoint':selection['recommended_checkpoint'],'candidate_checkpoint':str(checkpoint),'checkpoint_sha256':file_sha256(checkpoint),'metadata_sha256':file_sha256(checkpoint.with_suffix('.metadata.json')),'development':json.loads((output/'development/metrics.json').read_text()),'retrospective':retro,'artifact_sha256':{name:file_sha256(output/name) for name in evidence},'test_used_for_selection':False}
        write_json_report(report_path,result) # Overall PASS follows metadata and all evidence.
        return result
    except BaseException as exc:
        write_json_report(output/('reverification.json' if verify_existing else 'final_evaluation.json'),{'status':'FAIL','reason':repr(exc),'recovery':'Resume only the same frozen model/protocol/data'})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,default=Path('datasets/expanded_strict_v2'));parser.add_argument('--output',type=Path,default=Path('artifacts/phase2_2'));parser.add_argument('--checkpoint',type=Path,default=Path('artifacts/models/mahjong_discard_mlp_v3.pt'));parser.add_argument('--tests-xml',type=Path,default=Path('docs/evidence/phase2_2/full_suite.xml'));parser.add_argument('--verify-existing',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    result=finish_optimization(args.dataset,args.output,args.checkpoint,args.tests_xml,args.verify_existing,args.resume)
    print(json.dumps({'status':result['status'],'decision':result['promotion_decision'],'new_blind_test_available':False,'retrospective':{name:{key:values[key] for key in METRICS} for name,values in result['retrospective']['models'].items()}},indent=2))


if __name__=='__main__':main()
