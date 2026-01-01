#!/usr/bin/env python3
"""
Export FIRE simulation data to JSON for visualization.

Runs Monte Carlo simulation and exports percentile trajectories, failure
examples, and summary statistics.

Note: Mortality modeling is handled here (not in fire_simulator) because
death doesn't change the financial simulation - we run the full simulation
then categorize outcomes based on sampled death age.
"""

import json
import random
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import (
    DEFAULT_PARAMS, FINNISH_MALE_MORTALITY,
    HEALTH_CLASS_PARAMS, TECH_SCENARIO_PARAMS, AGE_IMPROVEMENT_RATES
)
from fire_simulator import run_simulation, SimulationResult
from scenarios import monte_carlo_returns, historical_sequence_returns, load_historical_returns


# =============================================================================
# MORTALITY MODELING - Two-Dimension Model
# =============================================================================
# Dimension 1: Personal Health (age-varying adjustment with convergence)
# Dimension 2: Medical Advances (gradual improvement over time)
# =============================================================================


def health_adjusted_mortality(age: int, base_qx: float, health_class: str = "average") -> float:
    """
    Age-varying health adjustment with convergence.

    Based on SOA 2015 VBT Super Preferred / Standard ratios.
    Health advantage diminishes with age as everyone converges toward frailty.
    Convergence completes by age 100 to allow proper modeling of supercentenarians.

    Args:
        age: Current age
        base_qx: Base mortality rate from table (per 1000)
        health_class: "excellent", "average", or "impaired"

    Returns:
        Adjusted mortality rate (per 1000)
    """
    params = HEALTH_CLASS_PARAMS.get(health_class, HEALTH_CLASS_PARAMS['average'])
    base_ratio = params['base_ratio']
    convergence_ratio = params['convergence_ratio']
    convergence_age = params.get('convergence_age', 100)

    # Linear convergence from base_ratio at age 45 to convergence_ratio at convergence_age
    # For ages outside this range, clamp to the boundary values
    base_age = 45
    if age <= base_age:
        ratio = base_ratio
    elif age >= convergence_age:
        ratio = convergence_ratio
    else:
        # Linear interpolation from base_age to convergence_age
        years_span = convergence_age - base_age
        years_from_base = age - base_age
        ratio = base_ratio + (convergence_ratio - base_ratio) * (years_from_base / years_span)

    return base_qx * ratio


def mortality_improvement_factor(age: int, years_in_future: int, scenario: str = "moderate") -> float:
    """
    Calculate mortality improvement factor for future years.

    Based on demographic research: improvement rates vary by age and
    are expected to converge to long-term rates over time.

    Args:
        age: Age at which mortality is being assessed
        years_in_future: How many years from retirement (0 = today)
        scenario: "conservative", "moderate", or "optimistic"

    Returns:
        Multiplier to apply to current mortality (< 1 means improved/lower mortality)
    """
    if years_in_future <= 0:
        return 1.0

    # Get age-specific base improvement rate
    base_rate = 0.012  # Default: 1.2% annual improvement
    for (age_low, age_high), rate in AGE_IMPROVEMENT_RATES.items():
        if age_low <= age < age_high:
            base_rate = rate
            break

    # Apply scenario multiplier
    scenario_params = TECH_SCENARIO_PARAMS.get(scenario, TECH_SCENARIO_PARAMS['moderate'])
    rate = base_rate * scenario_params['rate_multiplier']

    # Compound improvement over time
    # Each year, mortality is reduced by the improvement rate
    return (1 - rate) ** years_in_future


def _get_qx(
    age: int,
    mortality_table: Dict[int, float],
    health_class: str = "average",
    tech_scenario: str = "moderate",
    years_from_retirement: int = 0
) -> float:
    """
    Get death probability (qx per 1,000) for a given age with adjustments.

    Applies both health adjustment and technology improvement.

    Args:
        age: Current age
        mortality_table: Dict of age -> qx (death probability per 1,000)
        health_class: "excellent", "average", or "impaired"
        tech_scenario: "conservative", "moderate", or "optimistic"
        years_from_retirement: Years since retirement started (for tech improvement)

    Returns:
        Adjusted mortality rate (per 1000)
    """
    # Get base rate from table
    if age in mortality_table:
        base_qx = mortality_table[age]
    else:
        min_age = min(mortality_table.keys())
        max_age = max(mortality_table.keys())
        if age < min_age:
            base_qx = mortality_table[min_age]
        else:
            base_qx = 500  # 50% annual death rate for very old ages

    # Apply health adjustment (age-varying)
    adjusted_qx = health_adjusted_mortality(age, base_qx, health_class)

    # Apply tech improvement (time-varying)
    tech_factor = mortality_improvement_factor(age, years_from_retirement, tech_scenario)
    adjusted_qx = adjusted_qx * tech_factor

    return adjusted_qx


