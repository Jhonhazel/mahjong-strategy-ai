"""Memory-bounded MLP experiments; model selection receives train/validation only."""
import argparse
import csv
from dataclasses import asdict, dataclass
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import shutil
import time

import numpy as np
import torch

from app.domain.tiles import TILE_LIST
from app.mlp import MahjongDiscardMLP, encode_observations, masked_cross_entropy, masked_log_probabilities
from training.expanded_dataset import SPLITS, canonical_hash, read_commits, require, split_for_match, validate_expansion
from training.dataset_loader import file_sha256
from training.reporting import write_json_report
from training.train_mlp import EarlyStopping, TrainConfig, select_device, weights_sha256


class ShardCorpus:
    def __init__(self, root, allow_test=False):
        self.root = Path(root)
        self.quality = validate_expansion(self.root)
        self.contract = json.loads((self.root / "data_contract.json").read_text())
        self.contract_sha256 = file_sha256(self.root / "data_contract.json")
        self.shards = self.contract["shards"]
        self.allow_test = allow_test

    def split(self, name):
        if name not in SPLITS:
            raise ValueError("Unknown expanded split")
        if name in ("test", "historical_test") and not self.allow_test:
            raise ValueError("Held-out split is locked until model freeze")
        counts = {m: n for m,n in self.quality["samples_per_match"].items() if split_for_match(m, self.contract["original_roles"]) == name}
        return ShardSplit(self, name, counts)


@dataclass(frozen=True)
class ShardSplit:
    corpus: ShardCorpus
    name: str
    match_counts: dict[str, int]
    source_roles: tuple[str, ...] | None = None

    def __post_init__(self):
        if self.source_roles is not None and (self.name not in ("train","validation") or self.source_roles != ("train","validation")):
            raise ValueError("Development remapping permits original train/validation roles only")

    @property
    def match_ids(self):
        return set(self.match_counts)

    @property
    def samples(self):
        return sum(self.match_counts.values())

    @property
    def identity(self):
        value=[self.corpus.contract_sha256, self.name, self.match_counts]
        if self.source_roles is not None:value.append(list(self.source_roles))
        return canonical_hash(value)

    def batches(self, batch_size, seed=0, epoch=0, shuffle=False):
        if batch_size < 1:
            raise ValueError("Positive batch size required")
        rng = np.random.default_rng(np.random.SeedSequence([seed,epoch]))
        indices = np.arange(len(self.corpus.shards))
        if shuffle: rng.shuffle(indices)
        for shard_index in indices:
            shard = self.corpus.shards[int(shard_index)]
            with np.load(self.corpus.root / shard["path"] / "samples.npz", allow_pickle=False) as storage:
                roles = storage["split"]
                matches = storage["match_id"]
                allowed = np.fromiter((match in self.match_counts for match in matches), dtype=bool, count=len(matches))
                role_mask=np.isin(roles,[SPLITS.index(name) for name in self.source_roles]) if self.source_roles is not None else roles==SPLITS.index(self.name)
                rows = np.flatnonzero(role_mask & allowed)
                if not len(rows): continue
                if shuffle: rng.shuffle(rows)
                arrays = {key: storage[key] for key in ("obs","mask","act","uid","seat","post_meld","source_ordinal","source_row","decision_order")}
            for offset in range(0,len(rows),batch_size):
                chosen = rows[offset:offset+batch_size]
                features = encode_observations(arrays["obs"][chosen])
                targets = arrays["act"][chosen].astype(np.int64)-2
                masks = arrays["mask"][chosen,2:36].copy()
                meta = {key: values[chosen] for key,values in arrays.items() if key not in ("obs","mask","act")}
                meta.update(match_id=matches[chosen], shard_path=shard["path"], shard_row=chosen.copy())
                yield features, targets, masks, meta


