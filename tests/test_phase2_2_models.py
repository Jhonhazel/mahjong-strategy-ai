import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from tests.test_phase2_1_training import expanded_root
from training.train_mlp import TrainConfig,weights_sha256


@pytest.mark.parametrize('widths,parameters',[((64,),89826),((128,),179618),((256,128),387746)])
def test_model_family_counts_forward_masked_probabilities_and_real_gradients(widths,parameters):
    from app.mlp import architecture_spec,parameter_count,MahjongDiscardMLP,masked_cross_entropy,masked_log_probabilities
    spec=architecture_spec(widths,.2);model=MahjongDiscardMLP(spec)
    assert parameter_count(spec)==sum(p.numel() for p in model.parameters())==parameters
    x=torch.rand(5,1368);y=torch.arange(5)%3;mask=torch.zeros((5,34),dtype=torch.bool);mask[:,:3]=True
    initial=weights_sha256(model.state_dict());optimizer=torch.optim.AdamW(model.parameters(),lr=.001)
    logits=model(x);assert logits.shape==(5,34) and torch.isfinite(logits).all()
    loss=masked_cross_entropy(logits,y,mask);loss.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    optimizer.step();assert weights_sha256(model.state_dict())!=initial
    probabilities=masked_log_probabilities(model(x),mask).exp()
    assert torch.all(probabilities[~mask]==0) and torch.allclose(probabilities.sum(1),torch.ones(5))
    model.eval();assert torch.equal(model(x),model(x))


@pytest.mark.parametrize('widths,dropout',[((2048,),.2),((128,64,32),.2),((0,),.2),((True,),.2),((128,),float('nan')),((128,),.9)])
def test_architecture_rejects_unsupported_or_unsafe_capacity(widths,dropout):
    from app.mlp import architecture_spec
    with pytest.raises(ValueError):architecture_spec(widths,dropout)


def test_existing_checkpoints_keep_exact_default_architecture_and_cpu_predictions():
    from app.mlp import MLP_SPEC,architecture_spec
    from app.model_checkpoint import load_checkpoint
    assert architecture_spec((64,),.2)==MLP_SPEC
    for name in ('mahjong_discard_mlp','mahjong_discard_mlp_v2'):
        model,metadata=load_checkpoint(Path('artifacts/models')/(name+'.pt'))
        assert metadata['architecture']==MLP_SPEC and model.architecture==MLP_SPEC
        assert weights_sha256(model.state_dict())==metadata['training']['best_weights_sha256']
        assert set(model.state_dict())=={'network.0.weight','network.0.bias','network.3.weight','network.3.bias'}


@pytest.mark.parametrize('widths',[(128,),(256,128)])
def test_larger_model_uses_existing_streamed_trainer_safe_checkpoint_and_resume(expanded_root,tmp_path,widths):
    from app.mlp import architecture_spec
    from app.model_checkpoint import load_checkpoint
    from training.expanded_training import ShardCorpus,nested_match_subset,train_sharded,save_run_checkpoint
    corpus=ShardCorpus(expanded_root);train=nested_match_subset(corpus.split('train'),80);val=corpus.split('validation')
    config=TrainConfig(max_epochs=3,patience=3,device='cpu',batch_size=16,seed=9);spec=architecture_spec(widths,.2)
    full=train_sharded(train,val,config,tmp_path/'full',model_spec=spec)
    train_sharded(train,val,config,tmp_path/'resume',model_spec=spec,stop_after_epoch=1)
    resumed=train_sharded(train,val,config,tmp_path/'resume',model_spec=spec,resume=True)
    assert full.summary['best_weights_sha256']==resumed.summary['best_weights_sha256']
    assert full.summary['history']==resumed.summary['history']
    assert full.summary['architecture_spec']==spec and full.summary['parameters']==sum(p.numel() for p in full.model.parameters())
    path=tmp_path/'variant.pt';saved=save_run_checkpoint(full,corpus,path)
    reloaded,metadata=load_checkpoint(path,expected_contract=corpus.contract)
    assert metadata['architecture']==spec and metadata['parameter_count']==full.summary['parameters']
    assert weights_sha256(reloaded.state_dict())==full.summary['best_weights_sha256']
    with pytest.raises(ValueError,match='identity'):
        train_sharded(train,val,config,tmp_path/'resume',model_spec=architecture_spec(widths,.3),resume=True)


def test_nonfinite_gradients_are_rejected_before_optimizer_update(expanded_root,tmp_path,monkeypatch):
    from app.mlp import MahjongDiscardMLP
    from training.expanded_training import ShardCorpus,nested_match_subset,train_sharded
    corpus=ShardCorpus(expanded_root)
    original=MahjongDiscardMLP.forward
    def poisoned(self,x):
        logits=original(self,x)
        logits.register_hook(lambda grad:torch.full_like(grad,float('nan')))
        return logits
    monkeypatch.setattr(MahjongDiscardMLP,'forward',poisoned)
    with pytest.raises(RuntimeError,match='gradient'):
        train_sharded(nested_match_subset(corpus.split('train'),80),corpus.split('validation'),TrainConfig(max_epochs=1,device='cpu'),tmp_path)
    assert not (tmp_path/'training_resume.sha256.json').exists()


def test_retained_resume_generations_are_bounded_without_losing_committed_pointer(tmp_path,monkeypatch):
    import training.expanded_training as module
    path=tmp_path/'training_resume.pt'
    for epoch in range(1,5):module.save_training_state(path,{'history':[{}]*epoch,'model':{'w':torch.tensor([float(epoch)])}},keep_generations=2)
    assert len(list(tmp_path.glob('training_resume.*.pt')))==2
    assert module.load_training_state(path)['model']['w'].item()==4
    real=module.write_json_report
    monkeypatch.setattr(module,'write_json_report',lambda *args:(_ for _ in ()).throw(OSError('pointer failure')))
    with pytest.raises(OSError):module.save_training_state(path,{'history':[{}]*5,'model':{'w':torch.tensor([5.])}},keep_generations=2)
    monkeypatch.setattr(module,'write_json_report',real)
    assert module.load_training_state(path)['model']['w'].item()==4
