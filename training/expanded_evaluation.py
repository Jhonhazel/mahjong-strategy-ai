"""Frozen common-cohort evaluation; streaming evidence and match-level uncertainty."""
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
import gzip
import itertools
import json
import math
from pathlib import Path

import numpy as np
import torch

from app.mlp import masked_log_probabilities
from app.model_checkpoint import load_checkpoint
from app.domain.tiles import TILE_LIST
from training.dataset_loader import file_sha256
from training.expanded_dataset import canonical_hash
from training.expanded_training import MetricAccumulator,ShardCorpus
from training.reporting import write_json_report

METRICS=("nll","top1","top3","macro_f1_34","macro_f1_supported","legal_rate")
EVIDENCE=("selection_freeze.json","model_freeze.json","protocol.json","test_predictions.jsonl.gz","per_class_metrics.csv","confusion_matrix.csv","confidence_intervals.json","subgroup_metrics.json","baseline_metrics.json","independent_recalculation.json")


def check(condition,message):
    if not condition:raise ValueError(message)


def prediction_records(path):
    with gzip.open(path,"rt",encoding="utf-8") as stream:
        for line in stream:yield json.loads(line)


def recalculate_saved_predictions(path,single_model_name=None):
    """Independent Python counters/math.fsum; never call the NumPy metric code."""
    accum={}
    for row in prediction_records(path):
        target=row["target_class"];legal=row["legal_classes"]
        check(type(target)is int and 0<=target<34 and target in legal,"Invalid saved target")
        model_predictions=row['models'] if single_model_name is None else {single_model_name:row}
        for name,prediction in model_predictions.items():
            state=accum.setdefault(name,{"n":0,"loss":0.,"correct3":0,"legal":0,"support":Counter(),"predicted":Counter(),"tp":Counter(),"confusion":[[0]*34 for _ in range(34)]})
            predicted=prediction["predicted_class"];top3=prediction["top3"];score=prediction["target_log_probability"]
            check(predicted in legal and len(set(top3))==len(top3)==min(3,len(legal)) and set(top3).issubset(legal) and top3[0]==predicted and math.isfinite(score),"Invalid saved legal prediction")
            probabilities=prediction["class_scores"]
            check(len(probabilities)==34 and all(math.isfinite(p) and 0<=p<=1 for p in probabilities) and math.isclose(math.fsum(probabilities),1.,abs_tol=1e-5),"Invalid saved scores")
            check(all(probabilities[i]==0 for i in range(34) if i not in legal),"Illegal class has saved probability")
            check(probabilities[predicted]>=max(probabilities)-1e-7,"Saved prediction is not highest-scored")
            state["n"]+=1;state["loss"]=math.fsum((state["loss"],-score));state["correct3"]+=target in top3;state["legal"]+=predicted in legal
            state["support"][target]+=1;state["predicted"][predicted]+=1;state["tp"][target]+=target==predicted;state["confusion"][target][predicted]+=1
    check(bool(accum),"No saved predictions")
    result={}
    for name,s in accum.items():
        f1={i:2*s["tp"][i]/(s["support"][i]+s["predicted"][i]) if s["support"][i]+s["predicted"][i] else 0. for i in range(34)}
        result[name]={"samples":s["n"],"nll":s["loss"]/s["n"],"top1":sum(s["tp"].values())/s["n"],"top3":s["correct3"]/s["n"],"macro_f1_34":math.fsum(f1.values())/34,"macro_f1_supported":math.fsum(f1[i] for i in s["support"])/len(s["support"]),"legal_rate":s["legal"]/s["n"],"confusion_matrix":s["confusion"]}
    return result


