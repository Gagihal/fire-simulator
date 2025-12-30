#!/usr/bin/env python3
"""
Export FIRE simulation data to JSON for visualization.

Runs Monte Carlo simulation and exports:
- Percentile trajectories (5th, 10th, 15th, 25th, 50th, 75th, 95th)
- Failed simulation examples
- Summary statistics
"""

import json
import random
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from config import DEFAULT_PARAMS, FINNISH_MALE_MORTALITY
from fire_simulator import run_simulation, SimulationResult
from scenarios import monte_carlo_returns


# =============================================================================
# MORTALITY MODELING
# =============================================================================

def sample_death_age(
    start_age: int,
    end_age: int,
    mortality_table: Dict[int, float],
    healthy_factor: float = 1.0
) -> Optional[int]:
    """
    Sample a death age using mortality table probabilities.

    Args:
        start_age: Age at start of simulation
        end_age: Maximum age to simulate
        mortality_table: Dict of age -> qx (death probability per 1,000)
        healthy_factor: Multiplier for qx (< 1.0 = healthier than average)

    Returns:
        Age of death, or None if survived to end_age
    """
    for age in range(start_age, end_age + 1):
        # Get qx for this age (probability of dying within the year, per 1,000)
        qx = mortality_table.get(age, mortality_table.get(end_age, 500))

        # Apply healthy lifestyle adjustment
        adjusted_qx = qx * healthy_factor

        # Convert to probability (qx is per 1,000)
        death_prob = adjusted_qx / 1000

        # Roll the dice
        if random.random() < death_prob:
            return age

    return None  # Survived to end_age


def calculate_survival_probability(
    start_age: int,
    end_age: int,
    mortality_table: Dict[int, float],
    healthy_factor: float = 1.0
) -> float:
    """
    Calculate probability of surviving from start_age to end_age.

    This is the cumulative survival probability:
    P(survive to end) = Product of (1 - qx/1000) for each year
    """
    survival_prob = 1.0
    for age in range(start_age, end_age + 1):
        qx = mortality_table.get(age, mortality_table.get(end_age, 500))
        adjusted_qx = qx * healthy_factor
        death_prob = adjusted_qx / 1000
        survival_prob *= (1 - death_prob)
    return survival_prob


def get_life_expectancy(
    start_age: int,
    mortality_table: Dict[int, float],
    healthy_factor: float = 1.0,
    max_age: int = 110
) -> float:
    """
    Calculate expected remaining years of life from start_age.
    """
    survival_prob = 1.0
    expected_years = 0.0

    for age in range(start_age, max_age + 1):
        qx = mortality_table.get(age, mortality_table.get(max(mortality_table.keys()), 500))
        adjusted_qx = qx * healthy_factor
        death_prob = adjusted_qx / 1000

        # Expected years = sum of P(alive at each age)
        expected_years += survival_prob

        survival_prob *= (1 - death_prob)

    return expected_years


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


