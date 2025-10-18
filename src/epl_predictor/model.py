from __future__ import annotations

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_model() -> Pipeline:
	"""Return a basic classifier pipeline for 3-way match outcome (H/D/A)."""
	return Pipeline(
		steps=[
			("imputer", SimpleImputer(strategy="median")),
			("scaler", StandardScaler()),
			(
				"clf",
				LogisticRegression(
					multi_class="multinomial",
					max_iter=1000,
					n_jobs=None,
				),
			),
		]
	)
