"""
FR (Frequency Regulation) Revenue and Profit Prediction System using Machine Learning.

This module provides AI-powered predictions for:
- Future FR revenue and profit
- Activation patterns and earnings
- Market opportunity forecasting
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler


class FRPredictor:
    """AI-powered predictor for FR trading metrics."""

    def __init__(self, power_mw: float = 25.0):
        self.profit_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.revenue_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.activation_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=7,
            random_state=42
        )
        self.capacity_price_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.activation_price_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.power_mw = power_mw

    def prepare_features(self, daily_history: pd.DataFrame) -> pd.DataFrame:
        """Extract features from daily FR history for ML prediction."""
        if daily_history.empty:
            return pd.DataFrame()

        df = daily_history.copy()

        # Time-based features
        df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        df['day_of_month'] = pd.to_datetime(df['date']).dt.day
        df['month'] = pd.to_datetime(df['date']).dt.month
        df['quarter'] = pd.to_datetime(df['date']).dt.quarter
        df['week_of_year'] = pd.to_datetime(df['date']).dt.isocalendar().week
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Rolling statistics (7-day window) - using actual column names
        for col in ['total_revenue_eur', 'capacity_revenue_eur', 'activation_revenue_eur', 'activation_energy_mwh']:
            if col in df.columns:
                df[f'{col}_rolling_mean_7d'] = df[col].rolling(window=7, min_periods=1).mean()
                df[f'{col}_rolling_std_7d'] = df[col].rolling(window=7, min_periods=1).std().fillna(0)

        # Rolling statistics (30-day window)
        for col in ['total_revenue_eur', 'capacity_revenue_eur', 'activation_revenue_eur', 'activation_energy_mwh']:
            if col in df.columns:
                df[f'{col}_rolling_mean_30d'] = df[col].rolling(window=30, min_periods=1).mean()
                df[f'{col}_rolling_std_30d'] = df[col].rolling(window=30, min_periods=1).std().fillna(0)

        # Lag features
        for col in ['total_revenue_eur', 'capacity_revenue_eur', 'activation_revenue_eur', 'activation_energy_mwh']:
            if col in df.columns:
                df[f'{col}_lag_1'] = df[col].shift(1).fillna(0)
                df[f'{col}_lag_7'] = df[col].shift(7).fillna(0)

        return df

    def train(self, daily_history: pd.DataFrame) -> Dict[str, float]:
        """Train prediction models on historical FR data."""
        if daily_history.empty or len(daily_history) < 30:
            return {
                'status': 'error',
                'message': 'Insufficient data for training (need at least 30 days)',
                'profit_score': 0.0,
                'revenue_score': 0.0,
                'activation_score': 0.0
            }

        # Prepare features
        df = self.prepare_features(daily_history)

        # Define feature columns (exclude target and non-numeric)
        exclude_cols = {'date', 'total_revenue_eur', 'capacity_revenue_eur', 'activation_revenue_eur', 'activation_energy_mwh'}
        feature_cols = [col for col in df.columns if col not in exclude_cols and df[col].dtype in [np.float64, np.int64]]

        if not feature_cols:
            return {
                'status': 'error',
                'message': 'No valid features extracted',
                'profit_score': 0.0,
                'revenue_score': 0.0,
                'activation_score': 0.0
            }

        # Prepare training data (use 80% for training)
        train_size = int(len(df) * 0.8)
        train_df = df.iloc[:train_size]
        test_df = df.iloc[train_size:]

        X_train = train_df[feature_cols].fillna(0)
        X_test = test_df[feature_cols].fillna(0)

        # Scale features
        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train revenue model (total revenue)
        if 'total_revenue_eur' in df.columns:
            y_revenue_train = train_df['total_revenue_eur'].values
            y_revenue_test = test_df['total_revenue_eur'].values
            self.revenue_model.fit(X_train_scaled, y_revenue_train)
            revenue_score = self.revenue_model.score(X_test_scaled, y_revenue_test) if len(test_df) > 0 else 0.0
        else:
            revenue_score = 0.0

        # Train profit model (activation revenue)
        if 'activation_revenue_eur' in df.columns:
            y_profit_train = train_df['activation_revenue_eur'].values
            y_profit_test = test_df['activation_revenue_eur'].values
            self.profit_model.fit(X_train_scaled, y_profit_train)
            profit_score = self.profit_model.score(X_test_scaled, y_profit_test) if len(test_df) > 0 else 0.0
        else:
            profit_score = 0.0

        # Train capacity revenue model
        if 'capacity_revenue_eur' in df.columns:
            y_capacity_train = train_df['capacity_revenue_eur'].values
            y_capacity_test = test_df['capacity_revenue_eur'].values
            self.capacity_price_model.fit(X_train_scaled, y_capacity_train)
            capacity_score = self.capacity_price_model.score(X_test_scaled, y_capacity_test) if len(test_df) > 0 else 0.0
        else:
            capacity_score = 0.0

        self.is_trained = True
        self.feature_cols = feature_cols

        return {
            'status': 'success',
            'message': f'Models trained on {train_size} days, tested on {len(test_df)} days',
            'profit_score': max(0.0, profit_score),
            'revenue_score': max(0.0, revenue_score),
            'capacity_score': max(0.0, capacity_score),
            'train_samples': train_size,
            'test_samples': len(test_df)
        }

    def predict_next_period(
        self,
        daily_history: pd.DataFrame,
        forecast_days: int = 365
    ) -> tuple[pd.DataFrame, Dict[str, float]]:
        """Predict FR revenue, profit, and activations for next N days.

        Returns:
            Tuple of (predictions_df, metrics_dict)
        """

        if not self.is_trained:
            train_result = self.train(daily_history)
            if train_result['status'] == 'error':
                return pd.DataFrame(), {
                    'revenue_r2': 0.0,
                    'capacity_r2': 0.0,
                    'activation_r2': 0.0,
                    'training_samples': 0
                }

        # Prepare last known features
        df = self.prepare_features(daily_history)

        if df.empty:
            return pd.DataFrame(), {
                'revenue_r2': 0.0,
                'capacity_r2': 0.0,
                'activation_r2': 0.0,
                'training_samples': 0
            }

        # Get training metrics (re-train to get scores)
        train_result = self.train(daily_history)

        # Get last date and create future dates
        last_date = pd.to_datetime(df['date'].iloc[-1])
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=forecast_days)

        predictions = []

        # Use last known values as baseline
        last_row = df.iloc[-1:].copy()

        for future_date in future_dates:
            # Update time features
            pred_row = last_row.copy()
            pred_row['day_of_week'] = future_date.dayofweek
            pred_row['day_of_month'] = future_date.day
            pred_row['month'] = future_date.month
            pred_row['quarter'] = future_date.quarter
            pred_row['week_of_year'] = future_date.isocalendar().week
            pred_row['is_weekend'] = 1 if future_date.dayofweek in [5, 6] else 0

            # Extract features
            X_pred = pred_row[self.feature_cols].fillna(0)
            X_pred_scaled = self.scaler.transform(X_pred)

            # Make predictions
            total_revenue_pred = max(0, float(self.revenue_model.predict(X_pred_scaled)[0]))
            activation_revenue_pred = max(0, float(self.profit_model.predict(X_pred_scaled)[0]))

            # Capacity revenue is total - activation
            capacity_revenue_pred = max(0, total_revenue_pred - activation_revenue_pred)

            # Activation energy estimate: assume ~2 hours activation per day at battery power
            activation_energy_pred = self.power_mw * 2.0

            predictions.append({
                'date': future_date,
                'predicted_total_revenue_eur': total_revenue_pred,
                'predicted_capacity_revenue_eur': capacity_revenue_pred,
                'predicted_activation_revenue_eur': activation_revenue_pred,
                'predicted_activation_energy_mwh': activation_energy_pred,
            })

            # Update last_row with predictions for next iteration
            if 'total_revenue_eur' in last_row.columns:
                last_row['total_revenue_eur'] = total_revenue_pred
            if 'capacity_revenue_eur' in last_row.columns:
                last_row['capacity_revenue_eur'] = capacity_revenue_pred
            if 'activation_revenue_eur' in last_row.columns:
                last_row['activation_revenue_eur'] = activation_revenue_pred
            if 'activation_energy_mwh' in last_row.columns:
                last_row['activation_energy_mwh'] = activation_energy_pred

        pred_df = pd.DataFrame(predictions)

        # Return metrics
        metrics = {
            'revenue_r2': train_result.get('revenue_score', 0.0),
            'capacity_r2': train_result.get('capacity_score', 0.0),
            'activation_r2': train_result.get('profit_score', 0.0),
            'training_samples': train_result.get('train_samples', len(daily_history))
        }

        return pred_df, metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from trained models."""
        if not self.is_trained:
            return pd.DataFrame()

        importance_data = []

        for name, model in [
            ('Revenue', self.revenue_model),
            ('Activation Revenue', self.profit_model),
            ('Activation Hours', self.activation_model)
        ]:
            if hasattr(model, 'feature_importances_'):
                for feature, importance in zip(self.feature_cols, model.feature_importances_):
                    importance_data.append({
                        'model': name,
                        'feature': feature,
                        'importance': importance
                    })

        return pd.DataFrame(importance_data)