def sample_death_age(
    start_age: int,
    end_age: int,
    mortality_table: Dict[int, float],
    health_class: str = "average",
    tech_scenario: str = "moderate"
) -> Optional[int]:
    """
    Sample a death age using mortality table probabilities.

    Args:
        start_age: Age at start of simulation (retirement age)
        end_age: Maximum age to simulate
        mortality_table: Dict of age -> qx (death probability per 1,000)
        health_class: "excellent", "average", or "impaired"
        tech_scenario: "conservative", "moderate", or "optimistic"

    Returns:
        Age of death, or None if survived to end_age
    """
    for age in range(start_age, end_age + 1):
        years_from_retirement = age - start_age
        qx = _get_qx(age, mortality_table, health_class, tech_scenario, years_from_retirement)

        death_prob = qx / 1000

        if random.random() < death_prob:
            return age

    return None  # Survived to end_age


def calculate_survival_probability(
    start_age: int,
    end_age: int,
    mortality_table: Dict[int, float],
    health_class: str = "average",
    tech_scenario: str = "moderate"
) -> float:
    """
    Calculate probability of surviving from start_age to end_age.

    This is the cumulative survival probability:
    P(survive to end) = Product of (1 - qx/1000) for each year
    """
    survival_prob = 1.0
    for age in range(start_age, end_age + 1):
        years_from_retirement = age - start_age
        qx = _get_qx(age, mortality_table, health_class, tech_scenario, years_from_retirement)
        death_prob = qx / 1000
        survival_prob *= (1 - death_prob)
    return survival_prob


def get_life_expectancy(
    start_age: int,
    mortality_table: Dict[int, float],
    health_class: str = "average",
    tech_scenario: str = "moderate",
    max_age: int = 110
) -> float:
    """
    Calculate expected remaining years of life from start_age.
    """
    survival_prob = 1.0
    expected_years = 0.0

    for age in range(start_age, max_age + 1):
        years_from_retirement = age - start_age
        qx = _get_qx(age, mortality_table, health_class, tech_scenario, years_from_retirement)
        death_prob = qx / 1000

        # Expected years = sum of P(alive at each age)
        expected_years += survival_prob

        survival_prob *= (1 - death_prob)

    return expected_years


def calculate_dynamic_end_age(
    start_age: int,
    mortality_table: Dict[int, float],
    health_class: str = "average",
    tech_scenario: str = "moderate",
    survival_threshold: float = 0.01,
    hard_cap: int = 110
) -> dict:
    """
    Calculate simulation end age based on survival probability threshold.

    Instead of asking users to pick an end_age, we calculate the age at which
    survival probability drops below the threshold (default 1%). This ensures
    the simulation runs long enough to capture realistic longevity scenarios
    for each health/tech combination.

    Args:
        start_age: Age at retirement/simulation start
        mortality_table: Dict of age -> qx (death probability per 1,000)
        health_class: "excellent", "average", or "impaired"
        tech_scenario: "conservative", "moderate", or "optimistic"
        survival_threshold: End simulation when survival drops below this (default 0.01 = 1%)
        hard_cap: Maximum end age regardless of survival probability

    Returns:
        Dict containing:
            - end_age: The calculated end age for simulation
            - survival_at_end: The survival probability at that age
            - life_expectancy: Expected years of life from start_age
            - survival_percentiles: Survival probability at key ages (75, 85, 90, 95, 100, 105)
    """
    survival_prob = 1.0
    expected_years = 0.0
    calculated_end_age = hard_cap

    # Track survival at key ages for display
    key_ages = [75, 80, 85, 90, 95, 100, 105, 110]
    survival_percentiles = {}

    for age in range(start_age, hard_cap + 1):
        years_from_retirement = age - start_age
        qx = _get_qx(age, mortality_table, health_class, tech_scenario, years_from_retirement)
        death_prob = qx / 1000

        # Track survival at key ages
        if age in key_ages:
            survival_percentiles[age] = round(survival_prob * 100, 1)

        # Accumulate expected years
        expected_years += survival_prob

        # Apply mortality for this year
        survival_prob *= (1 - death_prob)

        # Check if we've dropped below threshold
        if survival_prob < survival_threshold and calculated_end_age == hard_cap:
            calculated_end_age = age
            # Continue loop to calculate full life expectancy and all percentiles

    # Ensure end_age is at least start_age + 10 (minimum reasonable simulation)
    calculated_end_age = max(calculated_end_age, start_age + 10)

    return {
        'end_age': calculated_end_age,
        'survival_at_end': round(survival_prob * 100, 2),
        'life_expectancy': round(expected_years, 1),
        'survival_percentiles': survival_percentiles
    }


