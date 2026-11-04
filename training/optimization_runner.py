"""Bounded, registered MLP experiments with paired group/seed development checks."""
import argparse
import copy
from dataclasses import asdict,replace
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import shutil

from app.mlp import architecture_spec,parameter_count
from app.model_checkpoint import load_checkpoint
from training.dataset_loader import file_sha256
from training.expanded_dataset import canonical_hash
from training.expanded_training import benchmark_loading,train_sharded,training_state_exists,save_run_checkpoint
from training.optimization_data import DevelopmentCorpus,development_splits,evaluation_lineage,FOLD_SALT,FOLD_BUCKETS
from training.reporting import write_json_report
from training.train_mlp import TrainConfig,weights_sha256


def protocol_config(dataset_sha,lineage_sha,config=None):
    config=config or TrainConfig(batch_size=256,max_epochs=60,patience=8,device='cpu')
    return {'version':'phase2.2-mlp-protocol-v1','dataset_contract_sha256':dataset_sha,'lineage_content_sha256':lineage_sha,'common_config':asdict(config),'primary_seed':config.seed,'robustness_seed':config.seed+1,'primary_fold':0,'robustness_fold':1,'primary_architectures':{'E0':architecture_spec((64,),.2),'E1':architecture_spec((128,),.2),'E2':architecture_spec((256,128),.2)},'E3_rule':'Choose lower validation NLL of E1/E2; change only weight_decay to0.001 when selected eval train-minus-val Top1>=0.03, otherwise only dropout to0.1','trial_budget':8,'optional_E4_E5':'NOT RUN; bounded four primary configurations','selection_metric':'validation_nll','shortlist_rule':'Minimum fold0 primary-seed validation NLL among E1/E2/E3; no historical test','seed_policy':'Publish primary-seed fold0 candidate; robustness seed is never used to cherry-pick checkpoint','promotion_rule':'Three paired development runs: mean reference-minus-candidate NLL>=0.01, every paired NLL improvement>0, mean Top1/Top3/MacroF1 degradation<=0.002, all legal; no supported UID>=1000 loses>0.05 Top1; service p95<=50ms; compatibility/game/regression safety PASS','test_kind':'retrospective_known_test_only_after_freeze','new_blind_test_available':False}


class ExperimentRegistry:
    def __init__(self,root,protocol):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.protocol=copy.deepcopy(protocol)
        self.protocol_path=self.root/'protocol.json';self.path=self.root/'experiment_registry.json'
        if self.protocol_path.exists():
            if json.loads(self.protocol_path.read_text())!=protocol:raise ValueError('Frozen protocol differs')
        else:write_json_report(self.protocol_path,protocol)
        self.value=json.loads(self.path.read_text()) if self.path.exists() else {'status':'RUNNING','protocol_sha256':file_sha256(self.protocol_path),'entries':[]}
        if self.value['protocol_sha256']!=file_sha256(self.protocol_path):raise ValueError('Registry protocol hash changed')
        ids=[r['id'] for r in self.value['entries']]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate experiment IDs')

    def register(self,entry,resume=False):
        existing=next((r for r in self.value['entries'] if r['id']==entry['id']),None)
        if existing is not None:
            if not resume:raise ValueError('Duplicate experiment ID')
            if any(existing.get(k)!=v for k,v in entry.items()):raise ValueError('Experiment identity changed')
            return existing
        value=copy.deepcopy(entry);value['status']='REGISTERED';self.value['entries'].append(value);self.save();return value

    def save(self):write_json_report(self.path,self.value)


def regularization_candidate(source):
    config=TrainConfig(**source['config']);spec=source['architecture']
    if source['generalization_gap']>=.03:return copy.deepcopy(spec),replace(config,weight_decay=.001),'Observed eval train/validation Top1 gap>=3pp; increase weight decay only'
    widths=(spec['hidden_dim'],) if 'hidden_dim' in spec else tuple(spec['hidden_dims'])
    return architecture_spec(widths,.1),config,'Observed gap<3pp; test reduced dropout only, without changing capacity'