def match_bootstrap(counts,resamples=2000,seed=2026,reference_model='original_phase2',candidate_model='selected_v2'):
    check(bool(counts) and resamples>=2,"Nonempty matches and at least two bootstrap draws required")
    matches=sorted(counts);names=sorted(counts[matches[0]]["correct"])
    n=np.array([counts[m]["n"] for m in matches],np.int64)
    correct={name:np.array([counts[m]["correct"][name] for m in matches],np.int64) for name in names}
    rng=np.random.default_rng(seed);draws={name:[] for name in names};deltas=[]
    for start in range(0,resamples,64):
        sampled=rng.integers(0,len(matches),size=(min(64,resamples-start),len(matches)))
        denominator=n[sampled].sum(axis=1)
        fractions={name:values[sampled].sum(axis=1)/denominator for name,values in correct.items()}
        for name,values in fractions.items():draws[name].extend(values.tolist())
        deltas.extend((fractions[candidate_model]-fractions[reference_model]).tolist())
    interval=lambda values:np.quantile(values,[.025,.975]).tolist()
    delta_key='paired_delta_selected_vs_phase2' if (reference_model,candidate_model)==('original_phase2','selected_v2') else 'paired_delta_candidate_vs_reference'
    return {"method":"Percentile paired bootstrap of complete matches; decision-weighted accuracy within each resampled cohort","matches":len(matches),"samples":int(n.sum()),"resamples":resamples,"seed":seed,"models":{name:{"top1":float(correct[name].sum()/n.sum()),"interval_95":interval(values)} for name,values in draws.items()},delta_key:{"point":float((correct[candidate_model].sum()-correct[reference_model].sum())/n.sum()),"interval_95":interval(deltas)},"limitation":"Known-player match-disjoint cohort; intervals do not establish unseen-player generalization or Mahjong winning strength"}


def _frozen_models(corpus,output,checkpoint):
    frozen=json.loads((output/"selection_freeze.json").read_text())
    check(frozen["status"]=="FROZEN" and frozen["test_labels_used_for_selection"] is False,"Model selection is not frozen")
    check(frozen["dataset_contract_sha256"]==corpus.contract_sha256,"Frozen dataset contract changed")
    check(file_sha256(output/"protocol.json")==frozen["protocol_sha256"],"Frozen experiment protocol changed")
    check(str(checkpoint)==frozen["checkpoint"] and file_sha256(checkpoint)==frozen["checkpoint_sha256"],"Frozen selected weights changed")
    selected,metadata=load_checkpoint(checkpoint,expected_contract=corpus.contract)
    if metadata.get("test_evaluation") is None:
        check(file_sha256(checkpoint.with_suffix(".metadata.json"))==frozen["pre_evaluation_metadata_sha256"],"Frozen selected metadata changed")
    models={"selected_v2":selected}
    for entry in frozen["comparison_models"]:
        path=Path(entry["checkpoint"])
        check(file_sha256(path)==entry["checkpoint_sha256"] and file_sha256(path.with_suffix(".metadata.json"))==entry["metadata_sha256"],"Frozen comparison model changed")
        contract=json.loads(Path("datasets/data_contract.json").read_text()) if entry["name"]=="original_phase2" else corpus.contract
        models[entry["name"]],comparison_metadata=load_checkpoint(path,expected_contract=contract)
        if entry["name"]==frozen["selected_experiment"]:
            immutable=lambda value:{k:v for k,v in value.items() if k!="test_evaluation"}
            check(immutable(metadata)==immutable(comparison_metadata),"Selected metadata differs from frozen experiment")
    identity={"status":"FROZEN","dataset_contract_sha256":corpus.contract_sha256,"selection_sha256":file_sha256(output/"selection_freeze.json"),"protocol_sha256":frozen["protocol_sha256"],"selected_sha256":frozen["checkpoint_sha256"],"metadata_content_sha256":canonical_hash({k:v for k,v in metadata.items() if k!="test_evaluation"}),"comparison_models":frozen["comparison_models"],"test_used_for_selection":False}
    path=output/"model_freeze.json"
    if path.exists():check(json.loads(path.read_text())==identity,"Evaluation freeze changed")
    else:write_json_report(path,identity)
    return frozen,models,metadata


