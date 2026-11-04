"""Internal development folds; all previously evaluated test matches stay excluded."""
import hashlib
import json
from pathlib import Path

from training.dataset_loader import file_sha256
from training.expanded_dataset import _validate_expansion,canonical_hash,split_for_match
from training.expanded_training import ShardCorpus,ShardSplit
from training.verify_encoder_parity import partition_for_match

FOLD_SALT="phase2.2-dev-fold-v1:"
FOLD_BUCKETS=5


def validate_optimization_output(output):
    output=Path(output).resolve()
    bases={Path.cwd().resolve(),Path(__file__).resolve().parents[1]}
    if any(output.is_relative_to(base/name) for base in bases for name in ('artifacts/phase2','artifacts/phase2_1','datasets')):
        raise ValueError('Cannot write optimization results into protected old artifacts/dataset')
    return output


class DevelopmentCorpus(ShardCorpus):
    def __init__(self,root,group_keys=None):
        self.root=Path(root)
        # The old public audit invalidates old contracts on failure. New-phase
        # verification must be read-only even when an input is corrupt.
        self.quality=_validate_expansion(self.root,None,True,True)
        self.contract=json.loads((self.root/"data_contract.json").read_text())
        self.contract_sha256=file_sha256(self.root/"data_contract.json")
        self.shards=self.contract["shards"]
        self.allow_test=False
        self.group_keys=dict(group_keys or {})
        pool=permitted_matches(self)
        if any(m not in pool or representative not in pool for m,representative in self.group_keys.items()):raise ValueError("Trajectory group outside permitted development pool")
        groups={}
        for match,representative in self.group_keys.items():
            if self.group_keys.get(representative,representative)!=representative:raise ValueError("Noncanonical trajectory group")
            groups.setdefault(representative,{representative}).add(match)
        if any(min(members)!=representative for representative,members in groups.items()):raise ValueError("Trajectory representative must be the smallest source match ID")


def development_bucket(match,group_keys=None):
    representative=(group_keys or {}).get(match,match)
    return int.from_bytes(hashlib.sha256((FOLD_SALT+representative).encode()).digest()[:8],"big")%FOLD_BUCKETS


def role_matches(corpus,role):
    return {m:n for m,n in corpus.quality['samples_per_match'].items() if split_for_match(m,corpus.contract['original_roles'])==role}


def permitted_matches(corpus):
    return {**role_matches(corpus,'train'),**role_matches(corpus,'validation')}


def development_splits(corpus,fold):
    if type(fold)is not int or not 0<=fold<FOLD_BUCKETS:raise ValueError("Unknown development fold")
    pool=permitted_matches(corpus)
    train={m:n for m,n in pool.items() if development_bucket(m,corpus.group_keys)!=fold}
    validation={m:n for m,n in pool.items() if development_bucket(m,corpus.group_keys)==fold}
    if not train or not validation:raise ValueError("Empty development training/validation fold")
    return ShardSplit(corpus,'train',train,('train','validation')),ShardSplit(corpus,'validation',validation,('train','validation'))


def assert_fair_saved_v2(corpus,evaluation_matches):
    overlap=set(role_matches(corpus,'train')).intersection(evaluation_matches)
    if overlap:raise ValueError(f"Saved v2 comparison overlaps previous training matches ({len(overlap)}); retrain E0 on the same split")


def evaluation_lineage(corpus):
    roles={name:sorted(role_matches(corpus,name)) for name in ('train','validation','test','historical_test')}
    historical=sorted(set(roles['test'])|set(roles['historical_test']))
    pool=permitted_matches(corpus)
    if set(pool).intersection(historical):raise ValueError("Historical test entered development")
    old={name:sorted(m for m in corpus.contract['original_roles'] if partition_for_match(m)==name) for name in ('train','validation','test')}
    return {'status':'PASS','dataset_contract_sha256':corpus.contract_sha256,'dataset_run_id':corpus.contract['run_id'],'dataset_samples':corpus.contract['accepted_samples'],'dataset_matches':corpus.contract['accepted_matches'],'evaluation_kind':'internal_group_development','new_blind_test_available':False,'external_source_policy':'No new compatible source supplied/available locally; do not download unknown rulesets','phase2_roles':old,'phase2_1_roles':roles,'historical_test_match_ids':historical,'historical_test_exclusion_sha256':canonical_hash(historical),'permitted_development_match_ids':sorted(pool),'permitted_development_samples':sum(pool.values()),'development_pool_sha256':canonical_hash(pool),'trajectory_group_keys':corpus.group_keys,'trajectory_group_sha256':canonical_hash(corpus.group_keys),'fold_algorithm':"sha256('phase2.2-dev-fold-v1:' + group_representative), first8 unsigned big-endian modulo5; representative=min match ID of identical whole observable trajectory, otherwise self; validation=bucket fold_id",'folds':{str(fold):{'training_matches':len([m for m in pool if development_bucket(m,corpus.group_keys)!=fold]),'validation_matches':len([m for m in pool if development_bucket(m,corpus.group_keys)==fold]),'validation_samples':sum(n for m,n in pool.items() if development_bucket(m,corpus.group_keys)==fold)} for fold in range(FOLD_BUCKETS)},'previous_evaluation_cohorts':[{'kind':'Phase2 published test','matches':old['test'],'pristine':False},{'kind':'Phase2.1 published test','matches':roles['test'],'pristine':False},{'kind':'Phase2.1 original validation /all learning-curve and selected-model development','matches':roles['validation'],'pristine':False}],'fair_reference_rule':'Retrain E0 from random initialization under exactly the candidate train/development restrictions; never use saved v2 in-sample scores as held-out reference'}


def build_trajectory_groups(corpus):
    import numpy as np
    signatures={}
    for shard in corpus.shards:
        with np.load(corpus.root/shard['path']/'samples.npz',allow_pickle=False) as z:
            selected=np.isin(z['split'],[0,1]);obs=z['obs'][selected];mask=z['mask'][selected,2:36];seats=z['seat'][selected];matches=z['match_id'][selected]
        for match in np.unique(matches):
            rows=np.flatnonzero(matches==match)
            digest=hashlib.sha256(obs[rows].tobytes()+mask[rows].tobytes()+seats[rows].tobytes()).digest()
            signatures.setdefault(digest,[]).append(str(match))
    groups=[sorted(ids) for ids in signatures.values() if len(ids)>1]
    mapping={match:ids[0] for ids in groups for match in ids}
    return {'status':'PASS','method':'whole-observable-trajectory-v1','hash_fields':['obs','legal_discard_mask','seat'],'targets_used_for_grouping':False,'dataset_contract_sha256':corpus.contract_sha256,'groups':groups,'group_keys':mapping,'group_keys_sha256':canonical_hash(mapping),'filtered_samples':0}