def development_metadata(corpus,training,validation,config,fold,registry,history_path):
    lineage=evaluation_lineage(corpus)
    return {'version':'phase2.2-dev-v1','evaluation_kind':'internal_group_development','new_blind_test_available':False,'selection_metric':'validation_nll','fold_salt':FOLD_SALT,'fold_count':FOLD_BUCKETS,'fold_id':fold,'trajectory_group_keys':corpus.group_keys,'training_match_ids':sorted(training.match_ids),'validation_match_ids':sorted(validation.match_ids),'historical_test_match_ids':lineage['historical_test_match_ids'],'training_match_ids_sha256':canonical_hash(sorted(training.match_ids)),'validation_match_ids_sha256':canonical_hash(sorted(validation.match_ids)),'historical_test_match_ids_sha256':canonical_hash(lineage['historical_test_match_ids']),'training_samples':training.samples,'validation_samples':validation.samples,'seed':config.seed,'protocol_sha256':file_sha256(registry.protocol_path),'lineage_content_sha256':canonical_hash(lineage),'history_reference':str(history_path),'history_sha256':file_sha256(history_path),'historical_test_labels_used_for_selection':False}


def run_case(corpus,registry,experiment,spec,config,fold,resume=False,stop_after_epoch=None):
    if (registry.root/'model_freeze.json').exists():raise ValueError('Model already frozen; no further experiments')
    if experiment not in ('E0','E1','E2','E3') or fold not in (0,1):raise ValueError('Unknown experiment/fold')
    common=TrainConfig(**registry.protocol['common_config'])
    if config.seed not in (registry.protocol['primary_seed'],registry.protocol['robustness_seed']):raise ValueError('Undeclared experiment seed')
    expected=replace(common,seed=config.seed)
    if experiment=='E3' and config.weight_decay==.001:expected=replace(expected,weight_decay=.001)
    if asdict(config)!=asdict(expected):raise ValueError('Configuration differs from frozen protocol')
    if experiment!='E3' and spec!=registry.protocol['primary_architectures'][experiment]:raise ValueError('Architecture differs from frozen primary matrix')
    if corpus.contract_sha256!=registry.protocol['dataset_contract_sha256'] or canonical_hash(evaluation_lineage(corpus))!=registry.protocol['lineage_content_sha256']:raise ValueError('Development lineage identity changed')
    training,validation=development_splits(corpus,fold)
    identity={'id':f'{experiment}_f{fold}_s{config.seed}','experiment':experiment,'architecture':spec,'parameters':parameter_count(spec),'config':asdict(config),'fold':fold,'model_seed':config.seed,'training_identity':training.identity,'validation_identity':validation.identity}
    entry=registry.register(identity,resume)
    folder=registry.root/'experiments'/identity['id'];checkpoint=folder/'model.pt'
    if entry['status']=='PASS':
        model,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
        if file_sha256(checkpoint)!=entry['checkpoint_sha256'] or file_sha256(checkpoint.with_suffix('.metadata.json'))!=entry['metadata_sha256'] or weights_sha256(model.state_dict())!=entry['best_weights_sha256']:raise ValueError('Completed experiment artifact changed')
        history_path=folder/'history.json';summary=json.loads(history_path.read_text())
        if file_sha256(history_path)!=entry['history_sha256'] or metadata['validation_metrics']!=entry['validation'] or summary['best_validation_metrics']!=entry['validation'] or summary['selected_train_metrics']!=entry['train'] or summary['generalization_gap']!=entry['generalization_gap'] or entry['checkpoint']!=str(checkpoint):raise ValueError('Completed experiment metric/evidence mismatch')
        if metadata['development']!=development_metadata(corpus,training,validation,config,fold,registry,history_path):raise ValueError('Completed experiment development identity changed')
        return entry
    if shutil.disk_usage(registry.root).free<1024**3:raise OSError('Insufficient disk: retain at least1GiB before training')
    entry['status']='RUNNING';registry.save()
    try:
        run=train_sharded(training,validation,config,folder,resume=resume and training_state_exists(folder/'training_resume.pt'),stop_after_epoch=stop_after_epoch,model_spec=spec,checkpoint_retention=2)
        if run.summary['status']=='PAUSED':entry.update(status='PAUSED',benchmark_epoch_seconds=run.summary['elapsed_seconds'],epochs_executed=run.summary['epochs_executed']);registry.save();return entry
        metadata=save_run_checkpoint(run,corpus,checkpoint,development_metadata(corpus,training,validation,config,fold,registry,folder/'history.json'))
        loaded,_=load_checkpoint(checkpoint,expected_contract=corpus.contract)
        if weights_sha256(loaded.state_dict())!=run.summary['best_weights_sha256']:raise ValueError('CPU selected checkpoint content mismatch')
        entry.update(status='PASS',best_epoch=run.summary['best_epoch'],epochs_executed=run.summary['epochs_executed'],training_seconds=run.summary['elapsed_seconds'],train=run.summary['selected_train_metrics'],validation=run.summary['best_validation_metrics'],generalization_gap=run.summary['generalization_gap'],checkpoint=str(checkpoint),checkpoint_sha256=metadata['checkpoint_sha256'],metadata_sha256=file_sha256(checkpoint.with_suffix('.metadata.json')),history_sha256=file_sha256(folder/'history.json'),best_weights_sha256=run.summary['best_weights_sha256'],train_samples=training.samples,train_matches=len(training.match_ids),validation_samples=validation.samples,validation_matches=len(validation.match_ids))
        registry.save();return entry
    except BaseException as exc:
        entry.update(status='FAIL',reason=repr(exc));registry.save();raise


