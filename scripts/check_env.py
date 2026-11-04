"""Run with python -m scripts.check_env; writes evidence, not assumed success."""
import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def verify_environment() -> dict[str, object]:
    import numpy as np
    from MahjongGB import MahjongFanCalculator, MahjongShanten

    if not (3, 11) <= sys.version_info[:2] < (3, 13):
        raise RuntimeError("CPython 3.11 or 3.12 is required")
    hand = ("W1", "W1", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W9", "W9")
    shanten = MahjongShanten((), hand)
    fans = MahjongFanCalculator((), hand, "W5", 0, True, False, False, False, 0, 0, True)
    total = sum(points * count for points, count, *_ in fans)
    if shanten != 0 or total != 92:
        raise RuntimeError(f"Library smoke check failed: shanten={shanten}, fan={total}")
    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "architecture": platform.machine(), "virtual_environment": sys.prefix != sys.base_prefix,
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pytest", "PyMahjongGB")},
        "numpy_dtype": str(np.zeros((38, 4, 9), dtype=np.int8).dtype),
        "pymahjonggb_ok": True, "sample_shanten": shanten, "sample_nine_gates_fan": total,
        "windows_x64": "NOT RUN" if platform.system() != "Windows" else "current host",
        "macos_arm64": "current host" if platform.system() == "Darwin" and platform.machine() == "arm64" else "NOT RUN",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("datasets/environment_report.json"))
    args = parser.parse_args()
    report = verify_environment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