def nested_match_subset(training, budget):
    if training.name != "train" or budget < 1:
        raise ValueError("Learning curves require a positive training-only budget")
    ordered = sorted(training.match_counts, key=lambda m: hashlib.sha256(("phase2.1-learning-curve-v1:"+m).encode()).digest())
    selected, n = {}, 0
    for match in ordered:
        selected[match] = training.match_counts[match]
        n += selected[match]
        if n >= budget: break
    return ShardSplit(training.corpus,"train",selected)


class MetricAccumulator:
    def __init__(self):
        self.confusion = np.zeros((34,34),np.int64)
        self.n = self.correct3 = 0
        self.nll = 0.

    def update(self, logs, targets, masks, rankings=None):
        if logs.ndim != 2 or logs.shape[1] != 34 or masks.shape != logs.shape or masks.dtype != np.bool_ or targets.shape != (len(logs),) or targets.dtype.kind not in "iu" or not len(logs):
            raise ValueError("Invalid metric batch shapes/dtypes")
        if np.any((targets<0)|(targets>=34)) or not masks[np.arange(len(logs)),targets].all() or not np.isfinite(logs[masks]).all() or not np.isneginf(logs[~masks]).all():
            raise ValueError("Invalid legal target/log probabilities")
        if not np.allclose(np.exp(logs).sum(axis=1),1.,rtol=1e-5,atol=1e-6):
            raise ValueError("Log probabilities do not normalize")
        order = np.argsort(-logs,axis=1,kind="stable") if rankings is None else rankings
        if order.shape != logs.shape or np.any(np.sort(order,axis=1) != np.arange(34)):
            raise ValueError("Expected a full class permutation")
        ranked_logs=np.take_along_axis(logs,order,axis=1)
        if np.any(ranked_logs[:,1:] > ranked_logs[:,:-1]):
            raise ValueError("Invalid ranking")
        predicted=order[:,0]
        if not masks[np.arange(len(logs)),predicted].all(): raise ValueError("Illegal prediction")
        np.add.at(self.confusion,(targets,predicted),1)
        self.correct3 += int(((order[:,:3]==targets[:,None]) & np.take_along_axis(masks,order[:,:3],axis=1)).any(axis=1).sum())
        self.nll += float(-logs[np.arange(len(logs)),targets].astype(np.float64).sum())
        self.n += len(logs)

    def finish(self):
        if not self.n: raise ValueError("No metric observations")
        cm=self.confusion
        tp=np.diag(cm); support=cm.sum(axis=1); predicted=cm.sum(axis=0)
        precision=np.divide(tp,predicted,out=np.zeros(34),where=predicted!=0)
        recall=np.divide(tp,support,out=np.zeros(34),where=support!=0)
        f1=np.divide(2*precision*recall,precision+recall,out=np.zeros(34),where=(precision+recall)!=0)
        return {"samples":self.n,"nll":self.nll/self.n,"top1":float(tp.sum()/self.n),"top3":self.correct3/self.n,"macro_f1_34":float(f1.mean()),"macro_f1_supported":float(f1[support>0].mean()),"supported_classes":int((support>0).sum()),"legal_rate":1.,"confusion_matrix":cm.tolist(),"per_class":[{"class_id":i,"tile":tile,"support":int(support[i]),"predicted_count":int(predicted[i]),"precision":float(precision[i]),"recall":float(recall[i]),"f1":float(f1[i])} for i,tile in enumerate(TILE_LIST)]}


def evaluate_stream(model, split, batch_size=512, device="cpu"):
    model.eval()
    acc=MetricAccumulator()
    with torch.inference_mode():
        for features,targets,masks,_ in split.batches(batch_size):
            logs=masked_log_probabilities(model(torch.from_numpy(features).to(device)),torch.from_numpy(masks).to(device)).cpu().numpy()
            acc.update(logs,targets,masks)
    return acc.finish()