def promotion_decision(pairs,latency,safety_pass,uid_safety=True):
    if not safety_pass:return {'decision':'INCONCLUSIVE','reason':'Required compatibility/game/regression verification incomplete or failed','test_used_for_selection':False}
    if len(pairs)!=3 or any(not math.isfinite(row[side]['nll']) for row in pairs for side in ('reference','candidate')):raise ValueError('Exactly three finite paired development runs required')
    deltas=[row['reference']['nll']-row['candidate']['nll'] for row in pairs]
    mean=lambda key,side:sum(row[side][key] for row in pairs)/len(pairs)
    improved=sum(deltas)/len(deltas)>=.01 and min(deltas)>0
    nondegrading=all(mean(key,'candidate')>=mean(key,'reference')-.002 for key in ('top1','top3','macro_f1_34'))
    legal=all(row[side]['legal_rate']==1 for row in pairs for side in ('reference','candidate'))
    promote=improved and nondegrading and legal and uid_safety and latency['p95_ms']<=50
    return {'decision':'PROMOTE_V3' if promote else 'RETAIN_V2','reason':'Prespecified paired development NLL/classification/UID/latency/safety criteria satisfied' if promote else 'Development improvement or nondegradation/safety criterion not satisfied; stable v2 remains recommended','mean_nll_improvement':sum(deltas)/len(deltas),'paired_nll_improvements':deltas,'mean_reference':{k:mean(k,'reference') for k in ('nll','top1','top3','macro_f1_34')},'mean_candidate':{k:mean(k,'candidate') for k in ('nll','top1','top3','macro_f1_34')},'uid_safety':uid_safety,'latency_p95_ms':latency['p95_ms'],'test_used_for_selection':False,'evaluation_kind':'internal_group_development; two folds and one same-fold seed repetition, no new blind test'}


