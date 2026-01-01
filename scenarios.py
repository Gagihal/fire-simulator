"""
Scenario Definitions for FIRE Simulation

Functions that generate different return sequences for Monte Carlo simulation
and historical backtesting.
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any


# =============================================================================
# MONTE CARLO (RANDOM) RETURNS
# =============================================================================

def random_returns(years: int, mean: float = 0.06, std: float = 0.15,
                   seed: int = None) -> List[float]:
    """Generate random returns from a normal distribution."""
    if seed is not None:
        random.seed(seed)
    return [random.gauss(mean, std) for _ in range(years)]


def monte_carlo_returns(years: int, num_simulations: int = 1000,
                        mean: float = 0.06, std: float = 0.15) -> List[List[float]]:
    """Generate many random return sequences for Monte Carlo analysis."""
    return [random_returns(years, mean, std) for _ in range(num_simulations)]


# =============================================================================
# HISTORICAL RETURNS (SHILLER DATA)
# =============================================================================

_HISTORICAL_DATA = None


def load_historical_returns() -> Dict[str, Any]:
    """
    Load Shiller historical returns data.

    Returns dict with:
    - years: List of years (1872-2022)
    - real_returns: Real (inflation-adjusted) total returns including dividends
    - nominal_returns: Nominal returns
    - inflation: Inflation rates
    """
    global _HISTORICAL_DATA
    if _HISTORICAL_DATA is None:
        data_path = Path(__file__).parent / 'historical_returns.json'
        with open(data_path) as f:
            _HISTORICAL_DATA = json.load(f)
    return _HISTORICAL_DATA


def historical_sequence_returns(years_needed: int) -> List[List[float]]:
    """
    Generate return sequences for historical backtesting.

    For each possible starting year in the dataset, creates a sequence
    of the required length. If years_needed exceeds remaining data,
    wraps around to the beginning of the dataset.

    Args:
        years_needed: Number of years of returns needed (e.g., 48 for age 47→95)

    Returns:
        List of return sequences, one per possible starting year.
        Each sequence contains real (inflation-adjusted) returns.
    """
    data = load_historical_returns()
    real_returns = data['real_returns']

    sequences = []
    for start_idx in range(len(real_returns)):
        sequence = []
        for i in range(years_needed):
            idx = (start_idx + i) % len(real_returns)
            sequence.append(real_returns[idx])
        sequences.append(sequence)

    return sequences


def get_historical_years() -> List[int]:
    """Return list of years available in historical data."""
    return load_historical_returns()['years']