def cpu_tree(value):
    if isinstance(value,torch.Tensor): return value.detach().cpu().clone()
    if isinstance(value,dict): return {key:cpu_tree(item) for key,item in value.items()}
    if isinstance(value,list): return [cpu_tree(item) for item in value]
    if isinstance(value,tuple): return tuple(cpu_tree(item) for item in value)
    return value


def save_training_state(path,value,keep_generations=None):
    if keep_generations is not None and keep_generations!=2:raise ValueError("Bounded retention keeps current and previous committed generations")
    pointer_path=path.with_suffix('.sha256.json')
    previous=json.loads(pointer_path.read_text()).get('generation') if pointer_path.exists() else None
    temporary=path.with_suffix(".tmp")
    torch.save(cpu_tree(value),temporary)
    digest=file_sha256(temporary)
    epoch=len(value["history"])
    generation=path.with_name(f"{path.stem}.{epoch:04d}.{digest}.pt")
    temporary.replace(generation)
    # Commit one atomic pointer after the immutable generation is complete.
    # A failed pointer publication leaves the previous generation recoverable.
    write_json_report(path.with_suffix(".sha256.json"),{"sha256":digest,"generation":generation.name})
    if keep_generations==2:
        for old in path.parent.glob(path.stem+'.*.pt'):
            if old.name not in {generation.name,previous}:old.unlink()


def training_state_exists(path):
    return path.is_file() or path.with_suffix(".sha256.json").is_file()


def load_training_state(path):
    pointer=json.loads(path.with_suffix(".sha256.json").read_text())
    name=pointer.get("generation",path.name)  # Existing completed legacy states remain loadable.
    if Path(name).name!=name:raise ValueError("Unsafe resume generation path")
    generation=path.parent/name
    if generation.resolve().parent!=path.parent.resolve() or not generation.is_file() or file_sha256(generation)!=pointer["sha256"]:raise ValueError("Resume checkpoint checksum mismatch")
    return torch.load(generation,map_location="cpu",weights_only=True)


@dataclass(frozen=True)
class StreamingRun:
    model: MahjongDiscardMLP
    summary: dict