def run_matrix(dataset,output,benchmark_epoch=False,resume=False,common_config=None):
    output=Path(output)
    if any(output.resolve().is_relative_to(Path(p).resolve()) for p in ('artifacts/phase2','artifacts/phase2_1','datasets')):raise ValueError('Cannot write optimization results into protected old artifacts/dataset')
    group_file=output/'trajectory_groups.json'
    grouping=json.loads(group_file.read_text());corpus=DevelopmentCorpus(dataset,group_keys=grouping['group_keys'])
    if grouping['dataset_contract_sha256']!=corpus.contract_sha256 or grouping['group_keys_sha256']!=canonical_hash(corpus.group_keys):raise ValueError('Trajectory grouping identity changed')
    lineage=evaluation_lineage(corpus);protocol=protocol_config(corpus.contract_sha256,canonical_hash(lineage),common_config);registry=ExperimentRegistry(output,protocol)
    write_json_report(output/'evaluation_lineage.json',lineage)
    common=TrainConfig(**protocol['common_config'])
    if benchmark_epoch:
        train,_=development_splits(corpus,0);write_json_report(output/'loader_benchmark.json',benchmark_loading(train,common.batch_size))
        row=run_case(corpus,registry,'E0',protocol['primary_architectures']['E0'],common,0,resume=resume,stop_after_epoch=1)
        write_json_report(output/'epoch_benchmark.json',{'status':row['status'],'actual_full_training_samples':train.samples,'actual_epoch_seconds':row.get('benchmark_epoch_seconds'),'note':'Operational pause after first real epoch; same protocol/optimizer/RNG state resumes E0 without changing hyperparameters'})
        return row
    if (output/'training_complete.json').exists():raise ValueError('Training matrix complete; use final verification, not new tuning')
    primary={}
    for name in ('E0','E1','E2'):primary[name]=run_case(corpus,registry,name,protocol['primary_architectures'][name],common,0,resume=resume)
    source=min((primary['E1'],primary['E2']),key=lambda r:r['validation']['nll'])
    spec,adjusted,reason=regularization_candidate(source)
    write_json_report(output/'regularization_choice.json',{'status':'FROZEN_BEFORE_E3','source':source['id'],'architecture':spec,'config':asdict(adjusted),'reason':reason,'test_used':False})
    primary['E3']=run_case(corpus,registry,'E3',spec,adjusted,0,resume=resume)
    shortlisted=min((primary[k] for k in ('E1','E2','E3')),key=lambda r:r['validation']['nll'])
    best_config=TrainConfig(**shortlisted['config'])
    pairs=[{'reference':primary['E0']['validation'],'candidate':shortlisted['validation'],'reference_id':primary['E0']['id'],'candidate_id':shortlisted['id']}]
    for fold,seed in ((1,common.seed),(0,common.seed+1)):
        reference=run_case(corpus,registry,'E0',primary['E0']['architecture'],replace(common,seed=seed),fold,resume=resume)
        candidate=run_case(corpus,registry,shortlisted['experiment'],shortlisted['architecture'],replace(best_config,seed=seed),fold,resume=resume)
        pairs.append({'reference':reference['validation'],'candidate':candidate['validation'],'reference_id':reference['id'],'candidate_id':candidate['id']})
    result={'status':'PASS','selected_experiment':shortlisted['id'],'primary_seed_fixed':common.seed,'primary_fold_fixed':0,'primary_candidates':list(primary.values()),'paired_development':pairs,'test_used_for_selection':False,'all_expected_runs':8,'optional_E4_E5':'NOT RUN; bounded protocol'}
    if len(registry.value['entries'])!=8 or any(r['status']!='PASS' for r in registry.value['entries']):raise ValueError('Incomplete bounded experiment matrix')
    write_json_report(output/'experiment_comparison.json',result)
    registry.value['status']='TRAINING_COMPLETE';registry.save()
    write_json_report(output/'training_complete.json',{'status':'PASS','selected_experiment':shortlisted['id'],'registry_sha256':file_sha256(registry.path),'comparison_sha256':file_sha256(output/'experiment_comparison.json')})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,default=Path('datasets/expanded_strict_v2'));parser.add_argument('--output',type=Path,default=Path('artifacts/phase2_2'));parser.add_argument('--benchmark-epoch',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    result=run_matrix(args.dataset,args.output,args.benchmark_epoch,args.resume)
    print(json.dumps({'status':result['status'],'selected_experiment':result.get('selected_experiment'),'test_used':False},indent=2))


if __name__=='__main__':main()
