"""Small masked Behavior Cloning run; selection API receives train/validation only."""
import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from app.mlp import MahjongDiscardMLP, masked_cross_entropy, masked_log_probabilities
from training.metrics import classification_metrics
from training.phase2_dataset import PreparedSplit, prepare_split, validate_dataset
from training.reporting import write_json_report


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 2026
    learning_rate: float = .001
    weight_decay: float = .0001
    batch_size: int = 32
    max_epochs: int = 80
    patience: int = 10
    device: str = "auto"
    cpu_threads: int = 1


@dataclass
class EarlyStopping:
    patience: int
    best_loss: float = math.inf
    best_epoch: int = 0
    bad_epochs: int = 0

    def observe(self, epoch: int, validation_loss: float) -> bool:
        if not math.isfinite(validation_loss):
            raise ValueError("Validation loss must be finite")
        if validation_loss < self.best_loss:
            self.best_loss, self.best_epoch, self.bad_epochs = validation_loss, epoch, 0
            return True
        self.bad_epochs += 1
        return False

    @property
    def should_stop(self):
        return self.bad_epochs >= self.patience


@dataclass(frozen=True)
class TrainingRun:
    model: MahjongDiscardMLP
    best_state_dict: dict[str, torch.Tensor]
    history: list[dict]
    best_epoch: int
    epochs_executed: int
    best_validation_metrics: dict
    initial_weights_sha256: str
    best_weights_sha256: str
    optimizer_steps: int
    elapsed_seconds: float
    device: str
    device_probe: list[dict]
    stop_reason: str


