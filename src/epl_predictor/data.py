from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd


COMMON_ODDS_SETS: List[Tuple[str, str, str]] = [
	("B365H", "B365D", "B365A"),  # Bet365
	("PSH", "PSD", "PSA"),        # Pinnacle closing odds (if available)
	("WHH", "WHD", "WHA"),        # William Hill
]


def read_match_csv(csv_path: str | Path) -> pd.DataFrame:
	csv_path = Path(csv_path)
	if not csv_path.exists():
		raise FileNotFoundError(f"CSV not found: {csv_path}")
	df = pd.read_csv(csv_path)
	return df


def find_odds_columns(df: pd.DataFrame) -> Optional[Tuple[str, str, str]]:
	for home_col, draw_col, away_col in COMMON_ODDS_SETS:
		if all(col in df.columns for col in (home_col, draw_col, away_col)):
			return home_col, draw_col, away_col
	return None


def ensure_training_columns(df: pd.DataFrame, target_col: str = "FTR") -> None:
	if target_col not in df.columns:
		raise ValueError(
			f"Target column '{target_col}' not found. Expected e.g. football-data.co.uk 'FTR'."
		)
	odds = find_odds_columns(df)
	if odds is None:
		raise ValueError(
			"No bookmaker odds columns found. Expected one of: "
			+ ", ".join("/".join(cols) for cols in COMMON_ODDS_SETS)
		)
