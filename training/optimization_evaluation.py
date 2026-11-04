"""Frozen internal/retrospective comparisons, independent evidence and integrity."""
from datetime import datetime,timezone
import csv
import json
import math
from pathlib import Path
import shutil

import numpy as np

from app.model_checkpoint import load_checkpoint
from training.dataset_loader import file_sha256
from training.expanded_dataset import canonical_hash
from training.expanded_evaluation import match_bootstrap,prediction_records,recalculate_saved_predictions,METRICS
from training.optimization_analysis import analyze_model
from training.optimization_data import role_matches
from training.optimization_runner import ExperimentRegistry,run_case
from training.reporting import write_json_report
from training.train_mlp import TrainConfig


def check(condition,message):
    if not condition:raise ValueError(message)


def immutable_metadata(metadata):return {k:v for k,v in metadata.items() if k!='test_evaluation'}


def assert_model_evaluation_allowed(metadata,corpus,matches):
    if 'development' in metadata:training=set(metadata['development']['training_match_ids'])
    elif metadata['dataset'].get('dataset_version')=='expanded_strict_v2':training=set(role_matches(corpus,'train'))
    else:training={m for m,r in corpus.contract['original_roles'].items() if r=='train'}
    check(not training.intersection(matches),'Evaluation contains previous training matches; saved checkpoint is not a fair unseen reference')


def verify_candidate(corpus,output,checkpoint):
    output,checkpoint=Path(output),Path(checkpoint)
    frozen=json.loads((output/'candidate_freeze.json').read_text())
    check(frozen['status']=='FROZEN' and frozen['dataset_contract_sha256']==corpus.contract_sha256,'Frozen candidate data changed')
    check(str(checkpoint)==frozen['checkpoint'] and file_sha256(checkpoint)==frozen['checkpoint_sha256'],'Frozen candidate weights changed')
    for name,key in [('experiment_registry.json','registry_sha256'),('protocol.json','protocol_sha256'),('experiment_comparison.json','comparison_sha256')]:check(file_sha256(output/name)==frozen[key],f'Frozen {name} changed')
    reference=Path(frozen['reference_checkpoint'])
    check(file_sha256(reference)==frozen['reference_sha256'] and file_sha256(reference.with_suffix('.metadata.json'))==frozen['reference_metadata_sha256'],'Frozen reference model changed')
    registry=json.loads((output/'experiment_registry.json').read_text())
    check(len(registry['entries'])==8 and all(row['status']=='PASS' for row in registry['entries']),'Frozen experiment matrix incomplete')
    for row in registry['entries']:
        path=Path(row['checkpoint'])
        for artifact,digest in ((path,row['checkpoint_sha256']),(path.with_suffix('.metadata.json'),row['metadata_sha256']),(path.parent/'history.json',row['history_sha256'])):
            check(artifact.is_file() and file_sha256(artifact)==digest,f'Frozen experiment artifact changed: {artifact}')
    _,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
    check(canonical_hash(immutable_metadata(metadata))==frozen['metadata_content_sha256'],'Frozen candidate metadata changed')
    return frozen