def weights_sha256(state_dict) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(state_dict.items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def select_device(preference="auto"):
    if preference not in ("auto", "mps", "cuda", "cpu"):
        raise ValueError("Device must be auto, mps, cuda or cpu")
    candidates = ("mps", "cuda", "cpu") if preference == "auto" else (preference,)
    probes = []
    for candidate in candidates:
        available = candidate == "cpu" or candidate == "mps" and torch.backends.mps.is_available() or candidate == "cuda" and torch.cuda.is_available()
        if not available:
            probes.append({"device": candidate, "status": "UNAVAILABLE"})
            continue
        try:
            probe = MahjongDiscardMLP().to(candidate)
            features = torch.ones((2, 1368), dtype=torch.float32, device=candidate)
            masks = torch.zeros((2, 34), dtype=torch.bool, device=candidate)
            masks[:, :3] = True
            loss = masked_cross_entropy(probe(features), torch.tensor([0, 1], device=candidate), masks)
            loss.backward()
            probes.append({"device": candidate, "status": "PASS", "masked_loss": float(loss.detach().cpu())})
            return candidate, probes
        except RuntimeError as exc:
            probes.append({"device": candidate, "status": "FAIL", "reason": str(exc)})
    raise RuntimeError(f"No requested device passed real forward/backward operations: {probes}")


def predict_log_probabilities(model, split: PreparedSplit, device="cpu") -> np.ndarray:
    model.eval()
    with torch.inference_mode():
        features = torch.tensor(split.features, dtype=torch.float32, device=device)
        masks = torch.tensor(split.legal_masks, dtype=torch.bool, device=device)
        logs = masked_log_probabilities(model(features), masks)
    return logs.cpu().numpy().copy()


def train_model(training: PreparedSplit, validation: PreparedSplit, config: TrainConfig) -> TrainingRun:
    # Check names before accessing any labels, including a mistakenly passed test split.
    if training.name != "train" or validation.name != "validation":
        raise ValueError("Model selection accepts train and validation splits only")
    if set(training.match_ids) & set(validation.match_ids):
        raise ValueError("Train/validation match groups overlap")
    if config.max_epochs < 1 or config.patience < 1 or config.batch_size < 1 or config.cpu_threads < 1 or not 0 < config.learning_rate < 1 or config.weight_decay < 0:
        raise ValueError("Invalid training configuration")
    torch.set_num_threads(config.cpu_threads)
    device, probes = select_device(config.device)
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.use_deterministic_algorithms(device == "cpu")
    model = MahjongDiscardMLP().to(device)
    initial_hash = weights_sha256(model.state_dict())
    data = TensorDataset(torch.tensor(training.features), torch.tensor(training.targets, dtype=torch.long), torch.tensor(training.legal_masks, dtype=torch.bool))
    generator = torch.Generator().manual_seed(config.seed)
    loader = DataLoader(data, batch_size=config.batch_size, shuffle=True, generator=generator, num_workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    stop = EarlyStopping(config.patience)
    history, steps = [], 0
    best_state, best_metrics = None, None
    started = time.perf_counter()
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        total_loss = 0.
        for features, targets, masks in loader:
            features, targets, masks = features.to(device), targets.to(device), masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = masked_cross_entropy(model(features), targets, masks)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().cpu()) * len(targets)
            steps += 1
        train_metrics = classification_metrics(predict_log_probabilities(model, training, device), training.targets, training.legal_masks)
        validation_metrics = classification_metrics(predict_log_probabilities(model, validation, device), validation.targets, validation.legal_masks)
        history.append({"epoch": epoch, "train_loss": total_loss / len(training.targets), "train_eval_nll": train_metrics["nll"], "train_top1": train_metrics["top1"], "validation_loss": validation_metrics["nll"], "validation_top1": validation_metrics["top1"], "validation_top3": validation_metrics["top3"], "validation_macro_f1_34": validation_metrics["macro_f1_34"], "validation_macro_f1_supported": validation_metrics["macro_f1_supported"]})
        if stop.observe(epoch, validation_metrics["nll"]):
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_metrics = validation_metrics
        if stop.should_stop:
            break
    elapsed = time.perf_counter() - started
    model.load_state_dict(best_state, strict=True)
    model.eval()
    selected_hash = weights_sha256(best_state)
    if selected_hash == initial_hash:
        raise RuntimeError("Training did not update the selected weights")
    return TrainingRun(model, best_state, history, stop.best_epoch, len(history), best_metrics, initial_hash, selected_hash, steps, elapsed, device, probes, "validation_patience" if stop.should_stop else "max_epochs")


def main():
    from app.model_checkpoint import build_metadata, save_checkpoint
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/phase2"))
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/models/mahjong_discard_mlp.pt"))
    parser.add_argument("--device", choices=("auto", "mps", "cuda", "cpu"), default="auto")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=10)
    args = parser.parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    corpus = validate_dataset(args.root, args.report_dir / "data_validation.json")
    config = TrainConfig(seed=args.seed, max_epochs=args.max_epochs, patience=args.patience, device=args.device)
    write_json_report(args.report_dir / "training_history.json", {"status": "RUNNING", "config": asdict(config)})
    try:
        result = train_model(prepare_split(corpus, "train"), prepare_split(corpus, "validation"), config)
        summary = {"status": "PASS", "config": asdict(config), "device": result.device, "device_probe": result.device_probe, "epochs_executed": result.epochs_executed, "best_epoch": result.best_epoch, "stop_reason": result.stop_reason, "elapsed_seconds": result.elapsed_seconds, "optimizer_steps": result.optimizer_steps, "initial_weights_sha256": result.initial_weights_sha256, "best_weights_sha256": result.best_weights_sha256, "selection": "minimum validation masked NLL; no test split passed to train_model", "test_labels_used_for_selection": False, "history": result.history, "best_validation_metrics": result.best_validation_metrics, "environment": {"python": platform.python_version(), "torch": str(torch.__version__), "numpy": np.__version__, "os": platform.system(), "architecture": platform.machine()}, "reproducibility": "Deterministic CPU seeds/algorithms; MPS best effort, cross-device bit equality not claimed"}
        metadata = build_metadata(corpus.contract, corpus.report, summary)
        save_checkpoint(result.model, args.checkpoint, metadata)
        write_json_report(args.report_dir / "training_history.json", summary)
        print(json.dumps({k: summary[k] for k in ("status", "device", "epochs_executed", "best_epoch", "stop_reason", "elapsed_seconds")}, indent=2))
    except Exception as exc:
        write_json_report(args.report_dir / "training_history.json", {"status": "FAIL", "config": asdict(config), "reason": repr(exc)})
        raise


if __name__ == "__main__":
    main()
