"""Install the supported unpatched release inside the active virtual environment."""
import subprocess
import sys


if __name__ == "__main__":
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Activate .venv or run its Python executable first")
    subprocess.run([sys.executable, "-m", "pip", "install", "PyMahjongGB==1.4.0"], check=True)
