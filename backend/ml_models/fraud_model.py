"""
XGBoost pipeline for detecting potentially fraudulent inpatient facility claims.

Highlights:
- Uses Kaggle dataset `leandrenash/enhanced-health-insurance-claims-dataset`
  (fetched via kagglehub).
- Performs lightweight feature engineering aimed at catching DRG upcoding and
  charge anomalies (e.g., charge-to-median-by-DRG ratios, payment-to-charge).
- Saves a compact artifact (model + feature metadata) for fast inference.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import joblib
import numpy as np
import pandas as pd
import kagglehub
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = BASE_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = ARTIFACT_DIR / "fraud_xgb.joblib"
METADATA_PATH = ARTIFACT_DIR / "fraud_xgb_meta.json"

# ---------- Feature configuration ----------

FeatureSpec = Dict[str, List[str]]

# Candidate column names per logical feature (dataset names vary).
FEATURE_CANDIDATES: FeatureSpec = {
    "claim_amount": [
        "claim_amount",
        "ClaimAmount",
        "TotalClaimChargeAmount",
        "total_claim_charge_amount",
        "InscClaimAmtReimbursed",
        "claim_total_amount",
    ],
    "paid_amount": [
        "paid_amount",
        "PaidAmount",
        "AmountPaid",
        "amount_paid",
        "DeductibleAmtPaid",
    ],
    "drg_code": [
        "drg_code",
        "DRGDefinition",
        "drg_definition",
        "DRG_CODE",
    ],
    "primary_diagnosis": [
        "primary_diagnosis",
        "PrimaryDiagnosis",
        "principal_diagnosis_code",
        "DiagnosisGroupCode",
        "DiagnosticRelatedGroup",
    ],
    "primary_procedure": [
        "primary_procedure",
        "PrincipalProcedureCode",
        "procedure_code",
        "procedure1",
        "ProcedureCode",
    ],
    "admission_type": ["AdmissionType", "admission_type", "admission_type_code"],
    "admission_source": [
        "AdmissionSource",
        "admission_source",
        "admission_source_code",
    ],
    "discharge_disposition": [
        "DischargeDisposition",
        "discharge_disposition",
        "discharge_status",
    ],
    "length_of_stay": ["length_of_stay", "LengthOfStay", "los"],
    "patient_age": ["patient_age", "Age", "age"],
    "gender": ["gender", "Gender", "Sex", "sex"],
    "num_diagnoses": [
        "num_diagnoses",
        "NumberOfDiagnosisCodes",
        "DiagnosisCodeCount",
        "diagnosis_count",
    ],
    "num_procedures": [
        "num_procedures",
        "NumberOfProcedureCodes",
        "ProcedureCodeCount",
        "procedure_count",
    ],
    "provider_state": ["provider_state", "ProviderState", "state"],
    "payer": ["payer", "Payer", "InsuranceCompany"],
}

CATEGORICAL_FEATURES = [
    "drg_code",
    "primary_diagnosis",
    "primary_procedure",
    "admission_type",
    "admission_source",
    "discharge_disposition",
    "gender",
    "provider_state",
    "payer",
]

TARGET_CANDIDATES = ["is_fraud", "fraud", "Fraud", "potential_fraud", "PotentialFraud"]

# ---------- Data classes ----------


@dataclass
class FraudModelBundle:
    """Serializable container for model + metadata."""

    pipeline: Pipeline
    feature_columns: List[str]
    categorical_cols: List[str]
    numeric_cols: List[str]
    drg_charge_medians: Dict[str, float]
    overall_charge_median: float
    training_metrics: Dict[str, float] = field(default_factory=dict)

    def predict_proba(self, records: Iterable[dict]) -> List[float]:
        df = build_feature_frame_from_records(
            records,
            self.drg_charge_medians,
            self.overall_charge_median,
        )
        # Ensure expected columns exist and order matches training
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = np.nan
        df = df[self.feature_columns]
        probs = self.pipeline.predict_proba(df)[:, 1]
        return [float(p) for p in probs]


# ---------- Helpers ----------


def _coalesce_column(df: pd.DataFrame, candidates: List[str], fill_value=np.nan) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series(fill_value, index=df.index)


def _cast_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _cast_string(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def _detect_target(df: pd.DataFrame) -> str:
    for candidate in TARGET_CANDIDATES:
        if candidate in df.columns:
            return candidate
    raise ValueError(
        "Could not find fraud target column. "
        f"Expected one of: {', '.join(TARGET_CANDIDATES)}"
    )


def _load_dataset() -> pd.DataFrame:
    dataset_path = Path(kagglehub.dataset_download("leandrenash/enhanced-health-insurance-claims-dataset"))
    csv_files = sorted(dataset_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("Dataset download succeeded but no CSV files were found.")
    # Heuristic: pick the largest CSV (typically the main claims table).
    csv_files.sort(key=lambda p: p.stat().st_size, reverse=True)
    df = pd.read_csv(csv_files[0])
    return df


def _derive_drg_medians(feature_df: pd.DataFrame) -> Tuple[Dict[str, float], float]:
    if "drg_code" not in feature_df.columns or "claim_amount" not in feature_df.columns:
        return {}, float(feature_df["claim_amount"].median() if "claim_amount" in feature_df else 1.0)
    medians = (
        feature_df.groupby("drg_code")["claim_amount"]
        .median()
        .dropna()
        .to_dict()
    )
    overall = float(feature_df["claim_amount"].median())
    return medians, overall


def _add_derived_features(
    df: pd.DataFrame,
    drg_medians: Dict[str, float],
    overall_median: float,
) -> pd.DataFrame:
    out = df.copy()
    out["payment_to_charge_ratio"] = _safe_divide(out.get("paid_amount"), out.get("claim_amount"))

    drg_ref = out.get("drg_code").map(drg_medians) if "drg_code" in out else pd.Series(np.nan, index=out.index)
    drg_ref = drg_ref.fillna(overall_median if overall_median else 1.0)
    out["drg_charge_ratio"] = _safe_divide(out.get("claim_amount"), drg_ref)

    # Binary flag for obvious upcoding (charge 25%+ above median for DRG)
    out["possible_drg_upcoding"] = (out["drg_charge_ratio"] > 1.25).astype(int)

    return out


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    # Preserve index to keep alignment with the DataFrame rows.
    base_index = None
    if numerator is not None:
        base_index = numerator.index
    elif denominator is not None:
        base_index = denominator.index
    num = numerator if numerator is not None else pd.Series(np.nan, index=base_index)
    denom = denominator if denominator is not None else pd.Series(np.nan, index=base_index)
    denom = denom.replace(0, np.nan)
    return num.astype(float) / denom.astype(float)


def build_feature_frame(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, float], float]:
    """Extracts standardized feature columns from the raw dataset."""
    features: Dict[str, pd.Series] = {}
    for logical_name, candidates in FEATURE_CANDIDATES.items():
        col = _coalesce_column(raw_df, candidates)
        if logical_name in CATEGORICAL_FEATURES:
            features[logical_name] = _cast_string(col)
        else:
            features[logical_name] = _cast_float(col)

    feature_df = pd.DataFrame(features)
    # Derived signals to highlight suspicious billing patterns
    drg_medians, overall_median = _derive_drg_medians(feature_df)
    feature_df = _add_derived_features(feature_df, drg_medians, overall_median)
    return feature_df, drg_medians, overall_median


def build_feature_frame_from_records(
    records: Iterable[dict],
    drg_medians: Dict[str, float],
    overall_median: float,
) -> pd.DataFrame:
    df = pd.DataFrame(list(records))
    # Ensure all expected logical columns exist before derivation
    for logical_name in FEATURE_CANDIDATES.keys():
        if logical_name not in df.columns:
            df[logical_name] = np.nan
    for logical_name in FEATURE_CANDIDATES.keys():
        if logical_name in CATEGORICAL_FEATURES:
            df[logical_name] = _cast_string(df[logical_name])
        else:
            df[logical_name] = _cast_float(df[logical_name])
    df = _add_derived_features(df, drg_medians, overall_median)
    return df


def _prepare_pipeline(feature_df: pd.DataFrame, target: pd.Series) -> FraudModelBundle:
    categorical_cols = [c for c in feature_df.columns if c in CATEGORICAL_FEATURES]
    numeric_cols = [c for c in feature_df.columns if c not in categorical_cols]

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", categorical_transformer, categorical_cols),
            ("numeric", numeric_transformer, numeric_cols),
        ]
    )

    # Handle imbalance: scale_pos_weight = (neg / pos)
    pos = float(target.sum())
    neg = float(len(target) - pos)
    scale_pos_weight = neg / pos if pos else 1.0

    model = XGBClassifier(
        n_estimators=220,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        min_child_weight=1,
        reg_lambda=1.0,
        n_jobs=4,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
    )

    clf = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])
    clf.fit(feature_df, target)
    return FraudModelBundle(
        pipeline=clf,
        feature_columns=list(feature_df.columns),
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
        drg_charge_medians={},  # filled by caller
        overall_charge_median=0.0,  # filled by caller
    )


def train_and_save(force_retrain: bool = False) -> FraudModelBundle:
    if MODEL_PATH.exists() and METADATA_PATH.exists() and not force_retrain:
        return joblib.load(MODEL_PATH)

    raw_df = _load_dataset()
    target_col = _detect_target(raw_df)
    target_raw = raw_df[target_col]
    target = target_raw.map({"Yes": 1, "No": 0}).fillna(target_raw).astype(int)

    feature_df, drg_medians, overall_median = build_feature_frame(raw_df)
    X_train, X_val, y_train, y_val = train_test_split(
        feature_df,
        target,
        test_size=0.2,
        random_state=42,
        stratify=target if target.nunique() > 1 else None,
    )

    bundle = _prepare_pipeline(X_train, y_train)
    bundle.drg_charge_medians = drg_medians
    bundle.overall_charge_median = overall_median

    y_val_pred = bundle.pipeline.predict(X_val)
    y_val_proba = bundle.pipeline.predict_proba(X_val)[:, 1]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, y_val_pred, average="binary", zero_division=0
    )
    bundle.training_metrics = {
        "f1": float(f1),
        "precision": float(precision),
        "recall": float(recall),
        "target_positive_rate": float(target.mean()),
    }

    joblib.dump(bundle, MODEL_PATH)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "feature_columns": bundle.feature_columns,
                "categorical_cols": bundle.categorical_cols,
                "numeric_cols": bundle.numeric_cols,
                "drg_charge_medians_size": len(bundle.drg_charge_medians),
                "overall_charge_median": bundle.overall_charge_median,
                "training_metrics": bundle.training_metrics,
            },
            f,
            indent=2,
        )
    return bundle


_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: FraudModelBundle | None = None


def get_fraud_model(force_retrain: bool = False) -> FraudModelBundle:
    """Load the model from disk or train if missing."""
    global _MODEL_CACHE
    with _MODEL_LOCK:
        if _MODEL_CACHE is not None and not force_retrain:
            return _MODEL_CACHE
        if MODEL_PATH.exists() and not force_retrain:
            _MODEL_CACHE = joblib.load(MODEL_PATH)
        else:
            _MODEL_CACHE = train_and_save(force_retrain=force_retrain)
        return _MODEL_CACHE


def model_feature_info() -> List[dict]:
    """Human-readable feature description for UI/API."""
    return [
        {"name": "claim_amount", "type": "number", "reason": "Total charges billed for the stay."},
        {"name": "paid_amount", "type": "number", "reason": "What was actually paid; large gaps can indicate padding."},
        {"name": "drg_code", "type": "categorical", "reason": "Signals expected severity; used for upcoding detection."},
        {"name": "primary_diagnosis", "type": "categorical", "reason": "Clinical context; mismatched with DRG can be suspicious."},
        {"name": "primary_procedure", "type": "categorical", "reason": "High-cost procedures paired with mild DRG may be fraud."},
        {"name": "admission_type", "type": "categorical", "reason": "Emergency vs elective patterns differ for fraud risk."},
        {"name": "admission_source", "type": "categorical", "reason": "Referral source helps spot unusual routing."},
        {"name": "discharge_disposition", "type": "categorical", "reason": "Early discharge after high billing can signal abuse."},
        {"name": "length_of_stay", "type": "number", "reason": "Too short or long stays relative to DRG raise flags."},
        {"name": "patient_age", "type": "number", "reason": "Age interacts with diagnosis/procedure severity."},
        {"name": "gender", "type": "categorical", "reason": "Minor but sometimes predictive for certain codes."},
        {"name": "num_diagnoses", "type": "number", "reason": "Large diagnosis lists with mild DRG can hint at upcoding."},
        {"name": "num_procedures", "type": "number", "reason": "High procedure volume for short stays can be suspicious."},
        {"name": "provider_state", "type": "categorical", "reason": "Regional practice patterns and risk baselines."},
        {"name": "payer", "type": "categorical", "reason": "Payer-specific rules can influence fraud likelihood."},
        {"name": "payment_to_charge_ratio", "type": "number", "reason": "Low ratios may indicate padded charges."},
        {"name": "drg_charge_ratio", "type": "number", "reason": "Charges relative to DRG median highlight upcoding."},
        {"name": "possible_drg_upcoding", "type": "number", "reason": "Binary flag when charges exceed DRG median by 25%."},
    ]

