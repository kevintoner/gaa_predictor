#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure package import from repo root /src
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
	sys.path.insert(0, str(SRC_PATH))

import pandas as pd  # noqa: E402
from epl_predictor.pipeline import predict_matches  # noqa: E402


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Predict EPL outcomes for a dataset")
	parser.add_argument("--model", required=True, help="Path to trained model .joblib")
	parser.add_argument("--input", required=True, help="Path to CSV with odds features")
	parser.add_argument("--output", required=True, help="Where to save predictions CSV")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	pred_df = predict_matches(model_path=args.model, input_csv=args.input)
	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	pred_df.to_csv(output_path, index=False)
	print(f"Wrote predictions to {output_path}")


if __name__ == "__main__":
	main()