# Legacy compatibility function
def _get_legacy_health_class(healthy_factor: float) -> str:
    """Map old healthy_lifestyle_factor to new health_class."""
    if healthy_factor is None:
        return 'average'
    if healthy_factor <= 0.5:
        return 'excellent'
    elif healthy_factor >= 1.2:
        return 'impaired'
    else:
        return 'average'


# =============================================================================
# HELPER FUNCTIONS - Reduce code duplication
# =============================================================================

def _extract_mortality_config(params: dict) -> tuple:
    """
    Extract mortality configuration from params with legacy support.

    Returns:
        Tuple of (enabled, health_class, tech_scenario)
    """
    mortality_config = params.get('mortality', {})
    enabled = mortality_config.get('enabled', False)
    health_class = mortality_config.get('health_class', 'average')
    tech_scenario = mortality_config.get('tech_scenario', 'moderate')

    # Legacy support: if old healthy_lifestyle_factor is provided, map to health_class
    if mortality_config.get('healthy_lifestyle_factor') is not None:
        health_class = _get_legacy_health_class(mortality_config['healthy_lifestyle_factor'])

    return enabled, health_class, tech_scenario


def _calculate_theoretical_mortality_stats(
    start_age: int,
    end_age: int,
    health_class: str,
    tech_scenario: str,
    mortality_enabled: bool
) -> tuple:
    """
    Calculate theoretical survival probability and life expectancy.

    Returns:
        Tuple of (survival_to_end_prob, life_expectancy)
    """
    if mortality_enabled:
        survival_to_end_prob = calculate_survival_probability(
            start_age, end_age, FINNISH_MALE_MORTALITY, health_class, tech_scenario
        )
        life_expectancy = get_life_expectancy(
            start_age, FINNISH_MALE_MORTALITY, health_class, tech_scenario
        )
    else:
        survival_to_end_prob = 1.0
        life_expectancy = end_age - start_age

    return survival_to_end_prob, life_expectancy


def _classify_mortality_outcomes(
    results: List,
    death_ages: List[Optional[int]],
    mortality_enabled: bool
) -> dict:
    """
    Classify simulation outcomes considering mortality.

    Categories:
    - survived_to_end: Made it to end_age with money
    - died_with_money: Died naturally before running out
    - ran_out_of_money: Portfolio hit zero while still alive (true failure)

    Returns:
        Dict with outcome counts and rates
    """
    num_simulations = len(results)
    failures = [r for r in results if not r.survived]
    survived_count = num_simulations - len(failures)

    if mortality_enabled:
        survived_to_end_count = 0
        died_with_money = 0
        ran_out_of_money = 0

        for result, death_age in zip(results, death_ages):
            if result.survived:
                if death_age is None:
                    survived_to_end_count += 1
                else:
                    died_with_money += 1
            else:
                ruin_age = result.ruin_age
                if death_age is not None and death_age < ruin_age:
                    died_with_money += 1  # Death "saved" them
                else:
                    ran_out_of_money += 1  # True failure

        real_failure_rate = ran_out_of_money / num_simulations

        actual_deaths = [d for d in death_ages if d is not None]
        avg_death_age = sum(actual_deaths) / len(actual_deaths) if actual_deaths else None
        death_before_end_rate = len(actual_deaths) / num_simulations
    else:
        survived_to_end_count = survived_count
        died_with_money = 0
        ran_out_of_money = len(failures)
        real_failure_rate = len(failures) / num_simulations
        avg_death_age = None
        death_before_end_rate = 0.0

    return {
        'survived_to_end': survived_to_end_count,
        'died_with_money': died_with_money,
        'ran_out_of_money': ran_out_of_money,
        'real_failure_rate': real_failure_rate,
        'avg_death_age': avg_death_age,
        'death_before_end_rate': death_before_end_rate
    }


