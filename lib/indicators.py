"""
Pure technical-indicator math. No I/O, no API calls, no LLM — just numbers in,
numbers out. Every figure shown in the UI is produced here in plain Python so
the model can never invent or alter a value.

All functions take an OHLC pandas DataFrame with columns:
    timestamp, open, high, low, close
"""

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float:
    """Relative Strength Index (Wilder's smoothing). Returns the latest value."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing == EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi_series = 100 - (100 / (1 + rs))
    value = rsi_series.iloc[-1]
    # If loss was zero (pure uptrend) RSI is 100.
    return float(value) if pd.notna(value) else 100.0


def moving_averages(close: pd.Series, fast: int = 10, slow: int = 30):
    """Fast/slow simple moving averages (latest values)."""
    ma_fast = close.rolling(fast).mean().iloc[-1]
    ma_slow = close.rolling(slow).mean().iloc[-1]
    return float(ma_fast), float(ma_slow)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD line, signal line, and histogram (latest values)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])


def atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range — a volatility measure used to size stops/targets."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_series = true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    value = atr_series.iloc[-1]
    if pd.isna(value):
        # Fallback for short series: simple mean of available true ranges.
        value = true_range.mean()
    return float(value)
