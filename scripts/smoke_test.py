from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def main() -> None:
    run([sys.executable, "-m", "app.cli", "update-data"])
    run([sys.executable, "-m", "app.cli", "run-backtest"])
    print("smoke test OK")


if __name__ == "__main__":
    main()