def prepare_candidate(corpus,output,checkpoint):
    output,checkpoint=Path(output),Path(checkpoint)
    check(checkpoint.resolve() not in {Path('artifacts/models/mahjong_discard_mlp.pt').resolve(),Path('artifacts/models/mahjong_discard_mlp_v2.pt').resolve()},'Cannot overwrite stable previous model')
    if (output/'candidate_freeze.json').exists():return verify_candidate(corpus,output,checkpoint)
    complete=json.loads((output/'training_complete.json').read_text());protocol=json.loads((output/'protocol.json').read_text());comparison=json.loads((output/'experiment_comparison.json').read_text())
    registry=ExperimentRegistry(output,protocol)
    check(complete['status']=='PASS' and registry.value['status']=='TRAINING_COMPLETE','Experiment matrix incomplete')
    check(file_sha256(registry.path)==complete['registry_sha256'] and file_sha256(output/'experiment_comparison.json')==complete['comparison_sha256'],'Completed matrix evidence changed')
    check(len(registry.value['entries'])==8 and all(r['status']=='PASS' for r in registry.value['entries']),'Expected eight completed registered runs')
    for row in registry.value['entries']:
        run_case(corpus,registry,row['experiment'],row['architecture'],TrainConfig(**row['config']),row['fold'],resume=True)
    selected=next(r for r in registry.value['entries'] if r['id']==comparison['selected_experiment'])
    eligible=[r for r in registry.value['entries'] if r['experiment'] in ('E1','E2','E3') and r['fold']==0 and r['model_seed']==protocol['primary_seed']]
    check(selected['id']==min(eligible,key=lambda r:r['validation']['nll'])['id'],'Selection does not match declared validation criterion')
    reference=next(r for r in registry.value['entries'] if r['experiment']=='E0' and r['fold']==0 and r['model_seed']==protocol['primary_seed'])
    source=Path(selected['checkpoint']);checkpoint.parent.mkdir(parents=True,exist_ok=True)
    if checkpoint.exists():check(file_sha256(checkpoint)==selected['checkpoint_sha256'],'Existing new checkpoint differs')
    else:
        temporary=checkpoint.with_suffix('.tmp');shutil.copyfile(source,temporary);temporary.replace(checkpoint)
    shutil.copyfile(source.with_suffix('.metadata.json'),checkpoint.with_suffix('.metadata.json'))
    _,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
    frozen={'status':'FROZEN','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'selected_experiment':selected['id'],'checkpoint':str(checkpoint),'checkpoint_sha256':file_sha256(checkpoint),'metadata_content_sha256':canonical_hash(immutable_metadata(metadata)),'source_checkpoint':str(source),'reference_checkpoint':reference['checkpoint'],'reference_sha256':reference['checkpoint_sha256'],'reference_metadata_sha256':reference['metadata_sha256'],'dataset_contract_sha256':corpus.contract_sha256,'registry_sha256':file_sha256(registry.path),'protocol_sha256':file_sha256(output/'protocol.json'),'comparison_sha256':file_sha256(output/'experiment_comparison.json'),'evaluation_kind':'internal_group_development','new_blind_test_available':False,'historical_test_used_for_selection':False}
    write_json_report(output/'candidate_freeze.json',frozen)
    shutil.copyfile(source.parent/'history.json',output/'training_history.json')
    return frozen


def _compare_rows(before,after):
    for key in ('shard_path','shard_row','match_id','player_uid','seat','target_class','predicted_class','top3','legal_classes'):check(before[key]==after[key],f'Saved prediction identity/rank changed: {key}')
    check(math.isclose(before['target_log_probability'],after['target_log_probability'],abs_tol=1e-7,rel_tol=0),'Saved target score differs from actual inference')
    check(np.allclose(before['class_scores'],after['class_scores'],atol=1e-7,rtol=1e-5),'Saved class probabilities differ from actual inference')


def _tables(output,metrics):
    with (output/'per_class_metrics.csv').open('w',newline='') as stream:
        fields=['model','class_id','tile','support','predicted_count','precision','recall','f1'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for name,values in metrics.items():
            for row in values['per_class']:writer.writerow(dict(row,model=name))
    with (output/'confusion_matrix.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['model','true_class']+list(range(34)))
        for name,values in metrics.items():
            for i,row in enumerate(values['confusion_matrix']):writer.writerow([name,i]+row)


def compare_models(corpus,split,checkpoints,output,kind,bootstrap_samples=2000,verify_existing=False,resume=False,freeze_path=None):
    from training.optimization_data import validate_optimization_output
    output=Path(output);validate_optimization_output(output);output.mkdir(parents=True,exist_ok=True)
    status_path=output/('reverification.json' if verify_existing else 'metrics.json')
    try:
        if not verify_existing and status_path.exists() and json.loads(status_path.read_text()).get('status')=='PASS':status_path=output/'attempt_status.json'
        if verify_existing:write_json_report(status_path,{'status':'RUNNING','kind':kind})
        return _compare_models(corpus,split,checkpoints,output,kind,bootstrap_samples,verify_existing,resume,freeze_path)
    except BaseException as exc:
        write_json_report(status_path,{'status':'FAIL','reason':repr(exc),'kind':kind})
        raise


def _compare_models(corpus,split,checkpoints,output,kind,bootstrap_samples=2000,verify_existing=False,resume=False,freeze_path=None):
    check(kind in ('internal_group_development','retrospective_known_test'),'Unknown evaluation kind; no new blind test exists')
    check(split.name==('validation' if kind=='internal_group_development' else 'test'),'Wrong cohort role')
    if kind=='retrospective_known_test':
        check(freeze_path is not None and Path(freeze_path).is_file(),'Retrospective evaluation requires final frozen selection')
        frozen=json.loads(Path(freeze_path).read_text());check(frozen['status']=='FROZEN' and frozen['historical_test_used_for_selection'] is False,'Final selection not frozen')
    output=Path(output);output.mkdir(parents=True,exist_ok=True);report_path=output/'metrics.json'
    old=json.loads(report_path.read_text()) if report_path.exists() else None
    check(not(verify_existing and resume),'Choose verify-existing or resume')
    if old:
        check(old['status']=='PASS' and verify_existing or old['status'] in ('FAIL','RUNNING') and resume,'Existing comparison requires verification or same-frozen resume')
    else:check(not verify_existing and not resume,'No previous comparison to verify/resume')
    if verify_existing:
        for name,digest in old['artifact_sha256'].items():check((output/name).is_file() and file_sha256(output/name)==digest,f'Saved evidence changed: {name}')
    models={};identities={}
    for name,path in checkpoints.items():
        check(name in ('reference_E0','candidate_v3','saved_v2'),'Unexpected comparison model name')
        model,metadata=load_checkpoint(Path(path),expected_contract=corpus.contract)
        assert_model_evaluation_allowed(metadata,corpus,split.match_ids)
        models[name]=model;identities[name]={'checkpoint_sha256':file_sha256(Path(path)),'metadata_content_sha256':canonical_hash(immutable_metadata(metadata))}
    check({'reference_E0','candidate_v3'}.issubset(models),'Paired reference/candidate required')
    identity={'dataset_contract_sha256':corpus.contract_sha256,'split_identity':split.identity,'models':identities,'kind':kind,'bootstrap_samples':bootstrap_samples,'group_keys_sha256':canonical_hash(corpus.group_keys)}
    context_path=output/'comparison_freeze.json'
    if context_path.exists():check(json.loads(context_path.read_text())==identity,'Frozen comparison identity changed')
    else:write_json_report(context_path,identity)
    if not verify_existing:write_json_report(report_path,{'status':'RUNNING','kind':kind})
    try:
        analyses={};metrics={};evidence=['comparison_freeze.json'];independent={}
        for name,model in models.items():
            path=output/(name+'_predictions.jsonl.gz');temporary=output/(name+'_verification.tmp')
            analysis=analyze_model(model,split,temporary if verify_existing else path)
            if verify_existing:
                count=0
                for before,after in zip(prediction_records(path),prediction_records(temporary),strict=True):_compare_rows(before,after);count+=1
                check(count==split.samples,'Saved prediction count changed');temporary.unlink()
                check(json.loads((output/(name+'_analysis.json')).read_text())==analysis,'Actual analysis differs from saved development evidence')
            else:write_json_report(output/(name+'_analysis.json'),analysis)
            analyses[name]=analysis;metrics[name]=analysis['metrics']
            independent[name]=recalculate_saved_predictions(path,single_model_name=name)[name]
            for key in METRICS:check(math.isclose(metrics[name][key],independent[name][key],abs_tol=1e-7,rel_tol=0),'Independent saved metric mismatch')
            check(metrics[name]['confusion_matrix']==independent[name]['confusion_matrix'],'Independent confusion mismatch')
            evidence.extend([path.name,name+'_analysis.json'])
        names=list(models);streams=[prediction_records(output/(name+'_predictions.jsonl.gz')) for name in names]
        counts={};observed=set();rows_count=0
        for rows in zip(*streams,strict=True):
            first=rows[0];match=first['match_id'];observed.add(match)
            check(all(all(row[key]==first[key] for key in ('match_id','shard_path','shard_row','target_class','legal_classes')) for row in rows),'Comparison cohorts differ')
            group=corpus.group_keys.get(match,match)
            value=counts.setdefault(group,{'n':0,'correct':{name:0 for name in names}});value['n']+=1;rows_count+=1
            for name,row in zip(names,rows):value['correct'][name]+=row['predicted_class']==row['target_class']
        check(rows_count==split.samples and observed==split.match_ids,'Evaluation sample/match reconciliation failed')
        intervals=match_bootstrap(counts,bootstrap_samples,2026,reference_model='reference_E0',candidate_model='candidate_v3')
        intervals.update(clusters=len(counts),matches=len(observed),method='Paired resampling of complete match-or-identical-observable-trajectory clusters; decision-weighted accuracy')
        uid_safety=[]
        for key,reference in analyses['reference_E0']['groups'].items():
            candidate=analyses['candidate_v3']['groups'].get(key)
            if key.startswith('uid:') and reference.get('samples',0)>=1000 and candidate and reference['top1']-candidate['top1']>.05:uid_safety.append({'uid':key[4:],'samples':reference['samples'],'reference_top1':reference['top1'],'candidate_top1':candidate['top1']})
        result={'status':'PASS','kind':kind,'new_blind_test_available':False,'samples':rows_count,'matches':len(observed),'players':analyses['candidate_v3']['player_count'],'models':metrics,'confidence_intervals':intervals,'independent_recalculation':'PASS','severe_uid_degradations':uid_safety,'uid_threshold':{'samples':1000,'maximum_top1_drop':.05},'limitations':'Internal development or already published historical test; not a new independent blind test. Known UID/repeated-state dependence remains.'}
        if verify_existing:
            for key in ('kind','samples','matches','players','models','confidence_intervals','severe_uid_degradations'):check(old[key]==result[key],'Recalculated comparison differs')
            write_json_report(output/'reverification.json',{'status':'PASS','actual_inference_repeated':True,'saved_predictions_recalculated':True});return old
        _tables(output,metrics);write_json_report(output/'confidence_intervals.json',intervals);write_json_report(output/'independent_recalculation.json',{'status':'PASS','models':independent})
        evidence.extend(['per_class_metrics.csv','confusion_matrix.csv','confidence_intervals.json','independent_recalculation.json'])
        result['artifact_sha256']={name:file_sha256(output/name) for name in evidence}
        write_json_report(report_path,result)
        return result
    except BaseException as exc:
        write_json_report(output/('reverification.json' if verify_existing else 'metrics.json'),{'status':'FAIL','reason':repr(exc),'kind':kind})
        raise
