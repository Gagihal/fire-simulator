"""
Stress Test Scenarios for FIRE Simulation

Defines pessimistic market scenarios to stress-test retirement plans.
Each scenario generates return sequences that model specific historical
or hypothetical adverse conditions.
"""

import random
from typing import List, Dict, Any


# =============================================================================
# SCENARIO METADATA
# =============================================================================

STRESS_SCENARIOS: Dict[str, Dict[str, Any]] = {
    'japan_lost_decades': {
        'name': 'Japan Lost Decades',
        'description': 'Extended stagnation: -40% crash followed by 0-1% real returns for 20+ years',
        'likelihood': 'Low for diversified global equity',
        'commentary': (
            'Japan experienced near-zero real returns for 34 years after the 1989 bubble. '
            'While possible for single-country exposure, global diversification makes this less likely. '
            'However, demographic headwinds could create similar patterns in aging economies.'
        ),
        'historical_precedent': 'Japan 1989-2023',
        'severity': 'extreme'
    },
    'sequence_risk_early_crash': {
        'name': 'Sequence of Returns Risk (Early Crash)',
        'description': 'Major crash (-35%, -15%, -10%) in years 1-3, then normal returns',
        'likelihood': 'Moderate (happens every 20-30 years)',
        'commentary': (
            'The worst time to retire is just before a major crash. '
            'Selling assets during drawdowns permanently impairs your portfolio. '
            'This is the #1 killer of early retirees and why the first 5 years matter most.'
        ),
        'historical_precedent': '2000 dot-com, 2008 GFC, 1929',
        'severity': 'high'
    },
    'climate_transition_shock': {
        'name': 'Climate Transition Shock',
        'description': 'Normal returns for 10 years, then permanent shift to 2-3% real returns',
        'likelihood': 'Unknown but increasing concern',
        'commentary': (
            'Models a scenario where climate transition costs permanently reduce corporate profitability. '
            'Stranded assets, carbon costs, and adaptation spending could compress returns for decades. '
            'This is a tail risk that traditional models don\'t capture.'
        ),
        'historical_precedent': 'Novel scenario',
        'severity': 'high'
    },
    'stagflation_1970s': {
        'name': '1970s Stagflation Redux',
        'description': 'High inflation with near-zero real returns for a decade',
        'likelihood': 'Low-moderate (policy dependent)',
        'commentary': (
            'The 1970s saw real stock returns near zero for over a decade despite high nominal returns. '
            'Inflation is the silent portfolio killer - it erodes purchasing power while markets appear stable. '
            'Could recur if inflation becomes entrenched or supply shocks persist.'
        ),
        'historical_precedent': '1966-1982 US markets',
        'severity': 'high'
    },
    'great_depression': {
        'name': 'Great Depression Sequence',
        'description': 'Severe crash (-50% Y1, -30% Y2) then slow 0-3% recovery for 8 years',
        'likelihood': 'Very low (banking/regulatory changes)',
        'commentary': (
            'The worst decade in US market history saw an 85% drawdown peak-to-trough. '
            'Modern banking safeguards make an exact repeat unlikely, but variants are possible. '
            'If your plan survives this, it\'s robust against almost anything.'
        ),
        'historical_precedent': '1929-1939',
        'severity': 'extreme'
    },
    'secular_stagnation': {
        'name': 'Secular Stagnation',
        'description': 'Permanently lower 3-4% real returns from day one',
        'likelihood': 'Moderate (demographics, debt)',
        'commentary': (
            'Many economists argue aging demographics and high debt levels will lead to permanently lower growth. '
            'The high returns of 1980-2020 may have been historically anomalous. '
            'This scenario tests whether your plan works in a "new normal" of lower returns.'
        ),
        'historical_precedent': 'Japan post-1990, some EU economies',
        'severity': 'moderate'
    },
    'rising_rates_regime': {
        'name': 'Rising Rates Regime Shift',
        'description': 'First 5 years: lower returns with higher volatility, then normal',
        'likelihood': 'Moderate-high near term',
        'commentary': (
            'The 40-year bond bull market ended in 2022. Transitioning to higher rates typically causes '
            'multiple compression and increased volatility. This tests early retirement during '
            'a regime shift similar to the early 1970s.'
        ),
        'historical_precedent': '1970s, 2022-?',
        'severity': 'moderate'
    },
    'euro_crisis_finland': {
        'name': 'Euro Crisis / Currency Collapse',
        'description': 'Finland-specific: -30% shock + 5 years of high inflation eroding real returns',
        'likelihood': 'Low but non-zero for eurozone',
        'commentary': (
            'Models a severe eurozone crisis with significant wealth destruction and inflation. '
            'Relevant for Euro-denominated portfolios. Currency and political risk are real, '
            'as Greece 2010-2015 and Argentina 2001 demonstrated.'
        ),
        'historical_precedent': 'Greece 2010-2015, Argentina 2001',
        'severity': 'high'
    }
}


