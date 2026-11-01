"""Repo paths and fixed constants. ASCII source; Korean text lives in config/*.json."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CONFIG = ROOT / "config"
MANIFESTS = ROOT / "manifests"
RESULTS = ROOT / "results"
GATE = ROOT / "runs" / "gate"
GATE_INPUTS = GATE / "inputs"
GATE_ANSWERS = GATE / "answers"
GATE_KEY = GATE / "key.csv"

SAV_2025 = RAW / "a2025.sav"
SAV_2024 = RAW / "a2024.sav"
SAV_2023 = RAW / "a2023.sav"

SPLIT_META = MANIFESTS / "splits_seed42.meta.json"

SEED = 42
WEIGHT = "psfwt"
TARGETS = ("ever", "weekly", "carb")
ANSWER_COL = {"ever": "p_zero_ever", "weekly": "p_zero_weekly", "carb": "p_carb_top1"}
AGE = "SQ2_range"
SEX = "SQ1"
REGION = "\uc9c0\uc5ed"  # sido label column
HOUSEHOLD = "H_ID"
PSU = "vuid"
STRATUM = "STR"
SPLIT_FRACTIONS = {"train": 0.50, "calibration": 0.10, "test": 0.40}
