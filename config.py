"""
Configuration for FIRE simulation.

This file contains your personal financial parameters.
Tweak these values to see how changes affect your outcomes.
"""

# =============================================================================
# YOUR SITUATION
# =============================================================================

DEFAULT_PARAMS = {
    # Portfolio
    'starting_portfolio': 1_200_000,  # Expected at FIRE (2029)

    # Annual expenses
    'annual_expenses': 32_500,        # Midpoint of 30-35k lifestyle

    # Income phases (age-dependent)
    # Income changes as you age - RGT winds down, pension kicks in
    'income_phases': [
        {'start_age': 47, 'end_age': 57, 'amount': 17_000, 'name': 'RGT + trading'},
        {'start_age': 58, 'end_age': 64, 'amount': 10_000, 'name': 'Trading only'},
        {'start_age': 65, 'end_age': 95, 'amount': 8_400, 'name': 'Kansaneläke'},
    ],

    # Windfall events (one-time additions to portfolio)
    'windfalls': [
        {'age': 55, 'amount': 200_000, 'name': 'Inheritance'},
        {'age': 58, 'amount': 60_000, 'name': 'RGT liquidation'},
    ],

    # Investment assumptions
    'expected_return': 0.06,          # 6% nominal (before inflation)
    'inflation': 0.02,                # 2% annual inflation
    'volatility': 0.15,               # Standard deviation for Monte Carlo

    # Time horizon
    'start_age': 47,                  # Age at FIRE (2029)
    'end_age': 95,                    # Model until this age

    # Emergency hustle (behavioral response to early crashes)
    # If portfolio crashes in first few years, you'd realistically return to work
    'emergency_hustle': {
        'enabled': True,
        'trigger_age_max': 52,        # Only trigger in first 5 years (47+5)
        'portfolio_threshold': 0.70,  # Trigger if portfolio < 70% of start
        'extra_income': 40_000,       # Annual hustle income
        'duration': 3,                # Years of hustle
    },

    # Dynamic spending rules (reduce expenses when portfolio drops)
    # All amounts in today's euros - will grow with inflation
    'spending_rules': {
        'enabled': True,
        'drop_threshold': 0.50,       # Trigger reduction at 50% of start
        'recovery_threshold': 0.60,   # Recover to normal at 60% of start
        'reduced_spending': 25_000,   # €25k/year when belt-tightening
        'lean_spending': 17_000,      # €17k/year lean mode (age 60+)
        'lean_age': 60,               # Age when lean mode becomes available
    },

    # Mortality modeling (realistic death probability each year)
    # Uses Finnish male mortality data from Tilastokeskus 2021
    'mortality': {
        'enabled': True,
        'healthy_lifestyle_factor': 0.65,  # Multiplier for qx values
                                           # 0.65 = ~35% lower mortality than average
                                           # (fit, non-smoker, tall, family longevity)
    },
}

# =============================================================================
# FINNISH MALE MORTALITY TABLE (Tilastokeskus 2021)
# =============================================================================
# qx = probability of dying within the year, per 1,000 males
# Source: Statistics Finland life tables for Finnish males

FINNISH_MALE_MORTALITY = {
    # Age: qx per 1,000
    47: 3.8,
    48: 4.1,
    49: 4.4,
    50: 4.8,
    51: 5.2,
    52: 5.7,
    53: 6.2,
    54: 6.8,
    55: 7.5,
    56: 8.3,
    57: 9.2,
    58: 10.2,
    59: 11.3,
    60: 12.5,
    61: 13.9,
    62: 15.4,
    63: 17.1,
    64: 19.0,
    65: 21.1,
    66: 23.4,
    67: 26.0,
    68: 28.9,
    69: 32.1,
    70: 35.7,
    71: 39.7,
    72: 44.2,
    73: 49.2,
    74: 54.8,
    75: 61.1,
    76: 68.1,
    77: 75.9,
    78: 84.6,
    79: 94.3,
    80: 105.1,
    81: 117.1,
    82: 130.5,
    83: 145.4,
    84: 162.0,
    85: 180.5,
    86: 201.0,
    87: 223.8,
    88: 249.2,
    89: 277.5,
    90: 308.9,
    91: 343.8,
    92: 382.4,
    93: 425.2,
    94: 472.5,
    95: 525.0,
}