# =============================================================================
# SCENARIO GENERATORS
# =============================================================================

def generate_japan_lost_decades(years: int, num_sims: int) -> List[List[float]]:
    """
    Japan Lost Decades: Extended stagnation after initial crash.

    Pattern:
    - Year 1: -35% to -45% crash
    - Years 2-20: 0-2% real returns with high volatility
    - Years 21+: Gradual recovery to 3-4% returns
    """
    sequences = []
    for _ in range(num_sims):
        sequence = []
        crash_severity = random.uniform(-0.45, -0.35)

        for year in range(years):
            if year == 0:
                # Initial crash
                ret = crash_severity
            elif year < 20:
                # Lost decades: near-zero real returns with volatility
                ret = random.gauss(0.01, 0.18)
            else:
                # Gradual recovery
                ret = random.gauss(0.035, 0.15)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_sequence_risk_crash(
    years: int,
    num_sims: int,
    mean: float = 0.06,
    std: float = 0.15
) -> List[List[float]]:
    """
    Sequence of Returns Risk: Big crash early, then normal Monte Carlo.

    Pattern:
    - Year 1: -35% (±5%)
    - Year 2: -15% (±5%)
    - Year 3: -10% (±5%)
    - Years 4+: Normal Monte Carlo with user's expected return/volatility
    """
    sequences = []
    for _ in range(num_sims):
        sequence = []
        for year in range(years):
            if year == 0:
                ret = random.gauss(-0.35, 0.05)
            elif year == 1:
                ret = random.gauss(-0.15, 0.05)
            elif year == 2:
                ret = random.gauss(-0.10, 0.05)
            else:
                ret = random.gauss(mean, std)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_climate_transition(
    years: int,
    num_sims: int,
    mean: float = 0.06,
    std: float = 0.15
) -> List[List[float]]:
    """
    Climate Transition Shock: Normal returns then permanent low returns.

    Pattern:
    - Years 1-10: Normal returns (user's expected return)
    - Years 11+: Permanently lower returns (2-3% real)
    """
    sequences = []
    transition_year = 10

    for _ in range(num_sims):
        sequence = []
        # Post-transition returns vary by simulation
        post_transition_mean = random.uniform(0.02, 0.03)

        for year in range(years):
            if year < transition_year:
                ret = random.gauss(mean, std)
            else:
                # Lower returns, slightly lower volatility
                ret = random.gauss(post_transition_mean, 0.12)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_stagflation_1970s(years: int, num_sims: int) -> List[List[float]]:
    """
    1970s Stagflation: High inflation erodes real returns for a decade.

    Pattern:
    - Years 1-10: Near-zero real returns (0-1%) with high volatility
    - Years 11+: Recovery to normal 5-6% returns
    """
    sequences = []
    stagflation_years = 10

    for _ in range(num_sims):
        sequence = []
        for year in range(years):
            if year < stagflation_years:
                # High nominal returns but inflation eats them
                # Net real return near zero
                ret = random.gauss(0.005, 0.16)
            else:
                # Recovery
                ret = random.gauss(0.055, 0.15)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_great_depression(years: int, num_sims: int) -> List[List[float]]:
    """
    Great Depression: Parametric model of 1929-1939.

    Pattern:
    - Year 1: -50% (±10%)
    - Year 2: -30% (±10%)
    - Years 3-10: Slow recovery 0-3%
    - Years 11+: Normal returns
    """
    sequences = []
    for _ in range(num_sims):
        sequence = []
        for year in range(years):
            if year == 0:
                ret = random.gauss(-0.50, 0.10)
            elif year == 1:
                ret = random.gauss(-0.30, 0.10)
            elif year < 10:
                # Slow recovery years
                ret = random.gauss(0.015, 0.12)
            else:
                # Return to normal
                ret = random.gauss(0.06, 0.15)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_secular_stagnation(years: int, num_sims: int) -> List[List[float]]:
    """
    Secular Stagnation: Permanently lower returns from day one.

    Pattern:
    - All years: 3-4% real returns (vs typical 6%)
    - Normal volatility
    """
    sequences = []
    for _ in range(num_sims):
        sequence = []
        # Each simulation gets slightly different "new normal"
        stagnation_mean = random.uniform(0.03, 0.04)

        for _ in range(years):
            ret = random.gauss(stagnation_mean, 0.14)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_rising_rates_regime(
    years: int,
    num_sims: int,
    mean: float = 0.06,
    std: float = 0.15
) -> List[List[float]]:
    """
    Rising Rates Regime Shift: Painful transition then normal.

    Pattern:
    - Years 1-5: Lower returns (mean - 3%), higher volatility (*1.3)
    - Years 6+: Normal Monte Carlo
    """
    sequences = []
    transition_years = 5

    for _ in range(num_sims):
        sequence = []
        for year in range(years):
            if year < transition_years:
                # Lower returns, higher volatility during transition
                ret = random.gauss(mean - 0.03, std * 1.3)
            else:
                ret = random.gauss(mean, std)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