def calculate_percentile_trajectories(
    results: List[SimulationResult],
    percentiles: List[int] = [5, 10, 15, 25, 50, 75, 95]
) -> Dict[str, List[float]]:
    """
    Calculate portfolio value at each percentile for each age.

    Returns dict with ages and percentile trajectories.
    """
    if not results:
        return {}

    # Get ages from first result (all should have same ages)
    ages = results[0].ages
    num_years = len(ages)

    trajectories = {"ages": ages}

    for p in percentiles:
        trajectory = []
        for year_idx in range(num_years):
            # Get all portfolio values at this year
            values = sorted([r.portfolio_values[year_idx] for r in results])
            # Calculate percentile
            idx = int(len(values) * p / 100)
            idx = min(idx, len(values) - 1)
            trajectory.append(values[idx])
        trajectories[f"p{p}"] = trajectory

    return trajectories


def get_failure_examples(
    results: List[SimulationResult],
    max_examples: int = 20
) -> List[Dict[str, Any]]:
    """
    Get example trajectories from failed simulations.

    Returns list of failures with their trajectories and ruin age.
    """
    failures = [r for r in results if not r.survived]

    # Sort by ruin age (earliest failures first - most interesting)
    failures.sort(key=lambda r: r.ruin_age or 999)

    examples = []
    for r in failures[:max_examples]:
        examples.append({
            "ruin_age": r.ruin_age,
            "trajectory": r.portfolio_values,
            "ages": r.ages,
            "hustle_activated": r.hustle_activated,
            "hustle_activation_age": r.hustle_activation_age,
            "spending_reduced": r.spending_reduced,
            "spending_went_lean": r.spending_went_lean
        })

    return examples


def get_close_call_examples(
    results: List[SimulationResult],
    threshold: float = 200_000,
    max_examples: int = 10
) -> List[Dict[str, Any]]:
    """
    Get examples that survived but got dangerously low.

    "Close calls" = survived but minimum portfolio dropped below threshold.
    """
    close_calls = []

    for r in results:
        if r.survived:
            min_value = min(r.portfolio_values)
            if min_value < threshold:
                close_calls.append({
                    "min_value": min_value,
                    "min_age": r.ages[r.portfolio_values.index(min_value)],
                    "final_portfolio": r.final_portfolio,
                    "trajectory": r.portfolio_values,
                    "ages": r.ages,
                    "hustle_activated": r.hustle_activated,
                    "spending_reduced": r.spending_reduced,
                    "spending_went_lean": r.spending_went_lean
                })

    # Sort by how close they got to ruin
    close_calls.sort(key=lambda x: x["min_value"])

    return close_calls[:max_examples]


def find_required_portfolio(
    base_params: dict,
    target_certainty: float,
    num_simulations: int = 500
) -> int:
    """
    Binary search to find minimum portfolio for target success rate.

    Args:
        base_params: Simulation parameters (portfolio value will be overridden)
        target_certainty: Target success rate (e.g., 0.95 for 95%)
        num_simulations: Simulations per test (lower for speed)

    Returns:
        Minimum portfolio needed to achieve target certainty
    """
    import copy

    low = base_params.get('starting_portfolio', 0)
    # Upper bound: 50x annual expenses or 5x current portfolio
    high = max(
        base_params.get('annual_expenses', 30000) * 50,
        low * 5,
        2_000_000
    )

    # Binary search with €10k precision
    while high - low > 10_000:
        mid = (low + high) // 2
        test_params = copy.deepcopy(base_params)
        test_params['starting_portfolio'] = mid

        result = run_monte_carlo(test_params, num_simulations)
        success_rate = result['summary']['success_rate']

        if success_rate >= target_certainty:
            high = mid
        else:
            low = mid

    return high