def create_fr_prediction_summary(predictions_df: pd.DataFrame, battery_power_mw: float = 25.0) -> Dict[str, float]:
    """Create summary statistics from FR predictions DataFrame.

    Args:
        predictions_df: DataFrame with predicted FR metrics
        battery_power_mw: Battery power capacity in MW

    Returns:
        Dictionary with summary statistics
    """
    if predictions_df.empty:
        return {
            'total_revenue_eur': 0.0,
            'total_capacity_revenue_eur': 0.0,
            'total_activation_revenue_eur': 0.0,
            'total_activation_energy_mwh': 0.0,
            'avg_daily_revenue_eur': 0.0,
            'avg_daily_capacity_eur': 0.0,
            'avg_daily_activation_eur': 0.0,
            'avg_daily_energy_mwh': 0.0,
            'battery_power_mw': battery_power_mw,
            'forecast_days': 0,
        }

    total_revenue = predictions_df['predicted_total_revenue_eur'].sum()
    total_capacity = predictions_df['predicted_capacity_revenue_eur'].sum()
    total_activation = predictions_df['predicted_activation_revenue_eur'].sum()
    total_energy = predictions_df['predicted_activation_energy_mwh'].sum()

    forecast_days = len(predictions_df)

    return {
        'total_revenue_eur': total_revenue,
        'total_capacity_revenue_eur': total_capacity,
        'total_activation_revenue_eur': total_activation,
        'total_activation_energy_mwh': total_energy,
        'avg_daily_revenue_eur': total_revenue / forecast_days if forecast_days > 0 else 0.0,
        'avg_daily_capacity_eur': total_capacity / forecast_days if forecast_days > 0 else 0.0,
        'avg_daily_activation_eur': total_activation / forecast_days if forecast_days > 0 else 0.0,
        'avg_daily_energy_mwh': total_energy / forecast_days if forecast_days > 0 else 0.0,
        'battery_power_mw': battery_power_mw,
        'forecast_days': forecast_days,
    }
