"""Pinned public corpus acquisition with bounded retry and safe extraction."""
import argparse
from dataclasses import dataclass
import gzip
import hashlib
import http.client
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import random
import shutil
import tarfile
import time
import urllib.error
import urllib.request

from app.domain.exceptions import CorruptedDatasetError, DatasetDownloadError

DATASET_REVISION = "c8435106623c106b9e03b980691bea24ba4ac240"
DATASET_ID = "Dannibal/ijcai-mahjong-round2"
MAX_EXTRACTED_BYTES = 10 * 1024**3
MAX_MEMBERS = 100000


@dataclass(frozen=True)
class DatasetSpec:
    filename: str
    expected_size: int
    expected_sha256: str

    @property
    def url(self):
        return f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{DATASET_REVISION}/{self.filename}"


DECISIONS_SPEC = DatasetSpec("finalist_decisions.tar.gz", 40599733, "7ff94612e28c2786bfc1bbfcda39a6745b5087061728d6be6bc39b43c6ee1c11")
GAMES_SPEC = DatasetSpec("finalist_games.tar.gz", 165209428, "68fe9a5613e523d65356ac5f3e3bc997be8a3ad08bc24035ae22aad17c1daa42")
FEATURE_SOURCE_REVISION = "6964d80b9f8a6670dda44f14b664c61112f61009"
FEATURE_SOURCE_URL = f"https://huggingface.co/Dannibal/ijcai-mahjong-ckpts-2026/resolve/{FEATURE_SOURCE_REVISION}/champion/feature.py"
FEATURE_SOURCE_SHA256 = "bad9976fd01b7f595cc6d840d7df91fb61993cf59a8f6131053ac921d58112b6"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path, expected_size, expected_sha256):
    if expected_size is not None and path.stat().st_size != expected_size:
        raise CorruptedDatasetError(f"Size mismatch for {path.name}")
    if expected_sha256 is not None and file_sha256(path) != expected_sha256:
        raise CorruptedDatasetError(f"SHA-256 mismatch for {path.name}")


def download_with_retry(url, dest_path, expected_size=None, expected_sha256=None, max_retries=4, base_backoff_sec=1.0, timeout_sec=30.0) -> Path:
    if max_retries < 1 or base_backoff_sec < 0 or timeout_sec <= 0:
        raise ValueError("Invalid retry/timeout parameters")
    dest = Path(dest_path)
    if dest.is_file() and (expected_size is not None or expected_sha256 is not None):
        try:
            _verify(dest, expected_size, expected_sha256)
            return dest
        except CorruptedDatasetError:
            pass  # Explicitly replace only this invalid dataset cache after successful download.
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    errors = []
    for attempt in range(max_retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MahjongStrategyAI/phase1"})
            with urllib.request.urlopen(request, timeout=timeout_sec) as response, partial.open("wb") as output:
                length = response.headers.get("Content-Length")
                received = 0
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    received += len(chunk)
                if length is not None and received != int(length):
                    raise http.client.IncompleteRead(b"", int(length) - received)
            _verify(partial, expected_size, expected_sha256)
            partial.replace(dest)
            return dest
        except CorruptedDatasetError:
            partial.unlink(missing_ok=True)
            raise
        except urllib.error.HTTPError as exc:
            errors.append(f"HTTP {exc.code}")
            if exc.code != 429 and not 500 <= exc.code < 600:
                partial.unlink(missing_ok=True)
                raise DatasetDownloadError(f"Non-retryable download failure: {errors[-1]}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        partial.unlink(missing_ok=True)
        if attempt + 1 < max_retries:
            delay = base_backoff_sec * 2**attempt
            time.sleep(delay + random.uniform(0, delay * 0.1))
    raise DatasetDownloadError(f"Download failed after {max_retries} attempts: {'; '.join(errors)}")


def validate_safe_tar_member_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or PureWindowsPath(name).drive:
        raise CorruptedDatasetError(f"Unsafe archive path: {name!r}")
    return path


def safe_extract_tar_gz(tar_gz_path, dest_dir) -> list[Path]:
    source, destination = Path(tar_gz_path), Path(dest_dir)
    try:
        # Consume the gzip trailer before creating output files (CRC / truncation).
        with gzip.open(source, "rb") as stream:
            total = 0
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_EXTRACTED_BYTES:
                    raise CorruptedDatasetError("Archive exceeds extraction size limit")
        with tarfile.open(source, "r:gz") as tar:
            members = tar.getmembers()
            if not members or len(members) > MAX_MEMBERS:
                raise CorruptedDatasetError("Invalid archive member count")
            targets, names = [], set()
            base = destination.resolve()
            for member in members:
                path = validate_safe_tar_member_name(member.name)
                target = destination.joinpath(*path.parts)
                if not target.resolve().is_relative_to(base) or not (member.isfile() or member.isdir()):
                    raise CorruptedDatasetError(f"Unsafe member type/path: {member.name}")
                if member.name in names:
                    raise CorruptedDatasetError(f"Duplicate archive member: {member.name}")
                names.add(member.name)
                targets.append((member, target))
            extracted = []
            for member, target in targets:
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                extracted.append(target)
            return extracted
    except CorruptedDatasetError:
        raise
    except (tarfile.TarError, EOFError, OSError, ValueError) as exc:
        raise CorruptedDatasetError(f"Invalid gzip/tar archive {source.name}: {exc}") from exc


def ensure_ijcai_dataset(datasets_root: Path) -> dict[str, Path]:
    root = Path(datasets_root)
    paths = {}
    for key, spec in [("decisions_tar", DECISIONS_SPEC), ("games_tar", GAMES_SPEC)]:
        paths[key] = download_with_retry(spec.url, root / spec.filename, spec.expected_size, spec.expected_sha256)
    # Re-extraction repairs incomplete directories; never rely on a magic file count.
    safe_extract_tar_gz(paths["decisions_tar"], root)
    paths["decisions_dir"] = root / "finalist_decisions"
    archives = []
    for spec in (DECISIONS_SPEC, GAMES_SPEC):
        with tarfile.open(root / spec.filename, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                validate_safe_tar_member_name(member.name)
            files = [m for m in members if m.isfile()]
            archives.append({"filename": spec.filename, "size": spec.expected_size, "sha256": spec.expected_sha256, "url": spec.url, "regular_file_count": len(files), "uncompressed_file_bytes": sum(m.size for m in files)})
    download_with_retry(FEATURE_SOURCE_URL, root / "references/feature.py", 15510, FEATURE_SOURCE_SHA256)
    metadata = {"dataset_id": DATASET_ID, "revision": DATASET_REVISION, "archives": archives, "feature_reference": {"url": FEATURE_SOURCE_URL, "revision": FEATURE_SOURCE_REVISION, "sha256": FEATURE_SOURCE_SHA256, "license": "MIT"}}
    (root / "acquisition_report.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets"))
    args = parser.parse_args()
    print({key: str(path) for key, path in ensure_ijcai_dataset(args.root).items()})


if __name__ == "__main__":
    main()
