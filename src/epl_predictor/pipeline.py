from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split

from .data import find_odds_columns, read_match_csv, ensure_training_columns
from .features import build_features
from .model import build_model


@dataclass
class TrainResult:
	model_path: Path
	accuracy: float
	log_loss: float
	num_train_rows: int
	num_test_rows: int


def train_model(
	input_csv: str | Path,
	output_model_path: str | Path,
	*,
	target_col: str = "FTR",
	test_size: float = 0.2,
	random_state: int = 42,
) -> TrainResult:
	df = read_match_csv(input_csv)
	ensure_training_columns(df, target_col=target_col)
	odds_cols = find_odds_columns(df)
	assert odds_cols is not None
	X, y = build_features(df, odds_cols, target_col=target_col)

	X_train, X_test, y_train, y_test = train_test_split(
		X, y, test_size=test_size, random_state=random_state, stratify=y
	)

	pipeline = build_model()
	pipeline.fit(X_train, y_train)

	y_pred = pipeline.predict(X_test)
	y_proba = pipeline.predict_proba(X_test)

	acc = float(accuracy_score(y_test, y_pred))
	ll = float(log_loss(y_test, y_proba, labels=["H", "D", "A"]))

	output_model_path = Path(output_model_path)
	output_model_path.parent.mkdir(parents=True, exist_ok=True)
	joblib.dump({"pipeline": pipeline, "odds_cols": odds_cols}, output_model_path)

	return TrainResult(
		model_path=output_model_path,
		accuracy=acc,
		log_loss=ll,
		num_train_rows=int(len(X_train)),
		num_test_rows=int(len(X_test)),
	)


def load_model(model_path: str | Path):
	obj = joblib.load(model_path)
	return obj["pipeline"], tuple(obj["odds_cols"])  # type: ignore[return-value]


def predict_matches(
	model_path: str | Path,
	input_csv: str | Path,
) -> pd.DataFrame:
	pipeline, odds_cols = load_model(model_path)
	df = read_match_csv(input_csv)
	if odds_cols is None:
		raise ValueError("Model file missing odds column metadata.")

	X, _ = build_features(df, odds_cols)
	proba = pipeline.predict_proba(X)
	pred_idx = np.argmax(proba, axis=1)
	idx_to_label = np.array(["H", "D", "A"])  # Assumes default class ordering
	pred = idx_to_label[pred_idx]

	result = pd.DataFrame(
		{
			"proba_H": proba[:, 0],
			"proba_D": proba[:, 1],
			"proba_A": proba[:, 2],
			"pred": pred,
		}
	)
	return result
