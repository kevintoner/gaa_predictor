# Premier League Predictor

A starter project for building a machine learning model to predict English Premier League match results.

## Project layout

```
~/premier-league-predictor
├── data
│   ├── raw/          # Put raw CSVs here (e.g., football-data.co.uk season files)
│   └── processed/    # Generated features/cleaned datasets
├── models/           # Saved trained models (e.g., .joblib)
├── notebooks/        # Exploratory analysis
├── scripts/          # CLI scripts for training and inference
├── src/
│   └── epl_predictor # Python package
└── tests/            # Tests
```

## Quickstart

1) Create a virtual environment and install dependencies

```bash
cd ~/premier-league-predictor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

2) Add raw data

- Download season CSVs from `https://www.football-data.co.uk/englandm.php` and place them under `data/raw/`.
- The starter pipeline expects bookmaking odds columns if available: `B365H`, `B365D`, `B365A`.

3) Train a baseline model

```bash
python scripts/train.py --input data/raw/E0_2023_2024.csv --output models/epl_baseline.joblib
```

4) Run predictions on a dataset

```bash
python scripts/predict.py --model models/epl_baseline.joblib --input data/raw/E0_2024_2025.csv --output predictions.csv
```

## Notes

- This is a minimal baseline using scikit-learn. Improve by engineering richer team form features, player availability, and market signals.
- For automated data, consider APIs like `https://www.football-data.org/` (API key required). A thin ingestion layer can be added to `src/epl_predictor/data.py`.

## License

MIT (add a `LICENSE` file if needed).
