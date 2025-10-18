from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd


def _implied_probs(odds: pd.DataFrame) -> pd.DataFrame:
	# Convert decimal odds to implied probability and renormalize to remove overround
	probs = 1.0 / odds.replace({0.0: np.nan})
	probs = probs.div(probs.sum(axis=1), axis=0)
	probs = probs.fillna(probs.mean())
	probs.columns = ["prob_H", "prob_D", "prob_A"]
	return probs


def build_features(
	df: pd.DataFrame,
	odds_cols: Tuple[str, str, str],
	*,
	target_col: str = "FTR",
) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
	"""
	Return features X and optional y.

	X columns:
	- prob_H, prob_D, prob_A from chosen odds
	- prob_diff_HA = prob_H - prob_A
	"""
	home_col, draw_col, away_col = odds_cols
	odds_df = df[[home_col, draw_col, away_col]].copy()
	odds_df.columns = ["odds_H", "odds_D", "odds_A"]

	probs = _implied_probs(odds_df)
	X = probs.copy()
	X["prob_diff_HA"] = X["prob_H"] - X["prob_A"]

	y: Optional[pd.Series] = None
	if target_col in df.columns:
		# Ensure labels are in {'H','D','A'}
		labels = df[target_col].astype(str).str.upper()
		mask = labels.isin({"H", "D", "A"})
		y = labels.where(mask)
		# Drop rows with unknown outcome if present
		valid = mask.values
		X = X.loc[valid].reset_index(drop=True)
		if y is not None:
			y = y.loc[valid].reset_index(drop=True)

	return X, y