def _saved_matches(expected,actual):
    for key in ("match_id","player_uid","seat","source_ordinal","shard_path","shard_row","target_class","legal_classes","post_meld"):
        check(expected[key]==actual[key],f"Saved prediction identity differs: {key}")
    check(set(expected["models"])==set(actual["models"]),"Saved model list differs")
    for name,before in expected["models"].items():
        after=actual["models"][name]
        check(before["predicted_class"]==after["predicted_class"] and before["top3"]==after["top3"],"Saved ranks differ from actual inference")
        check(math.isclose(before["target_log_probability"],after["target_log_probability"],abs_tol=1e-7,rel_tol=0) and np.allclose(before["class_scores"],after["class_scores"],atol=1e-7,rtol=1e-5),"Saved scores differ from actual inference")


def _test_pass(corpus,models,output,verify=False):
    corpus.allow_test=True
    test=corpus.split("test")
    check(test.samples>0,"No fresh locked test observations")
    counts=corpus.quality["splits"]["train"]["class_distribution"]
    prior=np.array([counts.get(tile,0) for tile in TILE_LIST],np.float64)+1.
    cutoff=float(np.median(prior-1))
    seed=json.loads((output/"protocol.json").read_text())["config"]["seed"]
    rng=np.random.default_rng(seed)
    names=list(models)+["class_prior","uniform_random_legal"]
    metrics={name:MetricAccumulator() for name in names}
    match_counts={};subgroups=defaultdict(dict)
    temporary=output/"test_predictions.tmp"
    saved=iter(prediction_records(output/"test_predictions.jsonl.gz")) if verify else None
    stream=None if verify else gzip.open(temporary,"wt",encoding="utf-8")
    for model in models.values():model.eval()
    try:
        with torch.inference_mode():
            for features,targets,masks,meta in test.batches(512):
                x=torch.from_numpy(features);legal=torch.from_numpy(masks)
                logs={name:masked_log_probabilities(model(x),legal).numpy() for name,model in models.items()}
                weights=np.where(masks,prior,0.)
                probabilities=weights/weights.sum(axis=1,keepdims=True)
                prior_logs=np.full(probabilities.shape,-np.inf)
                prior_logs[masks]=np.log(probabilities[masks])
                uniform=np.full(probabilities.shape,-np.inf)
                uniform[masks]=np.broadcast_to(-np.log(masks.sum(axis=1))[:,None],masks.shape)[masks]
                logs.update(class_prior=prior_logs,uniform_random_legal=uniform)
                rankings={name:np.argsort(-values,axis=1,kind="stable") for name,values in logs.items()}
                rankings["uniform_random_legal"]=np.argsort(-np.where(masks,rng.random(masks.shape),-np.inf),axis=1,kind="stable")
                for name in names:metrics[name].update(logs[name],targets,masks,rankings[name])
                probabilities={name:np.exp(value) for name,value in logs.items()}
                group_rows=defaultdict(list)
                for i,target in enumerate(targets):
                    match=str(meta["match_id"][i]);uid=str(meta["uid"][i]);ordinal=int(meta["source_ordinal"][i]);legal_classes=np.flatnonzero(masks[i]).tolist()
                    record={"match_id":match,"player_uid":uid,"seat":int(meta["seat"][i]),"source_ordinal":ordinal,"shard_path":meta["shard_path"],"shard_row":int(meta["shard_row"][i]),"target_class":int(target),"legal_classes":legal_classes,"post_meld":bool(meta["post_meld"][i]),"models":{name:{"predicted_class":int(rankings[name][i,0]),"top3":[int(c) for c in rankings[name][i,:min(3,len(legal_classes))]],"target_log_probability":float(logs[name][i,target]),"class_scores":probabilities[name][i].tolist()} for name in names}}
                    if verify:
                        expected=next(saved,None)
                        check(expected is not None,"Saved predictions truncated")
                        _saved_matches(expected,record)
                    else:stream.write(json.dumps(record,allow_nan=False,separators=(",",":"))+"\n")
                    counter=match_counts.setdefault(match,{"n":0,"correct":{name:0 for name in names}})
                    counter["n"]+=1
                    for name in names:counter["correct"][name]+=int(rankings[name][i,0]==target)
                    for group in (f"player:{uid}","player_seen:training" if uid in corpus.quality["splits"]["train"]["player_distribution"] else "player_seen:unseen_in_training",f"legal_choices:{len(legal_classes)}","phase:post_meld" if record["post_meld"] else "phase:draw",f"source_stratum:{min(9,ordinal*10//corpus.contract['source_games'])}","tile_frequency:above_train_median" if prior[target]-1>cutoff else "tile_frequency:below_or_equal_train_median"):
                        group_rows[group].append(i)
                for group,indices in group_rows.items():
                    for name in names:
                        accumulator=subgroups[group].setdefault(name,MetricAccumulator())
                        accumulator.update(logs[name][indices],targets[indices],masks[indices],rankings[name][indices])
        if verify:check(next(saved,None) is None,"Saved predictions contain extra rows")
    finally:
        if stream is not None:stream.close()
    if not verify:temporary.replace(output/"test_predictions.jsonl.gz")
    groups={group:{name:acc.finish() for name,acc in values.items()} for group,values in subgroups.items()}
    # Small-UID groups retain counts but avoid unstable per-class claims.
    groups={group:values if not group.startswith("player:") or next(iter(values.values()))["samples"]>=100 else {name:{"samples":m["samples"],"status":"INSUFFICIENT_SUPPORT_LT_100"} for name,m in values.items()} for group,values in groups.items()}
    return {name:acc.finish() for name,acc in metrics.items()},match_counts,{"groups":groups,"player_minimum_samples":100,"tile_frequency_training_median":cutoff,"source_strata":"Ten equal source-ordinal ranges; not calendar-time splits"},test