def generate_euro_crisis_finland(
    years: int,
    num_sims: int,
    mean: float = 0.06,
    std: float = 0.15
) -> List[List[float]]:
    """
    Euro Crisis / Currency Collapse: Finland-specific scenario.

    Pattern:
    - Year 1: -30% shock
    - Years 2-6: High inflation eats returns (-3% real on average)
    - Years 7+: Recovery, but with elevated volatility
    """
    sequences = []
    for _ in range(num_sims):
        sequence = []
        for year in range(years):
            if year == 0:
                # Initial shock
                ret = random.gauss(-0.30, 0.05)
            elif year < 6:
                # High inflation period - negative real returns
                ret = random.gauss(-0.03, 0.18)
            else:
                # Recovery with elevated volatility
                ret = random.gauss(mean * 0.9, std * 1.1)
            sequence.append(ret)

        sequences.append(sequence)
    return sequences


# =============================================================================
# DISPATCHER
# =============================================================================

def generate_scenario_returns(
    scenario_id: str,
    years: int,
    num_sims: int,
    mean: float = 0.06,
    std: float = 0.15
) -> List[List[float]]:
    """
    Generate return sequences for a specific stress scenario.

    Args:
        scenario_id: Key from STRESS_SCENARIOS dict
        years: Number of years to simulate
        num_sims: Number of simulations to run
        mean: User's expected return (for scenarios that use it)
        std: User's volatility (for scenarios that use it)

    Returns:
        List of return sequences, one per simulation
    """
    generators = {
        'japan_lost_decades': lambda: generate_japan_lost_decades(years, num_sims),
        'sequence_risk_early_crash': lambda: generate_sequence_risk_crash(years, num_sims, mean, std),
        'climate_transition_shock': lambda: generate_climate_transition(years, num_sims, mean, std),
        'stagflation_1970s': lambda: generate_stagflation_1970s(years, num_sims),
        'great_depression': lambda: generate_great_depression(years, num_sims),
        'secular_stagnation': lambda: generate_secular_stagnation(years, num_sims),
        'rising_rates_regime': lambda: generate_rising_rates_regime(years, num_sims, mean, std),
        'euro_crisis_finland': lambda: generate_euro_crisis_finland(years, num_sims, mean, std),
    }

    if scenario_id not in generators:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    return generators[scenario_id]()


def get_all_scenario_ids() -> List[str]:
    """Return list of all available scenario IDs."""
    return list(STRESS_SCENARIOS.keys())


def get_scenario_metadata(scenario_id: str) -> Dict[str, Any]:
    """Get metadata for a specific scenario."""
    if scenario_id not in STRESS_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    return STRESS_SCENARIOS[scenario_id].copy()
