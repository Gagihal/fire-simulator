"""
Scenario Definitions for FIRE Simulation

This file contains functions that generate different return sequences.
Each scenario tells a different story about what the market might do.

Why scenarios matter:
- The baseline (steady 6%) is unrealistic - markets don't give constant returns
- "Sequence of returns risk" means WHEN bad years happen matters enormously
- A crash right after retiring is devastating; the same crash 20 years later barely matters
"""

from typing import List
import random

# We'll use Python's built-in random module first
# Later we can upgrade to numpy for more sophisticated statistics


# =============================================================================
# SCENARIO GENERATORS
# =============================================================================

def baseline_returns(years: int, annual_return: float = 0.06) -> List[float]:
    """
    Steady returns every year - the simplest (and most optimistic) case.

    This is what most naive FIRE calculators assume.
    Reality is much bumpier.

    Args:
        years: How many years of returns to generate
        annual_return: The constant return rate (default 6%)

    Returns:
        List of return rates, one per year

    Example:
        >>> baseline_returns(3, 0.06)
        [0.06, 0.06, 0.06]
    """
    return [annual_return] * years


def crash_year_one(years: int, crash_size: float = -0.40,
                   recovery_return: float = 0.06) -> List[float]:
    """
    Market crashes in year 1, then normal returns.

    This tests "sequence of returns risk" - the danger of bad returns
    early in retirement when your portfolio is largest and most vulnerable.

    Historical context:
    - 2008 crash: S&P 500 down ~37%
    - 2000-2002 dot-com: Down ~49% total
    - 1929 crash: Down ~89% over 3 years

    We use -40% as a severe but not extreme scenario.

    Args:
        years: Total years to simulate
        crash_size: First year return (negative number, e.g., -0.40 for -40%)
        recovery_return: Returns for remaining years

    Returns:
        List starting with crash, then steady returns
    """
    if years < 1:
        return []
    return [crash_size] + [recovery_return] * (years - 1)


def lost_decade(years: int, bad_years: int = 10, bad_return: float = 0.02,
                good_return: float = 0.06) -> List[float]:
    """
    Low returns for first N years, then normal.

    This models scenarios like:
    - Japan 1990-2020 (decades of near-zero growth)
    - US 2000-2010 ("lost decade" with ~0% real returns)

    With 2% nominal returns and 2% inflation, you're getting 0% real growth
    while still withdrawing money - a slow bleed.

    Args:
        years: Total years to simulate
        bad_years: How many years of poor returns
        bad_return: Return during the bad period
        good_return: Return after recovery

    Returns:
        List with bad_years of bad_return, then good_return
    """
    bad_period = [bad_return] * min(bad_years, years)
    good_period = [good_return] * max(0, years - bad_years)
    return bad_period + good_period


def double_crash(years: int, crash_size: float = -0.30,
                 gap_years: int = 7, normal_return: float = 0.06) -> List[float]:
    """
    Two crashes separated by recovery period.

    Models something like 2000-2002 followed by 2008:
    - Crash, partial recovery, crash again
    - Tests resilience to repeated bad luck

    Args:
        years: Total years
        crash_size: Size of each crash
        gap_years: Years between crashes
        normal_return: Returns in non-crash years
    """
    returns = []
    for year in range(years):
        if year == 0:  # First crash
            returns.append(crash_size)
        elif year == gap_years:  # Second crash
            returns.append(crash_size)
        else:
            returns.append(normal_return)
    return returns


# =============================================================================
# MONTE CARLO
# =============================================================================

def random_returns(years: int, mean: float = 0.06, std: float = 0.15,
                   seed: int = None) -> List[float]:
    """
    Generate random returns from a normal distribution.

    Args:
        years: How many years of returns
        mean: Average return (default 6%)
        std: Standard deviation (default 15%)
        seed: Optional seed for reproducibility

    Returns:
        List of random returns
    """
    if seed is not None:
        random.seed(seed)
    return [random.gauss(mean, std) for _ in range(years)]


def monte_carlo_returns(years: int, num_simulations: int = 1000,
                        mean: float = 0.06, std: float = 0.15) -> List[List[float]]:
    """
    Generate many random return sequences for Monte Carlo analysis.

    Monte Carlo simulation answers: "What's the RANGE of possible outcomes?"
    Instead of one prediction, we get a probability distribution.

    Example output interpretation:
    - If 95% of simulations survive, you have 95% confidence
    - The spread between 5th and 95th percentile shows uncertainty

    Args:
        years: Years per simulation
        num_simulations: How many different futures to simulate
        mean: Average return per year
        std: Standard deviation

    Returns:
        List of return sequences (list of lists)
    """
    return [random_returns(years, mean, std) for _ in range(num_simulations)]


# =============================================================================
# SCENARIO PRESETS
# =============================================================================

# These are ready-to-use scenario definitions
# Each returns a dict with a name, description, and the returns generator

SCENARIOS = {
    'baseline': {
        'name': 'Baseline (6% steady)',
        'description': 'Optimistic: steady 6% returns every year',
        'generator': lambda years: baseline_returns(years, 0.06)
    },
    'crash_year_1': {
        'name': 'Crash Year 1 (-40%)',
        'description': 'Market crashes 40% immediately after you retire',
        'generator': lambda years: crash_year_one(years, -0.40, 0.06)
    },
    'lost_decade': {
        'name': 'Lost Decade (2% for 10 years)',
        'description': 'Japan/2000s scenario: 10 years of minimal returns',
        'generator': lambda years: lost_decade(years, 10, 0.02, 0.06)
    },
    'double_crash': {
        'name': 'Double Crash (-30% x2)',
        'description': 'Two 30% crashes, 7 years apart (like 2000 + 2008)',
        'generator': lambda years: double_crash(years, -0.30, 7, 0.06)
    },
    'conservative': {
        'name': 'Conservative (4% steady)',
        'description': 'Lower but safer: 4% returns (2% real after inflation)',
        'generator': lambda years: baseline_returns(years, 0.04)
    },
    'pessimistic': {
        'name': 'Pessimistic (3% steady)',
        'description': 'Very low: 3% returns (1% real)',
        'generator': lambda years: baseline_returns(years, 0.03)
    }
}


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Scenario Examples (10 years) ===\n")

    for key, scenario in SCENARIOS.items():
        returns = scenario['generator'](10)
        # Format returns as percentages
        returns_str = ', '.join([f"{r*100:+.0f}%" for r in returns[:5]])
        print(f"{scenario['name']}:")
        print(f"  First 5 years: {returns_str}...")
        print()

    print("=== Random Returns Sample ===\n")
    random_sample = random_returns(10, mean=0.06, std=0.15, seed=42)
    returns_str = ', '.join([f"{r*100:+.1f}%" for r in random_sample])
    print(f"10 random years: {returns_str}")
    print(f"Average: {sum(random_sample)/len(random_sample)*100:.1f}%")
