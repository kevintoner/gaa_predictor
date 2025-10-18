#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure package import from repo root /src
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
	sys.path.insert(0, str(SRC_PATH))

from epl_predictor.pipeline import train_model  # noqa: E402


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Train EPL outcome model")
	parser.add_argument("--input", required=True, help="Path to training CSV")
	parser.add_argument(
		"--output",
		required=True,
		help="Path to write trained model (e.g., models/epl_baseline.joblib)",
	)
	parser.add_argument("--target", default="FTR", help="Target column (default: FTR)")
	parser.add_argument("--test-size", type=float, default=0.2)
	parser.add_argument("--random-state", type=int, default=42)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	res = train_model(
		input_csv=args.input,
		output_model_path=args.output,
		target_col=args.target,
		test_size=args.test_size,
		random_state=args.random_state,
	)
	print(
		json.dumps(
			{
				"model_path": str(res.model_path),
				"accuracy": res.accuracy,
				"log_loss": res.log_loss,
				"num_train_rows": res.num_train_rows,
				"num_test_rows": res.num_test_rows,
			},
			indent=2,
		)
	)


if __name__ == "__main__":
	main()
