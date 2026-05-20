"""Generic preprocessing and feature-engineering pipeline."""

import pandas as pd


def _price_column(data: pd.DataFrame) -> str:
    for col in ("close", "value", "price"):
        if col in data.columns:
            return col
    raise ValueError("calculate_features requires one of: close, value, price")


def preprocess_data(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Clean market or indicator data before feature engineering."""
    if raw_data.empty:
        return raw_data.copy()
    data = raw_data.copy()
    if "date" in data.columns:
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data = data.dropna(subset=["date"]).sort_values("date")
    for col in ("open", "high", "low", "close", "value", "volume", "price"):
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    value_cols = [c for c in ("open", "high", "low", "close", "value", "price") if c in data.columns]
    if value_cols:
        data[value_cols] = data[value_cols].ffill().bfill()
    return data.reset_index(drop=True)


def calculate_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add baseline technical/statistical features to a cleaned dataframe."""
    features = preprocess_data(data)
    if features.empty:
        return features
    price_col = _price_column(features)
    price = features[price_col].astype(float)
    features["return_1"] = price.pct_change()
    features["sma5"] = price.rolling(5).mean()
    features["sma20"] = price.rolling(20).mean()
    features["volatility20"] = features["return_1"].rolling(20).std()
    return features

