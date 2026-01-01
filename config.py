"""
Configuration for FIRE simulation - personal financial parameters.
"""

DEFAULT_PARAMS = {
    # Portfolio
    'starting_portfolio': 1_200_000,  # Expected at FIRE (2029)

    # Annual expenses
    'annual_expenses': 32_500,        # Midpoint of 30-35k lifestyle

    # Income phases (age-dependent)
    # RGT = revenue-generating asset (rental property)
    'income_phases': [
        {'start_age': 47, 'end_age': 57, 'amount': 17_000, 'name': 'RGT (rental) + trading'},
        {'start_age': 58, 'end_age': 64, 'amount': 10_000, 'name': 'Trading only'},
        {'start_age': 65, 'end_age': 95, 'amount': 8_400, 'name': 'Kansaneläke (Finnish state pension)'},
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

    # Mortality modeling using Finnish male mortality data
    'mortality': {
        'enabled': True,
        'health_class': 'average',      # 'excellent', 'average', or 'impaired'
        'tech_scenario': 'moderate',    # 'conservative', 'moderate', or 'optimistic'
        # Legacy support (deprecated, use health_class instead)
        'healthy_lifestyle_factor': None,
    },
}

# Health class parameters for age-varying mortality adjustment
# Based on SOA 2015 VBT Super Preferred / Standard ratios
# Health advantage diminishes with age (convergence toward frailty)
# Convergence completes by age 100 to allow modeling of supercentenarians
HEALTH_CLASS_PARAMS = {
    'excellent': {
        'base_ratio': 0.30,         # Ratio at age 45 (70% lower mortality)
        'convergence_ratio': 1.0,   # Fully converged by age 100
        'convergence_age': 100,     # Age at which convergence completes
        'description': 'Non-smoker, healthy weight, regular exercise, no chronic conditions, family longevity'
    },
    'average': {
        'base_ratio': 1.0,
        'convergence_ratio': 1.0,
        'convergence_age': 100,
        'description': 'General population baseline'
    },
    'impaired': {
        'base_ratio': 1.50,         # 50% higher mortality at age 45
        'convergence_ratio': 1.0,   # Fully converged by age 100
        'convergence_age': 100,
        'description': 'Chronic conditions, smoking history, obesity, or significant health concerns'
    }
}

# Technology improvement scenarios for future mortality reduction
# Based on demographic research: improvement varies by age group
TECH_SCENARIO_PARAMS = {
    'conservative': {
        'rate_multiplier': 0.5,
        'description': 'Improvement slows significantly from historical rates (+1-2 years LE)'
    },
    'moderate': {
        'rate_multiplier': 1.0,
        'description': 'Continue post-2010 trends (+2-3 years LE)'
    },
    'optimistic': {
        'rate_multiplier': 1.5,
        'description': 'Medical advances accelerate - AI, gene therapy, etc (+4-5 years LE)'
    }
}

# Age-specific base improvement rates (annual) for tech dimension
# Middle ages improve faster (cardiovascular advances), oldest ages slower
# Ages 100+ have diminishing returns from medical advances
AGE_IMPROVEMENT_RATES = {
    (0, 65): 0.015,    # 1.5% annual improvement for working/early retirement ages
    (65, 85): 0.012,   # 1.2% annual improvement for young-old
    (85, 100): 0.006,  # 0.6% annual improvement for oldest-old
    (100, 150): 0.003  # 0.3% annual improvement for supercentenarians (diminishing returns)
}

# Finnish male mortality table (Tilastokeskus 2021)
# qx = probability of dying within the year, per 1,000 males
# Ages 47-95: Official Finnish statistics
# Ages 96-110: Extrapolated using Gompertz-Makeham model and supercentenarian research
#              Mortality plateaus around 650-685/1000 at extreme ages
FINNISH_MALE_MORTALITY = {
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
    # Extended ages (96-110) based on supercentenarian research
    # Mortality continues rising but plateaus around 650-685
    96: 550.0,
    97: 572.0,
    98: 592.0,
    99: 610.0,
    100: 625.0,
    101: 638.0,
    102: 650.0,
    103: 660.0,
    104: 668.0,
    105: 675.0,
    106: 680.0,
    107: 683.0,
    108: 685.0,
    109: 685.0,
    110: 685.0,  # Plateau - mortality doesn't increase beyond this
}
