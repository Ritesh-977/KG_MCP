"""Entry point: `python -m codegraph`."""

from __future__ import annotations

import sys

from codegraph.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
