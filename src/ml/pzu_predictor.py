"""
PZU Revenue and Profit Prediction System using Machine Learning.

This module provides AI-powered predictions for:
- Future revenue and profit
- Transaction patterns
- Optimal trading opportunities
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler


class PZUPredictor:
    """AI-powered predictor for PZU trading metrics."""

    def __init__(self, capacity_mwh: float = 50.0, power_mw: float = 25.0):
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
        self.transaction_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=7,
            random_state=42
        )
        self.buy_price_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.sell_price_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.capacity_mwh = capacity_mwh
        self.power_mw = power_mw

    def prepare_features(self, daily_history: pd.DataFrame) -> pd.DataFrame:
        """Extract features from daily history for ML prediction."""
        if daily_history.empty:
            return pd.DataFrame()

        df = daily_history.copy()

        # Time-based features
        df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        df['day_of_month'] = pd.to_datetime(df['date']).dt.day
        df['month'] = pd.to_datetime(df['date']).dt.month
        df['quarter'] = pd.to_datetime(df['date']).dt.quarter
        df['week_of_year'] = pd.to_datetime(df['date']).dt.isocalendar().week

        # Rolling statistics (7-day window)
        for col in ['daily_profit_eur', 'daily_revenue_eur', 'daily_cost_eur']:
            if col in df.columns:
                df[f'{col}_rolling_mean_7d'] = df[col].rolling(window=7, min_periods=1).mean()
                df[f'{col}_rolling_std_7d'] = df[col].rolling(window=7, min_periods=1).std().fillna(0)

        # Rolling statistics (30-day window)
        for col in ['daily_profit_eur', 'daily_revenue_eur', 'daily_cost_eur']:
            if col in df.columns:
                df[f'{col}_rolling_mean_30d'] = df[col].rolling(window=30, min_periods=1).mean()
                df[f'{col}_rolling_std_30d'] = df[col].rolling(window=30, min_periods=1).std().fillna(0)

        # Lag features
        for col in ['daily_profit_eur', 'daily_revenue_eur', 'daily_cost_eur']:
            if col in df.columns:
                df[f'{col}_lag_1'] = df[col].shift(1).fillna(0)
                df[f'{col}_lag_7'] = df[col].shift(7).fillna(0)

        # Energy features
        if 'charge_energy_mwh' in df.columns and 'discharge_energy_mwh' in df.columns:
            df['energy_efficiency'] = df['discharge_energy_mwh'] / (df['charge_energy_mwh'] + 1e-6)
            df['total_energy_mwh'] = df['charge_energy_mwh'] + df['discharge_energy_mwh']

        return df

    def train(self, daily_history: pd.DataFrame) -> Dict[str, float]:
        """Train prediction models on historical data."""
        if daily_history.empty or len(daily_history) < 30:
            return {
                'status': 'error',
                'message': 'Insufficient data for training (need at least 30 days)',
                'profit_score': 0.0,
                'revenue_score': 0.0,
                'transaction_score': 0.0
            }

        # Prepare features
        df = self.prepare_features(daily_history)

        # Define feature columns (exclude target and non-numeric)
        exclude_cols = {'date', 'daily_profit_eur', 'daily_revenue_eur', 'daily_cost_eur'}
        feature_cols = [col for col in df.columns if col not in exclude_cols and df[col].dtype in [np.float64, np.int64]]

        if not feature_cols:
            return {
                'status': 'error',
                'message': 'No valid features extracted',
                'profit_score': 0.0,
                'revenue_score': 0.0,
                'transaction_score': 0.0
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

        # Train profit model
        y_profit_train = train_df['daily_profit_eur'].values
        y_profit_test = test_df['daily_profit_eur'].values
        self.profit_model.fit(X_train_scaled, y_profit_train)
        profit_score = self.profit_model.score(X_test_scaled, y_profit_test) if len(test_df) > 0 else 0.0

        # Train revenue model
        if 'daily_revenue_eur' in df.columns:
            y_revenue_train = train_df['daily_revenue_eur'].values
            y_revenue_test = test_df['daily_revenue_eur'].values
            self.revenue_model.fit(X_train_scaled, y_revenue_train)
            revenue_score = self.revenue_model.score(X_test_scaled, y_revenue_test) if len(test_df) > 0 else 0.0
        else:
            revenue_score = 0.0

        # Train transaction model (predict number of profitable transactions)
        if 'charge_energy_mwh' in df.columns:
            y_transaction_train = train_df['charge_energy_mwh'].values
            y_transaction_test = test_df['charge_energy_mwh'].values
            self.transaction_model.fit(X_train_scaled, y_transaction_train)
            transaction_score = self.transaction_model.score(X_test_scaled, y_transaction_test) if len(test_df) > 0 else 0.0
        else:
            transaction_score = 0.0

        # Train buy price model
        buy_price_score = 0.0
        if 'daily_cost_eur' in df.columns and 'charge_energy_mwh' in df.columns:
            # Calculate avg buy price from cost and energy
            train_df['avg_buy_price'] = train_df['daily_cost_eur'] / (train_df['charge_energy_mwh'] + 1e-6)
            test_df['avg_buy_price'] = test_df['daily_cost_eur'] / (test_df['charge_energy_mwh'] + 1e-6)

            y_buy_train = train_df['avg_buy_price'].fillna(0).values
            y_buy_test = test_df['avg_buy_price'].fillna(0).values
            self.buy_price_model.fit(X_train_scaled, y_buy_train)
            buy_price_score = self.buy_price_model.score(X_test_scaled, y_buy_test) if len(test_df) > 0 else 0.0

        # Train sell price model
        sell_price_score = 0.0
        if 'daily_revenue_eur' in df.columns and 'discharge_energy_mwh' in df.columns:
            # Calculate avg sell price from revenue and energy
            train_df['avg_sell_price'] = train_df['daily_revenue_eur'] / (train_df['discharge_energy_mwh'] + 1e-6)
            test_df['avg_sell_price'] = test_df['daily_revenue_eur'] / (test_df['discharge_energy_mwh'] + 1e-6)

            y_sell_train = train_df['avg_sell_price'].fillna(0).values
            y_sell_test = test_df['avg_sell_price'].fillna(0).values
            self.sell_price_model.fit(X_train_scaled, y_sell_train)
            sell_price_score = self.sell_price_model.score(X_test_scaled, y_sell_test) if len(test_df) > 0 else 0.0

        self.is_trained = True
        self.feature_cols = feature_cols

        return {
            'status': 'success',
            'message': f'Models trained on {train_size} days, tested on {len(test_df)} days',
            'profit_score': max(0.0, profit_score),
            'revenue_score': max(0.0, revenue_score),
            'transaction_score': max(0.0, transaction_score),
            'buy_price_score': max(0.0, buy_price_score),
            'sell_price_score': max(0.0, sell_price_score),
            'train_samples': train_size,
            'test_samples': len(test_df)
        }

    def predict_next_period(
        self,
        daily_history: pd.DataFrame,
        forecast_days: int = 30
    ) -> Dict[str, object]:
        """Predict revenue, profit, and transactions for next N days."""

        if not self.is_trained:
            train_result = self.train(daily_history)
            if train_result['status'] == 'error':
                return {
                    'status': 'error',
                    'message': train_result['message'],
                    'predictions': pd.DataFrame()
                }

        # Prepare last known features
        df = self.prepare_features(daily_history)

        if df.empty:
            return {
                'status': 'error',
                'message': 'No features available for prediction',
                'predictions': pd.DataFrame()
            }

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

            # Extract features
            X_pred = pred_row[self.feature_cols].fillna(0)
            X_pred_scaled = self.scaler.transform(X_pred)

            # Make predictions
            profit_pred = float(self.profit_model.predict(X_pred_scaled)[0])
            revenue_pred = float(self.revenue_model.predict(X_pred_scaled)[0])
            transaction_pred = float(self.transaction_model.predict(X_pred_scaled)[0])
            buy_price_pred = float(self.buy_price_model.predict(X_pred_scaled)[0])
            sell_price_pred = float(self.sell_price_model.predict(X_pred_scaled)[0])

            # Apply battery power constraints
            # Constrain energy to battery capacity and power limits
            max_energy_per_cycle = min(self.capacity_mwh, self.power_mw * 2)  # 2 hours charge/discharge
            constrained_energy = min(max(0, transaction_pred), max_energy_per_cycle)

            # Calculate spread
            spread_pred = sell_price_pred - buy_price_pred

            # Recalculate profit and revenue based on constrained energy
            cost_pred = constrained_energy * buy_price_pred
            constrained_revenue = constrained_energy * 0.9 * sell_price_pred  # Apply efficiency
            constrained_profit = constrained_revenue - cost_pred

            predictions.append({
                'date': future_date,
                'predicted_profit_eur': constrained_profit,
                'predicted_revenue_eur': constrained_revenue,
                'predicted_energy_mwh': constrained_energy,
                'predicted_buy_price_eur_mwh': buy_price_pred,
                'predicted_sell_price_eur_mwh': sell_price_pred,
                'predicted_spread_eur_mwh': spread_pred,
                'confidence': 'high' if len(daily_history) > 90 else 'medium' if len(daily_history) > 30 else 'low'
            })

            # Update last_row with predictions for next iteration
            last_row['daily_profit_eur'] = constrained_profit
            last_row['daily_revenue_eur'] = constrained_revenue
            last_row['charge_energy_mwh'] = constrained_energy

        pred_df = pd.DataFrame(predictions)

        # Calculate summary statistics
        total_profit = pred_df['predicted_profit_eur'].sum()
        total_revenue = pred_df['predicted_revenue_eur'].sum()
        total_energy = pred_df['predicted_energy_mwh'].sum()
        avg_daily_profit = pred_df['predicted_profit_eur'].mean()
        avg_buy_price = pred_df['predicted_buy_price_eur_mwh'].mean()
        avg_sell_price = pred_df['predicted_sell_price_eur_mwh'].mean()
        avg_spread = pred_df['predicted_spread_eur_mwh'].mean()

        return {
            'status': 'success',
            'message': f'Predicted {forecast_days} days ahead (Battery: {self.capacity_mwh} MWh / {self.power_mw} MW)',
            'predictions': pred_df,
            'summary': {
                'total_predicted_profit_eur': total_profit,
                'total_predicted_revenue_eur': total_revenue,
                'total_predicted_energy_mwh': total_energy,
                'avg_daily_profit_eur': avg_daily_profit,
                'avg_buy_price_eur_mwh': avg_buy_price,
                'avg_sell_price_eur_mwh': avg_sell_price,
                'avg_spread_eur_mwh': avg_spread,
                'battery_capacity_mwh': self.capacity_mwh,
                'battery_power_mw': self.power_mw,
                'forecast_days': forecast_days,
                'confidence_level': pred_df['confidence'].iloc[0] if not pred_df.empty else 'low'
            }
        }

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from trained models."""
        if not self.is_trained:
            return pd.DataFrame()

        importance_data = []

        for name, model in [
            ('Profit', self.profit_model),
            ('Revenue', self.revenue_model),
            ('Transaction', self.transaction_model)
        ]:
            if hasattr(model, 'feature_importances_'):
                for feature, importance in zip(self.feature_cols, model.feature_importances_):
                    importance_data.append({
                        'model': name,
                        'feature': feature,
                        'importance': importance
                    })

        return pd.DataFrame(importance_data)


def create_prediction_summary(
    predictor: PZUPredictor,
    daily_history: pd.DataFrame,
    forecast_days: int = 30
) -> Dict[str, object]:
    """Create a complete prediction summary with training and forecasting."""

    # Train the model
    training_result = predictor.train(daily_history)

    if training_result['status'] == 'error':
        return {
            'status': 'error',
            'message': training_result['message'],
            'training': training_result,
            'forecast': None
        }

    # Generate predictions
    forecast_result = predictor.predict_next_period(daily_history, forecast_days)

    return {
        'status': 'success',
        'message': 'Prediction complete',
        'training': training_result,
        'forecast': forecast_result
    }
