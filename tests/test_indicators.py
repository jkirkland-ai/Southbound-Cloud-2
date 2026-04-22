import numpy as np
import pandas as pd

from analyzer import indicators


def test_rsi_all_gains_saturates_to_100():
    s = pd.Series(np.arange(1, 60, dtype=float))
    r = indicators.rsi(s, 14)
    assert r.iloc[-1] == 100.0


def test_rsi_all_losses_saturates_to_0():
    s = pd.Series(np.arange(60, 1, -1, dtype=float))
    r = indicators.rsi(s, 14)
    assert r.iloc[-1] == 0.0


def test_rsi_sanity_range():
    rng = np.random.default_rng(1)
    s = pd.Series(100 + rng.normal(0, 1, 200).cumsum())
    r = indicators.rsi(s, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_sma_matches_manual():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    m = indicators.sma(s, 3)
    assert np.isnan(m.iloc[0]) and np.isnan(m.iloc[1])
    assert m.iloc[2] == 2.0
    assert m.iloc[-1] == 4.0


def test_macd_signal_shape():
    s = pd.Series(np.linspace(100, 200, 100))
    m = indicators.macd(s)
    assert set(m.columns) == {"macd", "signal", "hist"}
    assert len(m) == 100


def test_bollinger_width_positive():
    s = pd.Series(100 + np.random.default_rng(2).normal(0, 1, 100))
    bb = indicators.bollinger(s, period=20, stddev=2.0).dropna()
    assert (bb["upper"] > bb["lower"]).all()


def test_crossed_above_and_below():
    a = pd.Series([1.0, 2.0])
    b = pd.Series([2.0, 1.5])
    assert indicators.crossed_above(a, b) is True
    assert indicators.crossed_below(a, b) is False

    a2 = pd.Series([2.0, 1.0])
    b2 = pd.Series([1.5, 2.0])
    assert indicators.crossed_below(a2, b2) is True


def test_pct_change_over():
    s = pd.Series([100.0, 101.0, 102.0, 110.0])
    assert indicators.pct_change_over(s, 3) == 10.0
    assert indicators.pct_change_over(s, 10) is None


def test_volume_ratio():
    v = pd.Series([1.0] * 20 + [5.0])
    r = indicators.volume_ratio(v, 10)
    assert r == 5.0