def run_and_export(
    params: dict,
    num_simulations: int = 1000,
    output_path: str = "visualization/data.json"
):
    """
    Run Monte Carlo simulation and export results to JSON.

    With mortality modeling enabled, each simulation gets a randomly sampled
    death age. Outcomes are categorized as:
    - survived_to_end: Made it to end_age with money
    - died_with_money: Died naturally before running out
    - ran_out_of_money: Portfolio hit zero while still alive (true failure)
    """
    print(f"Running {num_simulations} simulations...")

    years = params['end_age'] - params['start_age']
    start_age = params['start_age']
    end_age = params['end_age']

    # Mortality settings
    mortality_config = params.get('mortality', {})
    mortality_enabled = mortality_config.get('enabled', False)
    healthy_factor = mortality_config.get('healthy_lifestyle_factor', 1.0)

    if mortality_enabled:
        print(f"  Mortality modeling: ON (healthy factor: {healthy_factor})")
        # Calculate theoretical survival probability
        survival_to_end = calculate_survival_probability(
            start_age, end_age, FINNISH_MALE_MORTALITY, healthy_factor
        )
        life_expectancy = get_life_expectancy(
            start_age, FINNISH_MALE_MORTALITY, healthy_factor
        )
        print(f"  P(survive to {end_age}): {survival_to_end:.1%}")
        print(f"  Life expectancy from {start_age}: {life_expectancy:.1f} years (age {start_age + life_expectancy:.0f})")
    else:
        print("  Mortality modeling: OFF")
        survival_to_end = 1.0
        life_expectancy = end_age - start_age

    # Generate return sequences
    all_returns = monte_carlo_returns(
        years,
        num_simulations,
        mean=params['expected_return'],
        std=params['volatility']
    )

    # Run simulations
    results = []
    death_ages = []  # Track sampled death ages for each simulation

    for i, returns in enumerate(all_returns):
        if (i + 1) % 100 == 0:
            print(f"  Completed {i + 1}/{num_simulations}")

        # Sample death age for this simulation
        if mortality_enabled:
            death_age = sample_death_age(
                start_age, end_age, FINNISH_MALE_MORTALITY, healthy_factor
            )
        else:
            death_age = None  # Lives to end_age

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

    print("Calculating statistics...")

    # Calculate summary stats (without mortality)
    survived_count = sum(1 for r in results if r.survived)
    success_rate = survived_count / num_simulations

    final_values = sorted([r.final_portfolio for r in results])
    median_final = final_values[len(final_values) // 2]

    failures = [r for r in results if not r.survived]
    ruin_ages = [r.ruin_age for r in failures]
    avg_ruin_age = sum(ruin_ages) / len(ruin_ages) if ruin_ages else None

    hustle_activations = sum(1 for r in results if r.hustle_activated)

    # Spending rules stats
    spending_reductions = sum(1 for r in results if r.spending_reduced)
    lean_mode_activations = sum(1 for r in results if r.spending_went_lean)

    # Mortality-adjusted stats
    if mortality_enabled:
        # Categorize outcomes with mortality
        survived_to_end = 0  # Made it to end_age with money
        died_with_money = 0  # Died before running out
        ran_out_of_money = 0  # True failure: ran out while alive

        for i, (result, death_age) in enumerate(zip(results, death_ages)):
            if result.survived:
                # Portfolio lasted to end_age
                if death_age is None:
                    survived_to_end += 1  # Lived AND had money
                else:
                    died_with_money += 1  # Died before end_age (with money)
            else:
                # Portfolio ran out
                ruin_age = result.ruin_age
                if death_age is not None and death_age < ruin_age:
                    died_with_money += 1  # Died before going broke
                else:
                    ran_out_of_money += 1  # True failure

        # Real failure rate: only count those who ran out while alive
        real_failure_rate = ran_out_of_money / num_simulations

        # Distribution of death ages
        actual_deaths = [d for d in death_ages if d is not None]
        avg_death_age = sum(actual_deaths) / len(actual_deaths) if actual_deaths else None
        death_before_end_rate = len(actual_deaths) / num_simulations
    else:
        survived_to_end = survived_count
        died_with_money = 0
        ran_out_of_money = len(failures)
        real_failure_rate = len(failures) / num_simulations
        avg_death_age = None
        death_before_end_rate = 0.0

    # Build export data
    export_data = {
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
            # Original stats (ignoring mortality)
            "success_rate": success_rate,
            "failure_count": len(failures),
            "median_final": median_final,
            "avg_ruin_age": avg_ruin_age,
            "hustle_activation_rate": hustle_activations / num_simulations,
            "spending_reduction_rate": spending_reductions / num_simulations,
            "lean_mode_rate": lean_mode_activations / num_simulations,
            "percentile_5_final": final_values[int(len(final_values) * 0.05)],
            "percentile_95_final": final_values[int(len(final_values) * 0.95)],
            # Mortality-adjusted stats
            "mortality_enabled": mortality_enabled,
            "healthy_lifestyle_factor": healthy_factor if mortality_enabled else None,
            "survived_to_end": survived_to_end,
            "died_with_money": died_with_money,
            "ran_out_of_money": ran_out_of_money,
            "real_failure_rate": real_failure_rate,
            "avg_death_age": avg_death_age,
            "death_before_end_rate": death_before_end_rate,
            "theoretical_survival_to_end": survival_to_end if mortality_enabled else 1.0,
            "life_expectancy": life_expectancy if mortality_enabled else None
        }
    }

    # Write JSON
    output_file = Path(__file__).parent / output_path
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"\nExported to {output_file}")
    print(f"\n=== Results (ignoring mortality) ===")
    print(f"Success rate: {success_rate:.1%}")
    print(f"Failures: {len(failures)}")
    print(f"Median final portfolio: €{median_final:,.0f}")

    if mortality_enabled:
        print(f"\n=== Results (with mortality) ===")
        print(f"Survived to {end_age} with money: {survived_to_end} ({survived_to_end/num_simulations:.1%})")
        print(f"Died with money (before {end_age}): {died_with_money} ({died_with_money/num_simulations:.1%})")
        print(f"Ran out of money while alive: {ran_out_of_money} ({ran_out_of_money/num_simulations:.1%})")
        print(f"\nREAL FAILURE RATE: {real_failure_rate:.2%}")
        if avg_death_age:
            print(f"Average death age (in deaths): {avg_death_age:.1f}")

    return export_data


if __name__ == "__main__":
    run_and_export(DEFAULT_PARAMS, num_simulations=1000)
