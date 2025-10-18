"""Premier League prediction utilities.

Modules:
- data: CSV loading and validation
- features: feature engineering
- model: model definitions
- pipeline: end-to-end training and prediction
"""

from .data import read_match_csv, find_odds_columns
from .features import build_features
from .model import build_model
from .pipeline import train_model, predict_matches

__all__ = [
	"read_match_csv",
	"find_odds_columns",
	"build_features",
	"build_model",
	"train_model",
	"predict_matches",
]