def calculate_legacy_tradeoff(
    base_params: dict,
    portfolio_levels: List[int] = None,
    num_simulations: int = 500
) -> dict:
    """
    Calculate the trade-off between personal security and giving capacity.

    For each portfolio level, calculates:
    - Success rate (probability of not running out)
    - Expected final portfolio (median)
    - Expected "legacy" (amount above expenses that could be given)

    The idea: higher portfolio = higher success rate but also more "locked up"
    in personal safety buffer. Lower portfolio = more risk but more available
    for giving/impact now.

    Args:
        base_params: Simulation parameters (portfolio will be varied)
        portfolio_levels: List of portfolio values to test (default: auto-generate)
        num_simulations: Simulations per portfolio level

    Returns:
        Dict with trade-off curve data points
    """
    import copy

    annual_expenses = base_params.get('annual_expenses', 30000)
    years = base_params['end_age'] - base_params['start_age']

    # Auto-generate portfolio levels if not provided (10x to 40x expenses)
    if portfolio_levels is None:
        portfolio_levels = [
            int(annual_expenses * mult)
            for mult in [10, 12, 15, 18, 20, 22, 25, 28, 30, 35, 40]
        ]

    results = []
    for portfolio in portfolio_levels:
        test_params = copy.deepcopy(base_params)
        test_params['starting_portfolio'] = portfolio

        sim_result = run_monte_carlo(test_params, num_simulations)
        s = sim_result['summary']

        # Calculate "giving capacity" - portfolio above what's needed for safety
        # Using median final as proxy for expected outcome
        median_final = s['median_final']

        # How much could you give NOW (upfront) and still have this success rate?
        # Rough approximation: excess = portfolio - (portfolio needed for this rate)
        # More useful: what's the expected leftover at death/end?
        expected_legacy = max(0, median_final)

        # Calculate expected lifetime giving if you gave X% of portfolio growth each year
        # This is complex - for now, just use median final as "legacy potential"

        results.append({
            'portfolio': portfolio,
            'portfolio_multiple': round(portfolio / annual_expenses, 1),
            'success_rate': s['success_rate'],
            'real_failure_rate': s.get('real_failure_rate', 1 - s['success_rate']),
            'median_final': median_final,
            'percentile_5_final': s['percentile_5_final'],
            'percentile_95_final': s['percentile_95_final'],
            'expected_legacy': expected_legacy,
        })

    # Find the "efficient frontier" point - where does extra safety stop being worth it?
    # This is subjective, but we can highlight the 95% success point
    safe_portfolio = None
    for r in results:
        if r['success_rate'] >= 0.95 and safe_portfolio is None:
            safe_portfolio = r['portfolio']

    return {
        'curve': results,
        'annual_expenses': annual_expenses,
        'years': years,
        'safe_portfolio_95': safe_portfolio,
        'params': {
            'start_age': base_params['start_age'],
            'end_age': base_params['end_age'],
            'annual_expenses': annual_expenses,
        }
    }


