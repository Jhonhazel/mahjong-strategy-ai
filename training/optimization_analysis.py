"""Development-only error, confidence/calibration and observable repetition audits."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import time

import numpy as np
import torch

from app.domain.tiles import TILE_LIST
from app.mlp import masked_log_probabilities
from app.model_checkpoint import load_checkpoint
from training.expanded_dataset import canonical_hash
from training.expanded_training import MetricAccumulator
from training.optimization_data import DevelopmentCorpus,assert_fair_saved_v2,development_bucket,evaluation_lineage,validate_optimization_output
from training.reporting import write_json_report


def _finish(acc):
    return acc.finish() if acc.n else {'samples':0,'status':'NO_OBSERVATIONS'}


class ScoreDiagnostics:
    def __init__(self,bins=15):
        if bins<1:raise ValueError("Positive calibration bins required")
        self.bins=bins;self.bin_n=np.zeros(bins,np.int64);self.bin_correct=np.zeros(bins,np.int64);self.bin_conf=np.zeros(bins,np.float64)
        self.metrics=MetricAccumulator();self.nontrivial=MetricAccumulator();self.strata={k:MetricAccumulator() for k in ('1','2-3','4-6','7-10','>10')}
        self.ranks=Counter();self.brier=0.;self.low_margin=self.low_margin_errors=0;self.confidence_hist=np.zeros(20,np.int64)

    def update(self,logs,targets,masks):
        self.metrics.update(logs,targets,masks)
        probabilities=np.exp(logs);order=np.argsort(-logs,axis=1,kind='stable');predicted=order[:,0]
        confidence=probabilities[np.arange(len(logs)),predicted];correct=predicted==targets
        bins=np.minimum((confidence*self.bins).astype(np.int64),self.bins-1)
        self.bin_n+=np.bincount(bins,minlength=self.bins);self.bin_correct+=np.bincount(bins,weights=correct,minlength=self.bins).astype(np.int64);self.bin_conf+=np.bincount(bins,weights=confidence,minlength=self.bins)
        self.confidence_hist+=np.bincount(np.minimum((confidence*20).astype(np.int64),19),minlength=20)
        self.brier+=float((np.square(probabilities).sum(axis=1)-2*probabilities[np.arange(len(logs)),targets]+1).sum(dtype=np.float64))
        ranks=np.argmax(order==targets[:,None],axis=1)+1;self.ranks.update(str(int(r)) for r in ranks)
        margin=confidence-probabilities[np.arange(len(logs)),order[:,1]]
        self.low_margin+=int((margin<.05).sum());self.low_margin_errors+=int(((margin<.05)&~correct).sum())
        choices=masks.sum(axis=1)
        for key,selected in [('1',choices==1),('2-3',(choices>=2)&(choices<=3)),('4-6',(choices>=4)&(choices<=6)),('7-10',(choices>=7)&(choices<=10)),('>10',choices>10)]:
            if selected.any():self.strata[key].update(logs[selected],targets[selected],masks[selected])
        selected=choices>1
        if selected.any():self.nontrivial.update(logs[selected],targets[selected],masks[selected])

    def finish(self):
        n=self.metrics.n
        if not n:raise ValueError("No score observations")
        confidence=np.divide(self.bin_conf,self.bin_n,out=np.zeros(self.bins),where=self.bin_n>0)
        accuracy=np.divide(self.bin_correct,self.bin_n,out=np.zeros(self.bins),where=self.bin_n>0)
        return {'metrics':self.metrics.finish(),'ranks':dict(self.ranks),'legal_choice_strata':{key:_finish(acc) for key,acc in self.strata.items()},'nontrivial':_finish(self.nontrivial),'expected_calibration_error':float((self.bin_n*np.abs(confidence-accuracy)).sum()/n),'brier_score':self.brier/n,'mean_top1_confidence':float(self.bin_conf.sum()/n),'calibration_bins':[{'left':i/self.bins,'right':(i+1)/self.bins,'samples':int(self.bin_n[i]),'accuracy':float(accuracy[i]),'mean_confidence':float(confidence[i])} for i in range(self.bins)],'confidence_histogram_width':.05,'confidence_histogram':self.confidence_hist.tolist(),'top1_top2_margin_below_005':self.low_margin,'wrong_and_margin_below_005':self.low_margin_errors,'score_meaning':'Observed discard-class confidence, never Mahjong winning probability'}


class SignatureAudit:
    def __init__(self):self.inputs={};self.coarse={};self.n=0

    def add(self,obs,mask,target,bucket):
        if obs.shape!=(38,4,9) or mask.shape!=(34,) or not 0<=target<34 or not 0<=bucket<5:raise ValueError("Invalid observable signature input")
        key=hashlib.sha256(obs.tobytes()+mask.tobytes()).digest()
        value=self.inputs.setdefault(key,[0,0]);value[0]|=1<<(bucket*34+target);value[1]+=1
        coarse=hashlib.sha256(obs[:6].tobytes()+mask.tobytes()).digest()
        self.coarse[coarse]=self.coarse.get(coarse,0)|(1<<bucket);self.n+=1

    def finish(self):
        conflicts=conflicting_rows=labeled_distinct=cross_inputs=cross_labeled=0;limit=(1<<34)-1
        for pairs,n in self.inputs.values():
            first=pairs&limit;others=0
            for bucket in range(1,5):others|=(pairs>>(bucket*34))&limit
            labels=first|others;labeled_distinct+=labels.bit_count()
            conflicts+=labels.bit_count()>1
            if labels.bit_count()>1:conflicting_rows+=n
            cross_inputs+=bool(first and others);cross_labeled+=(first&others).bit_count()
        return {'observations':self.n,'distinct_observable_signatures':len(self.inputs),'repeated_observable_observations':self.n-len(self.inputs),'repeated_labeled_observations':self.n-labeled_distinct,'input_signatures_with_label_disagreement':conflicts,'observations_in_label_disagreement_groups':conflicting_rows,'fold0_vs_other_input_overlap_signatures':cross_inputs,'fold0_vs_other_labeled_overlap_signatures':cross_labeled,'coarse_hand_overlap_signatures':sum(bool(value&1 and value&~1) for value in self.coarse.values()),'observable_definition':'Full approved obs plus legal discard mask; no identity/outcome/hidden data','coarse_definition':'Own hand/winds planes0:6 plus legal mask, ignores public-history/meld context; overlap is only a potential near-duplicate flag','filtered_observations':0,'interpretation':'Repeated legal states are retained; source IDs/ingestion are separately checked. Conflicting observed labels are not proof of optimal-strategy ambiguity or a Bayes error bound.'}


def analyze_model(model,split,prediction_path=None):
    torch.set_num_threads(1);model.eval();diagnostics=ScoreDiagnostics();groups={};matches=set();uids=set()
    stream=gzip.open(prediction_path,'wt',encoding='utf-8') if prediction_path else None
    try:
        with torch.inference_mode():
            for features,targets,masks,meta in split.batches(512):
                logs=masked_log_probabilities(model(torch.from_numpy(features)),torch.from_numpy(masks)).numpy()
                diagnostics.update(logs,targets,masks);ordered=np.argsort(-logs,axis=1,kind='stable');probabilities=np.exp(logs)
                keys={}
                for i,target in enumerate(targets):
                    uid=str(meta['uid'][i]);match=str(meta['match_id'][i]);uids.add(uid);matches.add(match)
                    for key in ('uid:'+uid,'phase:post_meld' if meta['post_meld'][i] else 'phase:draw','family:'+TILE_LIST[int(target)][0]):keys.setdefault(key,[]).append(i)
                    if stream:
                        legal=np.flatnonzero(masks[i]).tolist()
                        row={'shard_path':meta['shard_path'],'shard_row':int(meta['shard_row'][i]),'match_id':match,'player_uid':uid,'seat':int(meta['seat'][i]),'target_class':int(target),'predicted_class':int(ordered[i,0]),'top3':ordered[i,:min(3,len(legal))].tolist(),'legal_classes':legal,'target_log_probability':float(logs[i,target]),'class_scores':probabilities[i].tolist()}
                        stream.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
                for key,rows in keys.items():groups.setdefault(key,MetricAccumulator()).update(logs[rows],targets[rows],masks[rows])
    finally:
        if stream:stream.close()
    return dict(diagnostics.finish(),match_count=len(matches),player_count=len(uids),groups={key:_finish(value) if not key.startswith('uid:') or value.n>=100 else {'samples':value.n,'status':'INSUFFICIENT_SUPPORT_LT_100'} for key,value in groups.items()})


def audit_repetition(corpus):
    audit=SignatureAudit();trajectories={};duplicate_trajectories=0;cross_fold_trajectories=0;examples=[]
    for shard in corpus.shards:
        with np.load(corpus.root/shard['path']/'samples.npz',allow_pickle=False) as z:
            selected=np.isin(z['split'],[0,1]);obs=z['obs'][selected];masks=z['mask'][selected,2:36];targets=z['act'][selected]-2;matches=z['match_id'][selected];seats=z['seat'][selected]
        for i,match in enumerate(matches):audit.add(obs[i],masks[i],int(targets[i]),development_bucket(str(match)))
        for match in np.unique(matches):
            rows=np.flatnonzero(matches==match)
            key=hashlib.sha256(obs[rows].tobytes()+masks[rows].tobytes()+targets[rows].tobytes()+seats[rows].tobytes()).digest()
            bucket=development_bucket(str(match))
            if key in trajectories:
                prior_match,prior_bucket=trajectories[key];duplicate_trajectories+=1;cross_fold_trajectories+=prior_bucket!=bucket
                if len(examples)<10:examples.append([prior_match,str(match)])
            else:trajectories[key]=(str(match),bucket)
    expansion=json.loads((corpus.root/'expansion_report.json').read_text())
    return dict(audit.finish(),identical_encoded_trajectories_extra_matches=duplicate_trajectories,identical_trajectory_cross_bucket_extra_matches=cross_fold_trajectories,trajectory_examples=examples,source_ingestion_duplicates=expansion['duplicate_ingestions'],source_ingestion_evidence='Previously audited unique match/source identities; no new extraction or filtering')


def run_error_analysis(dataset,output):
    output=Path(output);validate_optimization_output(output)
    if any((output/name).exists() for name in ('protocol.json','experiment_registry.json','candidate_freeze.json','model_freeze.json','training_complete.json')):
        raise ValueError('Diagnostics output is protocol-bound or frozen; use a separate output directory')
    output.mkdir(parents=True,exist_ok=True)
    write_json_report(output/'error_analysis.json',{'status':'RUNNING'})
    try:return _run_error_analysis(dataset,output)
    except BaseException as exc:
        write_json_report(output/'error_analysis.json',{'status':'FAIL','reason':repr(exc)})
        raise


def _run_error_analysis(dataset,output):
    start=time.perf_counter()
    corpus=DevelopmentCorpus(dataset)
    lineage=evaluation_lineage(corpus);write_json_report(output/'evaluation_lineage.json',lineage)
    split=corpus.split('validation');assert_fair_saved_v2(corpus,split.match_ids)
    checkpoint=Path('artifacts/models/mahjong_discard_mlp_v2.pt')
    model,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
    analysis=analyze_model(model,split,output/'baseline_validation_predictions.jsonl.gz')
    analysis.update(status='PASS',checkpoint_sha256=metadata['checkpoint_sha256'],cohort='Original Phase2.1 validation; previously used for model selection, development diagnostics only',cohort_match_ids_sha256=canonical_hash(sorted(split.match_ids)),dataset_contract_sha256=corpus.contract_sha256,repetition_audit=audit_repetition(corpus),seconds=time.perf_counter()-start,maximum_resident_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write_json_report(output/'error_analysis.json',analysis)
    print(json.dumps({key:analysis[key] for key in ('status','match_count','player_count','expected_calibration_error','mean_top1_confidence','brier_score','seconds')},indent=2))
    return analysis


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,default=Path('datasets/expanded_strict_v2'));parser.add_argument('--output',type=Path,default=Path('artifacts/phase2_2'));args=parser.parse_args()
    run_error_analysis(args.dataset,args.output)


if __name__=='__main__':main()