def _write_tables(output,models):
    with (output/"per_class_metrics.csv").open("w",newline="") as stream:
        fields=["model","class_id","tile","support","predicted_count","precision","recall","f1"]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for name,metric in models.items():
            for row in metric["per_class"]:writer.writerow(dict(row,model=name))
    with (output/"confusion_matrix.csv").open("w",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(["model","true_class"]+list(range(34)))
        for name,metric in models.items():
            for i,row in enumerate(metric["confusion_matrix"]):writer.writerow([name,i]+row)


def evaluate_expanded(dataset,output,checkpoint,verify_existing=False,resume=False,bootstrap_samples=2000):
    output,checkpoint=Path(output),Path(checkpoint)
    check(not(verify_existing and resume),"Choose verify-existing or resume")
    report_path=output/"evaluation_metrics.json"
    existing=json.loads(report_path.read_text()) if report_path.exists() else None
    if existing is not None:
        check((existing["status"]=="PASS" and verify_existing) or (existing["status"] in ("FAIL","RUNNING") and resume),"Existing held-out record requires verify-existing or same-frozen-model resume")
    else:check(not verify_existing and not resume,"No existing evaluation to verify/resume")
    if verify_existing:
        for name in EVIDENCE:check(name in existing["artifact_sha256"] and file_sha256(output/name)==existing["artifact_sha256"][name],f"Missing/changed evaluation artifact: {name}")
        check(file_sha256(checkpoint.with_suffix(".metadata.json"))==existing["metadata_sha256"],"Final metadata changed")
    torch.set_num_threads(1)
    corpus=ShardCorpus(dataset)
    frozen,models,metadata=_frozen_models(corpus,output,checkpoint)
    if not verify_existing:write_json_report(report_path,{"status":"RUNNING","checkpoint_sha256":frozen["checkpoint_sha256"]})
    try:
        metrics,counts,subgroups,test=_test_pass(corpus,models,output,verify_existing)
        independent=recalculate_saved_predictions(output/"test_predictions.jsonl.gz")
        for name,values in metrics.items():
            for key in METRICS:check(math.isclose(values[key],independent[name][key],abs_tol=1e-7,rel_tol=0),"Independent saved metric recalculation mismatch")
            check(values["confusion_matrix"]==independent[name]["confusion_matrix"],"Independent confusion matrix mismatch")
        intervals=match_bootstrap(counts,bootstrap_samples)
        result={"status":"PASS","evaluated_at_utc":datetime.now(timezone.utc).isoformat(),"checkpoint_sha256":frozen["checkpoint_sha256"],"dataset_contract_sha256":corpus.contract_sha256,"test_samples":test.samples,"test_matches":len(test.match_ids),"test_match_ids":sorted(test.match_ids),"models":metrics,"selection":"Frozen minimum validation NLL; no fresh-test tuning","test_labels_used_for_selection":False,"confidence_intervals":intervals,"independent_recalculation":"PASS: independent Python counters and math.fsum over saved prediction records","historical_test":"Original 102 decisions/five matches are a previously observed cohort, excluded from this fresh comparison and from training","limitations":["Known-player overlap across match-disjoint splits","Observed behavior is not an optimal-action label or winning probability","All four roster seats broaden the population relative to original tracked-seat subset","Unseen-player generalization is not established"]}
        summary={"checkpoint_sha256":result["checkpoint_sha256"],"samples":test.samples,"matches":len(test.match_ids),"dataset_contract_sha256":corpus.contract_sha256,"metrics":{key:metrics["selected_v2"][key] for key in METRICS},"report":"phase2_1/evaluation_metrics.json"}
        if verify_existing:
            check(existing["models"]==result["models"] and existing["test_match_ids"]==result["test_match_ids"] and existing["confidence_intervals"]==intervals,"Recomputed held-out results differ")
            check(metadata.get("test_evaluation")==summary,"Final metadata is incomplete")
            write_json_report(output/"reverification.json",{"status":"PASS","checkpoint_sha256":result["checkpoint_sha256"],"saved_predictions_recomputed":True,"independent_recalculation":True})
            return existing
        _write_tables(output,metrics)
        write_json_report(output/"confidence_intervals.json",intervals)
        write_json_report(output/"subgroup_metrics.json",subgroups)
        write_json_report(output/"baseline_metrics.json",{name:metrics[name] for name in ("class_prior","uniform_random_legal","original_phase2")})
        write_json_report(output/"independent_recalculation.json",{"status":"PASS","models":independent})
        metadata["test_evaluation"]=summary
        write_json_report(checkpoint.with_suffix(".metadata.json"),metadata)
        result["artifact_sha256"]={name:file_sha256(output/name) for name in EVIDENCE}
        result["metadata_sha256"]=file_sha256(checkpoint.with_suffix(".metadata.json"))
        write_json_report(report_path,result)  # PASS is the final required publication.
        return result
    except BaseException as exc:
        if not verify_existing:write_json_report(report_path,{"status":"FAIL","checkpoint_sha256":frozen["checkpoint_sha256"],"reason":repr(exc),"recovery":"resume only the same frozen data/configuration/weights"})
        else:write_json_report(output/"reverification.json",{"status":"FAIL","reason":repr(exc)})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",type=Path,default=Path("datasets/expanded_strict_v2"))
    parser.add_argument("--output",type=Path,default=Path("artifacts/phase2_1"))
    parser.add_argument("--checkpoint",type=Path,default=Path("artifacts/models/mahjong_discard_mlp_v2.pt"))
    parser.add_argument("--verify-existing",action="store_true");parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    result=evaluate_expanded(args.dataset,args.output,args.checkpoint,args.verify_existing,args.resume)
    print(json.dumps({"status":result["status"],"samples":result["test_samples"],"matches":result["test_matches"],"models":{name:{key:values[key] for key in METRICS} for name,values in result["models"].items()},"confidence_intervals":result["confidence_intervals"]},indent=2))


if __name__=="__main__":main()