def run_monte_carlo(params: dict, num_simulations: int = 1000) -> dict:
    """
    Run Monte Carlo simulation and return results.

    This is the core simulation function used by both the API and CLI export.

    With mortality modeling enabled, each simulation gets a randomly sampled
    death age. Outcomes are categorized as:
    - survived_to_end: Made it to end_age with money
    - died_with_money: Died naturally before running out
    - ran_out_of_money: Portfolio hit zero while still alive (true failure)
    """
    years = params['end_age'] - params['start_age']
    start_age = params['start_age']
    end_age = params['end_age']

    # Extract mortality config using helper
    mortality_enabled, health_class, tech_scenario = _extract_mortality_config(params)
    mortality_config = params.get('mortality', {})

    # Calculate theoretical survival stats
    survival_to_end_prob, life_expectancy = _calculate_theoretical_mortality_stats(
        start_age, end_age, health_class, tech_scenario, mortality_enabled
    )

    # Generate return sequences
    all_returns = monte_carlo_returns(
        years,
        num_simulations,
        mean=params['expected_return'],
        std=params['volatility']
    )

    # Run simulations
    results = []
    death_ages = []

    for returns in all_returns:
        if mortality_enabled:
            death_age = sample_death_age(
                start_age, end_age, FINNISH_MALE_MORTALITY, health_class, tech_scenario
            )
        else:
            death_age = None

        death_ages.append(death_age)

        result = run_simulation(
            starting_portfolio=params['starting_portfolio'],
            annual_expenses=params['annual_expenses'],
            returns_sequence=returns,
            start_age=params['start_age'],
            inflation_rate=params['inflation'],
            income_phases=params.get('income_phases'),
            windfalls=params.get('windfalls'),
            emergency_hustle=params.get('emergency_hustle'),
            spending_rules=params.get('spending_rules')
        )
        results.append(result)

    # Calculate summary stats
    survived_count = sum(1 for r in results if r.survived)
    success_rate = survived_count / num_simulations

    final_values = sorted([r.final_portfolio for r in results])
    median_final = final_values[len(final_values) // 2]

    failures = [r for r in results if not r.survived]
    ruin_ages = [r.ruin_age for r in failures]
    avg_ruin_age = sum(ruin_ages) / len(ruin_ages) if ruin_ages else None

    hustle_activations = sum(1 for r in results if r.hustle_activated)
    spending_reductions = sum(1 for r in results if r.spending_reduced)
    lean_mode_activations = sum(1 for r in results if r.spending_went_lean)

    # Classify outcomes using helper
    mortality_outcomes = _classify_mortality_outcomes(results, death_ages, mortality_enabled)

    return {
        "params": {
            "starting_portfolio": params['starting_portfolio'],
            "annual_expenses": params['annual_expenses'],
            "start_age": params['start_age'],
            "end_age": params['end_age'],
            "expected_return": params['expected_return'],
            "inflation": params['inflation'],
            "volatility": params['volatility'],
            "num_simulations": num_simulations,
            "income_phases": params.get('income_phases', []),
            "windfalls": params.get('windfalls', []),
            "emergency_hustle": params.get('emergency_hustle', {}),
            "spending_rules": params.get('spending_rules', {}),
            "mortality": mortality_config
        },
        "percentiles": calculate_percentile_trajectories(results),
        "failures": get_failure_examples(results, max_examples=30),
        "close_calls": get_close_call_examples(results, threshold=300_000),
        "summary": {
            "success_rate": success_rate,
            "failure_count": len(failures),
            "median_final": median_final,
            "avg_ruin_age": avg_ruin_age,
            "hustle_activation_rate": hustle_activations / num_simulations,
            "spending_reduction_rate": spending_reductions / num_simulations,
            "lean_mode_rate": lean_mode_activations / num_simulations,
            "percentile_5_final": final_values[int(len(final_values) * 0.05)],
            "percentile_95_final": final_values[int(len(final_values) * 0.95)],
            "mortality_enabled": mortality_enabled,
            "health_class": health_class if mortality_enabled else None,
            "tech_scenario": tech_scenario if mortality_enabled else None,
            "survived_to_end": mortality_outcomes['survived_to_end'],
            "died_with_money": mortality_outcomes['died_with_money'],
            "ran_out_of_money": mortality_outcomes['ran_out_of_money'],
            "real_failure_rate": mortality_outcomes['real_failure_rate'],
            "avg_death_age": mortality_outcomes['avg_death_age'],
            "death_before_end_rate": mortality_outcomes['death_before_end_rate'],
            "theoretical_survival_to_end": survival_to_end_prob if mortality_enabled else 1.0,
            "life_expectancy": life_expectancy if mortality_enabled else None
        }
    }


def run_simulation_with_custom_returns(
    params: dict,
    all_returns: List[List[float]],
    scenario_id: str = None
) -> dict:
    """
    Run simulation with externally-provided return sequences.

    This allows stress scenarios to inject specific return patterns
    instead of using Monte Carlo or historical sequences.

    Args:
        params: Simulation parameters
        all_returns: Pre-generated return sequences (one per simulation)
        scenario_id: Optional identifier for the scenario (for logging)

    Returns:
        Same structure as run_monte_carlo() for UI compatibility
    """
    num_simulations = len(all_returns)
    start_age = params['start_age']
    end_age = params['end_age']

    # Extract mortality config
    mortality_enabled, health_class, tech_scenario = _extract_mortality_config(params)
    mortality_config = params.get('mortality', {})

    # Calculate theoretical survival stats
    survival_to_end_prob, life_expectancy = _calculate_theoretical_mortality_stats(
        start_age, end_age, health_class, tech_scenario, mortality_enabled
    )

    # Run simulations with custom returns
    results = []
    death_ages = []

    for returns in all_returns:
        if mortality_enabled:
            death_age = sample_death_age(
                start_age, end_age, FINNISH_MALE_MORTALITY, health_class, tech_scenario
            )
        else:
            death_age = None

        death_ages.append(death_age)

        result = run_simulation(
            starting_portfolio=params['starting_portfolio'],
            annual_expenses=params['annual_expenses'],
            returns_sequence=returns,
            start_age=params['start_age'],
            inflation_rate=params.get('inflation', 0),
            income_phases=params.get('income_phases'),
            windfalls=params.get('windfalls'),
            emergency_hustle=params.get('emergency_hustle'),
            spending_rules=params.get('spending_rules')
        )
        results.append(result)

    # Calculate summary stats (same as run_monte_carlo)
    survived_count = sum(1 for r in results if r.survived)
    success_rate = survived_count / num_simulations

    final_values = sorted([r.final_portfolio for r in results])
    median_final = final_values[len(final_values) // 2]

    failures = [r for r in results if not r.survived]
    ruin_ages = [r.ruin_age for r in failures]
    avg_ruin_age = sum(ruin_ages) / len(ruin_ages) if ruin_ages else None

    hustle_activations = sum(1 for r in results if r.hustle_activated)
    spending_reductions = sum(1 for r in results if r.spending_reduced)
    lean_mode_activations = sum(1 for r in results if r.spending_went_lean)

    # Classify outcomes using helper
    mortality_outcomes = _classify_mortality_outcomes(results, death_ages, mortality_enabled)

    return {
        "params": {
            "starting_portfolio": params['starting_portfolio'],
            "annual_expenses": params['annual_expenses'],
            "start_age": params['start_age'],
            "end_age": params['end_age'],
            "num_simulations": num_simulations,
            "inflation": params.get('inflation', 0),
            "income_phases": params.get('income_phases', []),
            "windfalls": params.get('windfalls', []),
            "emergency_hustle": params.get('emergency_hustle', {}),
            "spending_rules": params.get('spending_rules', {}),
            "mortality": mortality_config,
            "scenario_id": scenario_id
        },
        "percentiles": calculate_percentile_trajectories(results),
        "failures": get_failure_examples(results, max_examples=30),
        "close_calls": get_close_call_examples(results, threshold=300_000),
        "summary": {
            "success_rate": success_rate,
            "failure_count": len(failures),
            "median_final": median_final,
            "avg_ruin_age": avg_ruin_age,
            "hustle_activation_rate": hustle_activations / num_simulations,
            "spending_reduction_rate": spending_reductions / num_simulations,
            "lean_mode_rate": lean_mode_activations / num_simulations,
            "percentile_5_final": final_values[int(len(final_values) * 0.05)],
            "percentile_95_final": final_values[int(len(final_values) * 0.95)],
            "mortality_enabled": mortality_enabled,
            "health_class": health_class if mortality_enabled else None,
            "tech_scenario": tech_scenario if mortality_enabled else None,
            "survived_to_end": mortality_outcomes['survived_to_end'],
            "died_with_money": mortality_outcomes['died_with_money'],
            "ran_out_of_money": mortality_outcomes['ran_out_of_money'],
            "real_failure_rate": mortality_outcomes['real_failure_rate'],
            "avg_death_age": mortality_outcomes['avg_death_age'],
            "death_before_end_rate": mortality_outcomes['death_before_end_rate'],
            "theoretical_survival_to_end": survival_to_end_prob if mortality_enabled else 1.0,
            "life_expectancy": life_expectancy if mortality_enabled else None
        }
    }


def run_historical_sequence(params: dict) -> dict:
    """
    Run simulation against all historical market periods.

    Uses Shiller's historical data (1872-2022) to test the retirement plan
    against every possible starting year. This preserves sequence-of-returns
    risk and shows actual worst-case scenarios.

    Note: Historical returns are real (inflation-adjusted), so we set
    inflation_rate=0 in the simulation. Income phases and windfalls should
    be specified in today's dollars (real terms).

    Supports optional mortality modeling (same as Monte Carlo).
    """
    start_age = params['start_age']
    end_age = params['end_age']
    years = end_age - start_age
    historical_data = load_historical_returns()
    historical_years = historical_data['years']

    # Extract mortality config using helper
    mortality_enabled, health_class, tech_scenario = _extract_mortality_config(params)

    # Calculate theoretical survival stats
    survival_to_end_prob, life_expectancy = _calculate_theoretical_mortality_stats(
        start_age, end_age, health_class, tech_scenario, mortality_enabled
    )

    # Get all historical sequences (one per starting year)
    all_returns = historical_sequence_returns(years)

    # Run simulation for each historical period
    results = []
    death_ages = []
    for returns in all_returns:
        # Sample death age for this historical period (if mortality enabled)
        if mortality_enabled:
            death_age = sample_death_age(start_age, end_age, FINNISH_MALE_MORTALITY, health_class, tech_scenario)
        else:
            death_age = None
        death_ages.append(death_age)

        result = run_simulation(
            starting_portfolio=params['starting_portfolio'],
            annual_expenses=params['annual_expenses'],
            returns_sequence=returns,
            start_age=start_age,
            inflation_rate=0,  # Returns are already real (inflation-adjusted)
            income_phases=params.get('income_phases'),
            windfalls=params.get('windfalls'),
            emergency_hustle=params.get('emergency_hustle'),
            spending_rules=params.get('spending_rules')
        )
        results.append(result)

    # Calculate summary statistics
    survived_count = sum(1 for r in results if r.survived)
    success_rate = survived_count / len(results)

    final_values = sorted([r.final_portfolio for r in results])
    median_final = final_values[len(final_values) // 2]

    failures = [r for r in results if not r.survived]
    ruin_ages = [r.ruin_age for r in failures]
    avg_ruin_age = sum(ruin_ages) / len(ruin_ages) if ruin_ages else None

    # Classify outcomes using helper
    mortality_outcomes = _classify_mortality_outcomes(results, death_ages, mortality_enabled)

    # Map failures back to starting years
    failure_details = []
    for i, r in enumerate(results):
        if not r.survived:
            start_year = historical_years[i]
            failure_details.append({
                'start_year': start_year,
                'ruin_age': r.ruin_age,
                'trajectory': r.portfolio_values,
                'ages': r.ages,
                'hustle_activated': r.hustle_activated,
                'spending_reduced': r.spending_reduced
            })

    # Sort failures by start year
    failure_details = sorted(failure_details, key=lambda x: x['start_year'])

    # Track activation rates
    hustle_activations = sum(1 for r in results if r.hustle_activated)
    spending_reductions = sum(1 for r in results if r.spending_reduced)

    return {
        'method': 'historical_sequence',
        'num_periods': len(results),
        'data_range': f"{historical_years[0]}-{historical_years[-1]}",
        'params': {
            'starting_portfolio': params['starting_portfolio'],
            'annual_expenses': params['annual_expenses'],
            'start_age': start_age,
            'end_age': end_age,
            'years': years,
            'income_phases': params.get('income_phases', []),
            'windfalls': params.get('windfalls', []),
            'emergency_hustle': params.get('emergency_hustle', {}),
            'spending_rules': params.get('spending_rules', {}),
            'mortality': params.get('mortality', {})
        },
        'summary': {
            'success_rate': success_rate,
            'survived_count': survived_count,
            'failure_count': len(failures),
            'median_final': median_final,
            'avg_ruin_age': avg_ruin_age,
            'percentile_5_final': final_values[int(len(final_values) * 0.05)],
            'percentile_95_final': final_values[int(len(final_values) * 0.95)],
            'hustle_activation_rate': hustle_activations / len(results),
            'spending_reduction_rate': spending_reductions / len(results),
            # Mortality stats
            'mortality_enabled': mortality_enabled,
            'health_class': health_class if mortality_enabled else None,
            'tech_scenario': tech_scenario if mortality_enabled else None,
            'survived_to_end': mortality_outcomes['survived_to_end'],
            'died_with_money': mortality_outcomes['died_with_money'],
            'ran_out_of_money': mortality_outcomes['ran_out_of_money'],
            'real_failure_rate': mortality_outcomes['real_failure_rate'],
            'avg_death_age': mortality_outcomes['avg_death_age'],
            'death_before_end_rate': mortality_outcomes['death_before_end_rate'],
            'theoretical_survival_to_end': survival_to_end_prob,
            'life_expectancy': life_expectancy
        },
        'failures': failure_details[:30],  # Limit to 30 examples
        'percentiles': calculate_percentile_trajectories(results),
        'close_calls': get_close_call_examples(results, threshold=300_000)
    }


def run_and_export(
    params: dict,
    num_simulations: int = 1000,
    output_path: str = "visualization/data.json"
):
    """Run simulation and export results to JSON file."""
    print(f"Running {num_simulations} simulations...")

    mortality_config = params.get('mortality', {})
    mortality_enabled = mortality_config.get('enabled', False)
    health_class = mortality_config.get('health_class', 'average')
    tech_scenario = mortality_config.get('tech_scenario', 'moderate')
    end_age = params['end_age']

    if mortality_enabled:
        print(f"  Mortality modeling: ON (health: {health_class}, tech: {tech_scenario})")
    else:
        print("  Mortality modeling: OFF")

    result = run_monte_carlo(params, num_simulations)

    output_file = Path(__file__).parent / output_path
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    s = result['summary']
    print(f"\nExported to {output_file}")
    print(f"\n=== Results (ignoring mortality) ===")
    print(f"Success rate: {s['success_rate']:.1%}")
    print(f"Failures: {s['failure_count']}")
    print(f"Median final portfolio: €{s['median_final']:,.0f}")

    if mortality_enabled:
        print(f"\n=== Results (with mortality) ===")
        print(f"Survived to {end_age} with money: {s['survived_to_end']} ({s['survived_to_end']/num_simulations:.1%})")
        print(f"Died with money (before {end_age}): {s['died_with_money']} ({s['died_with_money']/num_simulations:.1%})")
        print(f"Ran out of money while alive: {s['ran_out_of_money']} ({s['ran_out_of_money']/num_simulations:.1%})")
        print(f"\nREAL FAILURE RATE: {s['real_failure_rate']:.2%}")
        if s['avg_death_age']:
            print(f"Average death age (in deaths): {s['avg_death_age']:.1f}")

    return result


if __name__ == "__main__":
    run_and_export(DEFAULT_PARAMS, num_simulations=1000)