def train_sharded(training,validation,config,run_dir,resume=False,stop_after_epoch=None,model_spec=None,checkpoint_retention=None):
    if training.name!="train" or validation.name!="validation":
        raise ValueError("Model selection accepts train and validation splits only")
    if training.match_ids.intersection(validation.match_ids): raise ValueError("Train/validation match overlap")
    if not training.samples or not validation.samples: raise ValueError("Nonempty train/validation required")
    if config.max_epochs<1 or config.patience<1 or config.batch_size<1 or config.cpu_threads<1 or not 0<config.learning_rate<1 or config.weight_decay<0:
        raise ValueError("Invalid training config")
    run_dir=Path(run_dir); run_dir.mkdir(parents=True,exist_ok=True)
    path=run_dir/"training_resume.pt"
    identity={"config":asdict(config),"training":training.identity,"validation":validation.identity}
    if model_spec is not None:identity['architecture_spec']=model_spec
    if training_state_exists(path) and not resume: raise ValueError("Existing training state; use resume or a new run directory")
    torch.set_num_threads(config.cpu_threads)
    device,probes=select_device(config.device)
    random.seed(config.seed); np.random.seed(config.seed); torch.manual_seed(config.seed)
    torch.use_deterministic_algorithms(device=="cpu")
    model=MahjongDiscardMLP(model_spec).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=config.learning_rate,weight_decay=config.weight_decay)
    stop=EarlyStopping(config.patience)
    history,steps,elapsed=[],0,0.
    initial=weights_sha256(model.state_dict())
    best_state=best_metrics=None
    if resume:
        state=load_training_state(path)
        if state["identity"]!=identity or state["device"]!=device: raise ValueError("Resume identity changed")
        model.load_state_dict(state["model"],strict=True); optimizer.load_state_dict(state["optimizer"])
        stop=EarlyStopping(**state["early_stopping"])
        history,steps,elapsed=state["history"],state["steps"],state["elapsed"]
        best_state,best_metrics,initial=state["best_state"],state["best_metrics"],state["initial_hash"]
        torch.set_rng_state(state["torch_rng"])
        if device=="mps": torch.mps.set_rng_state(state["mps_rng"])
    started=time.perf_counter()
    status="PASS"
    for epoch in range(len(history)+1,config.max_epochs+1):
        if stop.should_stop: break
        model.train(); online=MetricAccumulator(); loss_sum=0.
        for features,targets,masks,_ in training.batches(config.batch_size,config.seed,epoch,shuffle=True):
            x=torch.from_numpy(features).to(device); y=torch.from_numpy(targets).to(device); legal=torch.from_numpy(masks).to(device)
            optimizer.zero_grad(set_to_none=True)
            logits=model(x); loss=masked_cross_entropy(logits,y,legal)
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):raise RuntimeError("Nonfinite model gradient")
            optimizer.step()
            loss_sum+=float(loss.detach().cpu())*len(targets)
            online.update(masked_log_probabilities(logits.detach(),legal).cpu().numpy(),targets,masks)
            steps+=1
        train_metrics=online.finish()
        metrics=evaluate_stream(model,validation,max(config.batch_size,512),device)
        record={"epoch":epoch,"train_loss":loss_sum/training.samples,"train_top1_online":train_metrics["top1"],"validation_loss":metrics["nll"],"validation_top1":metrics["top1"],"validation_top3":metrics["top3"],"validation_macro_f1_34":metrics["macro_f1_34"],"validation_macro_f1_supported":metrics["macro_f1_supported"]}
        history.append(record)
        if stop.observe(epoch,metrics["nll"]): best_state,best_metrics=cpu_tree(model.state_dict()),metrics
        total_elapsed=elapsed+time.perf_counter()-started
        state={"identity":identity,"device":device,"model":model.state_dict(),"optimizer":optimizer.state_dict(),"early_stopping":asdict(stop),"history":history,"steps":steps,"elapsed":total_elapsed,"best_state":best_state,"best_metrics":best_metrics,"initial_hash":initial,"torch_rng":torch.get_rng_state(),"mps_rng":torch.mps.get_rng_state() if device=="mps" else None}
        save_training_state(path,state,keep_generations=checkpoint_retention)
        write_json_report(run_dir/"history.json",{"status":"RUNNING","identity":identity,"history":history})
        print(json.dumps(dict(record,run=run_dir.name,elapsed_seconds=round(total_elapsed,3))),flush=True)
        if stop_after_epoch is not None and epoch>=stop_after_epoch and epoch<config.max_epochs and not stop.should_stop:
            status="PAUSED"; break
    elapsed+=time.perf_counter()-started
    model=model.cpu(); model.load_state_dict(best_state,strict=True); model.eval()
    selected=weights_sha256(model.state_dict())
    if selected==initial: raise RuntimeError("Selected model weights did not update")
    train_eval=evaluate_stream(model,training,512)
    summary={"status":status,"config":asdict(config),"architecture":"1368->64->34; ReLU; dropout=0.2","parameters":89826,"history":history,"best_epoch":stop.best_epoch,"epochs_executed":len(history),"best_validation_metrics":best_metrics,"selected_train_metrics":train_eval,"generalization_gap":train_eval["top1"]-best_metrics["top1"],"initial_weights_sha256":initial,"best_weights_sha256":selected,"optimizer_steps":steps,"elapsed_seconds":elapsed,"device":device,"device_probe":probes,"stop_reason":"validation_patience" if stop.should_stop else "operational_pause" if status=="PAUSED" else "max_epochs","test_labels_used_for_selection":False,"train_samples":training.samples,"train_matches":len(training.match_ids),"validation_samples":validation.samples,"validation_matches":len(validation.match_ids),"dataset_contract_sha256":training.corpus.contract_sha256,"training_subset_sha256":canonical_hash(training.match_counts),"max_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"resume_semantics":"Atomic completed-epoch state with optimizer/RNG/independent best weights; interrupted partial epoch restarts from last complete epoch","online_train_metric_note":"Dropout active, computed before each optimizer step; final selected_train_metrics use complete eval-mode training split"}
    hidden=[model.architecture['hidden_dim']] if 'hidden_dim' in model.architecture else model.architecture['hidden_dims']
    description='->'.join(str(width) for width in [1368]+hidden+[34])+f"; ReLU; dropout={model.architecture['dropout']}"
    summary.update(architecture=description,architecture_spec=model.architecture,parameters=sum(p.numel() for p in model.parameters()))
    write_json_report(run_dir/"history.json",summary)
    return StreamingRun(model,summary)


def save_run_checkpoint(run,corpus,path,development=None):
    from app.model_checkpoint import build_metadata,save_checkpoint
    from training.phase2_dataset import APPROVED_RUN_ID
    report={"splits":{name:corpus.quality["splits"][name] for name in ("train","validation","test")}}
    metadata=build_metadata(corpus.contract,report,run.summary,model_spec=run.summary.get('architecture_spec'))
    dataset=metadata["dataset"]
    dataset.update(phase1_run_id=APPROVED_RUN_ID,expanded_run_id=corpus.contract["run_id"],dataset_version=corpus.contract["dataset_version"],contract_sha256=corpus.contract_sha256,shards=corpus.contract["shards"],samples_hash_kind=corpus.contract["samples_hash_kind"],historical_test={k:corpus.quality["splits"]["historical_test"][k] for k in ("samples","matches")},exclusion_counts=json.loads((corpus.root/"expansion_report.json").read_text())["status_counts"],player_statistics={"distinct_players":corpus.quality["distinct_players"],"samples_per_player":corpus.quality["players"]})
    dataset["contract_content_sha256"]=canonical_hash(corpus.contract)
    metadata["training"]["training_subset"]={"samples":run.summary["train_samples"],"matches":run.summary["train_matches"],"sha256":run.summary["training_subset_sha256"]}
    if development is not None:
        metadata['optimization_phase']='2.2';metadata['development']=development
    return save_checkpoint(run.model,Path(path),metadata)


def benchmark_loading(split,batch_size=32,limit=64):
    started=time.perf_counter(); n=maximum=0
    for index,(features,targets,masks,_) in enumerate(split.batches(batch_size)):
        n+=len(targets); maximum=max(maximum,features.nbytes+masks.nbytes+targets.nbytes)
        if index+1>=limit: break
    elapsed=time.perf_counter()-started
    return {"samples":n,"seconds":elapsed,"samples_per_second":n/elapsed,"maximum_float32_batch_bytes":maximum,"maximum_shard_rows":max(s["samples"] for s in split.corpus.shards),"max_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"storage_policy":"One compressed shard on CPU; float32 conversion/transfer only for each batch; num_workers=0"}


def _experiment(corpus,training,validation,config,folder,resume):
    from app.model_checkpoint import load_checkpoint
    folder=Path(folder)
    path=folder/"model.pt"
    history_path=folder/"history.json"
    if resume and path.exists() and history_path.exists():
        summary=json.loads(history_path.read_text())
        if summary["status"]=="PASS":
            if summary["config"]!=asdict(config) or summary["dataset_contract_sha256"]!=corpus.contract_sha256 or summary["training_subset_sha256"]!=canonical_hash(training.match_counts): raise ValueError("Completed experiment identity changed")
            model,_=load_checkpoint(path,expected_contract=corpus.contract)
            if weights_sha256(model.state_dict())!=summary["best_weights_sha256"]: raise ValueError("Completed experiment weights changed")
            return StreamingRun(model,summary)
    run=train_sharded(training,validation,config,folder,resume=resume and training_state_exists(folder/"training_resume.pt"))
    save_run_checkpoint(run,corpus,path)
    return run


def run_experiments(root,output,checkpoint,config=None,budgets=(1000,10000,100000),resume=False):
    output,checkpoint=Path(output),Path(checkpoint)
    if (output/"selection_freeze.json").exists(): raise ValueError("Model selection already frozen; do not tune after held-out evaluation")
    if checkpoint.resolve()==Path("artifacts/models/mahjong_discard_mlp.pt").resolve(): raise ValueError("Cannot overwrite original Phase 2 checkpoint")
    config=config or TrainConfig(device="cpu")
    corpus=ShardCorpus(root)
    training,validation=corpus.split("train"),corpus.split("validation")
    output.mkdir(parents=True,exist_ok=True)
    protocol={"version":"phase2.1-experiments-v1","dataset_contract_sha256":corpus.contract_sha256,"config":asdict(config),"budgets":list(budgets),"subset_algorithm":"sha256('phase2.1-learning-curve-v1:' + match_id), nested complete-match prefixes","selection":"minimum validation NLL among full-data candidates only","secondary_metrics":["top1","top3","macro_f1_34"],"regularization_rule":"If full-data selected eval train Top-1 minus validation Top-1 >=0.03, run exactly one additional experiment with weight_decay=0.001 and all other settings fixed","capacity_change":"Not prespecified; keep original architecture to avoid conflating capacity and data effects","test_status":"LOCKED; experiment API cannot open test or historical_test"}
    protocol_path=output/"protocol.json"
    if protocol_path.exists():
        if json.loads(protocol_path.read_text())!=protocol: raise ValueError("Frozen experiment protocol differs")
    else: write_json_report(protocol_path,protocol)
    write_json_report(output/"loader_benchmark.json",benchmark_loading(training,config.batch_size))
    for source,destination in (("expansion_report.json","dataset_expansion_report.json"),("data_contract.json","dataset_contract.json"),("data_quality_report.json","data_quality_report.json")):
        shutil.copyfile(corpus.root/source,output/destination)
    write_json_report(output/"split_report.json",{"algorithm":corpus.contract["grouping"]["algorithm"],"splits":corpus.quality["splits"],"intersections":corpus.quality["split_intersections"],"historical_test_matches":corpus.quality["historical_test_matches"],"player_overlap":corpus.quality["player_overlap"],"test_used_for_selection":False})
    points=[]; eligible=[]; full_run=None; subsets=set()
    for budget in [b for b in budgets if b<training.samples]+[training.samples]:
        subset=nested_match_subset(training,budget)
        subset_hash=canonical_hash(subset.match_counts)
        if subset_hash in subsets: continue
        subsets.add(subset_hash)
        name="full_original" if subset.samples==training.samples else f"curve_{budget}"
        folder=output/"experiments"/name
        run=_experiment(corpus,subset,validation,config,folder,resume)
        summary=run.summary
        point={"name":name,"requested_budget":budget,"train_samples":subset.samples,"train_matches":len(subset.match_ids),"architecture":"1368->64->34","parameters":89826,"config":asdict(config),"best_epoch":summary["best_epoch"],"epochs_executed":summary["epochs_executed"],"training_seconds":summary["elapsed_seconds"],"train":summary["selected_train_metrics"],"validation":summary["best_validation_metrics"],"generalization_gap":summary["generalization_gap"],"checkpoint":str(folder/"model.pt"),"checkpoint_sha256":file_sha256(folder/"model.pt")}
        points.append(point)
        write_json_report(output/"learning_curve.json",{"status":"RUNNING","points":points,"test_used":False})
        if name=="full_original":
            full_run=run; eligible.append(point)
    if full_run.summary["generalization_gap"]>=.03:
        regularized=replace(config,weight_decay=.001)
        folder=output/"experiments"/"full_regularized"
        run=_experiment(corpus,training,validation,regularized,folder,resume)
        summary=run.summary
        eligible.append({"name":"full_regularized","train_samples":training.samples,"train_matches":len(training.match_ids),"architecture":"1368->64->34","parameters":89826,"config":asdict(regularized),"best_epoch":summary["best_epoch"],"epochs_executed":summary["epochs_executed"],"training_seconds":summary["elapsed_seconds"],"train":summary["selected_train_metrics"],"validation":summary["best_validation_metrics"],"generalization_gap":summary["generalization_gap"],"checkpoint":str(folder/"model.pt"),"checkpoint_sha256":file_sha256(folder/"model.pt")})
    selected=min(eligible,key=lambda item:item["validation"]["nll"])
    write_json_report(output/"learning_curve.json",{"status":"PASS","points":points,"test_used":False,"validation_cohort_unchanged":True})
    with (output/"learning_curve.csv").open("w",newline="") as stream:
        writer=csv.writer(stream); writer.writerow(["train_samples","train_matches","best_epoch","train_top1","validation_top1","validation_top3","validation_macro_f1","validation_nll","seconds"])
        for p in points: writer.writerow([p["train_samples"],p["train_matches"],p["best_epoch"],p["train"]["top1"],p["validation"]["top1"],p["validation"]["top3"],p["validation"]["macro_f1_34"],p["validation"]["nll"],p["training_seconds"]])
    write_json_report(output/"experiment_comparison.json",{"status":"PASS","eligible_full_data_candidates":eligible,"selected":selected["name"],"selection_metric":"validation_nll","test_used_for_selection":False,"regularization_triggered":len(eligible)>1})
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    source=Path(selected["checkpoint"])
    if checkpoint.exists():
        if file_sha256(checkpoint)!=selected["checkpoint_sha256"]: raise ValueError("Existing new checkpoint differs from selection")
    else:
        shutil.copyfile(source,checkpoint.with_suffix(".tmp"));checkpoint.with_suffix(".tmp").replace(checkpoint)
    shutil.copyfile(source.with_suffix(".metadata.json"),checkpoint.with_suffix(".metadata.json"))
    chosen_summary=json.loads((source.parent/"history.json").read_text())
    write_json_report(output/"training_history.json",chosen_summary)
    old=Path("artifacts/models/mahjong_discard_mlp.pt")
    frozen={"status":"FROZEN","frozen_at_utc":datetime.now(timezone.utc).isoformat(),"dataset_contract_sha256":corpus.contract_sha256,"protocol_sha256":file_sha256(protocol_path),"selected_experiment":selected["name"],"checkpoint":str(checkpoint),"checkpoint_sha256":file_sha256(checkpoint),"pre_evaluation_metadata_sha256":file_sha256(checkpoint.with_suffix(".metadata.json")),"validation_nll":selected["validation"]["nll"],"comparison_models":[{"name":"original_phase2","checkpoint":str(old),"checkpoint_sha256":file_sha256(old),"metadata_sha256":file_sha256(old.with_suffix(".metadata.json"))}]+[{"name":p["name"],"checkpoint":p["checkpoint"],"checkpoint_sha256":p["checkpoint_sha256"],"metadata_sha256":file_sha256(Path(p["checkpoint"]).with_suffix(".metadata.json"))} for p in eligible],"test_labels_used_for_selection":False}
    write_json_report(output/"selection_freeze.json",frozen)
    return frozen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",type=Path,default=Path("datasets/expanded_strict_v2"))
    parser.add_argument("--output",type=Path,default=Path("artifacts/phase2_1"))
    parser.add_argument("--checkpoint",type=Path,default=Path("artifacts/models/mahjong_discard_mlp_v2.pt"))
    parser.add_argument("--device",choices=("cpu","auto","mps"),default="cpu")
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    result=run_experiments(args.dataset,args.output,args.checkpoint,TrainConfig(device=args.device),resume=args.resume)
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
