"""Publish courtlistener.duckdb to Hugging Face (card text in card.yaml; logic in datapond-build).

    uv run python publish_to_hf.py --token hf_xxx [--card-only] [--verify]
"""
import sys

from datapond_build.publish import main

if __name__ == "__main__":
    sys.exit(main(["--db", "courtlistener.duckdb"] + sys.argv[1:]))
