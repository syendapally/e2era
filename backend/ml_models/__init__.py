"""
ML models package.

Currently contains an XGBoost pipeline for detecting potentially fraudulent
inpatient facility claims. The code is intentionally lightweight and readable
so it is easy to adapt when new claim signals become available.
"""

from ml_models.fraud_model import get_fraud_model  # noqa: F401

