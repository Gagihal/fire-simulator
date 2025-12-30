#!/usr/bin/env python3
"""
FIRE Simulation Runner

This is the main entry point that ties everything together:
- Loads your parameters from config.py
- Runs multiple scenarios from scenarios.py
- Displays results and generates charts

Now supports age-dependent income and multiple windfall events.

Run with: python run_simulation.py
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass

# Import our modules
from config import DEFAULT_PARAMS
from fire_simulator import (
    run_simulation, SimulationResult, format_currency,
    calculate_withdrawal_rate, get_income_for_age
)
from scenarios import SCENARIOS, monte_carlo_returns


# =============================================================================
# MULTI-SCENARIO ANALYSIS
# =============================================================================

def run_all_scenarios(params: dict) -> Dict[str, SimulationResult]:
    """
    Run all predefined scenarios and return results.
    """
    years = params['end_age'] - params['start_age']
    results = {}

    for key, scenario in SCENARIOS.items():
        returns = scenario['generator'](years)
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
        results[key] = result

    return results


def print_scenario_comparison(results: Dict[str, SimulationResult], params: dict):
    """Print a summary table comparing all scenarios."""
    print("\n" + "=" * 60)
    print("SCENARIO COMPARISON")
    print("=" * 60)
    print(f"\n{'Scenario':<30} {'Final Portfolio':>15} {'Survived':>10}")
    print("-" * 60)

    for key, result in results.items():
        scenario_name = SCENARIOS[key]['name']
        final = format_currency(result.final_portfolio)
        survived = "Yes" if result.survived else f"No (age {result.ruin_age})"
        print(f"{scenario_name:<30} {final:>15} {survived:>10}")

    print("-" * 60)


# =============================================================================
# MONTE CARLO ANALYSIS
# =============================================================================

@dataclass
class MonteCarloSummary:
    """Summary statistics from Monte Carlo simulation."""
    success_rate: float
    median_final: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    ruin_ages: List[int]


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile from sorted data."""
    idx = int(len(data) * p / 100)
    return data[min(idx, len(data) - 1)]


def run_monte_carlo(params: dict, num_simulations: int = 1000,
                    all_returns: List[List[float]] = None) -> Tuple[List[SimulationResult], MonteCarloSummary]:
    """Run Monte Carlo simulation with many random futures.

    Args:
        params: Simulation parameters
        num_simulations: Number of simulations (ignored if all_returns provided)
        all_returns: Optional pre-generated return sequences for A/B comparison
    """
    if all_returns is None:
        years = params['end_age'] - params['start_age']
        all_returns = monte_carlo_returns(
            years, num_simulations,
            mean=params['expected_return'],
            std=params['volatility']
        )

    all_results = []
    for returns in all_returns:
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
        all_results.append(result)

    final_values = sorted([r.final_portfolio for r in all_results])
    survived_count = sum(1 for r in all_results if r.survived)
    ruin_ages = [r.ruin_age for r in all_results if r.ruin_age is not None]

    summary = MonteCarloSummary(
        success_rate=survived_count / len(all_returns),
        median_final=percentile(final_values, 50),
        percentile_5=percentile(final_values, 5),
        percentile_25=percentile(final_values, 25),
        percentile_75=percentile(final_values, 75),
        percentile_95=percentile(final_values, 95),
        ruin_ages=ruin_ages
    )

    return all_results, summary


def print_monte_carlo_summary(summary: MonteCarloSummary, num_simulations: int):
    """Print Monte Carlo results."""
    print("\n" + "=" * 60)
    print(f"MONTE CARLO SIMULATION ({num_simulations:,} runs)")
    print("=" * 60)

    print(f"\nSuccess Rate: {summary.success_rate:.1%}")
    if summary.success_rate < 1.0:
        print(f"  ({(1-summary.success_rate)*100:.1f}% of simulations ran out of money)")
        if summary.ruin_ages:
            avg_ruin = sum(summary.ruin_ages) / len(summary.ruin_ages)
            print(f"  Average ruin age: {avg_ruin:.0f}")

    print(f"\nFinal Portfolio Distribution (at age 95):")
    print(f"  5th percentile:  {format_currency(summary.percentile_5):>15}  (pessimistic)")
    print(f"  25th percentile: {format_currency(summary.percentile_25):>15}")
    print(f"  50th percentile: {format_currency(summary.median_final):>15}  (median)")
    print(f"  75th percentile: {format_currency(summary.percentile_75):>15}")
    print(f"  95th percentile: {format_currency(summary.percentile_95):>15}  (optimistic)")


# =============================================================================
# BULLETPROOF FLOOR FINDER
# =============================================================================

def find_bulletproof_floor(params: dict, target_success_rate: float = 0.95,
                           num_simulations: int = 500) -> float:
    """Find minimum starting portfolio for target success rate."""
    low = 100_000
    high = params['starting_portfolio'] * 2

    while high - low > 10_000:
        mid = (low + high) / 2
        test_params = params.copy()
        test_params['starting_portfolio'] = mid

        _, summary = run_monte_carlo(test_params, num_simulations)

        if summary.success_rate >= target_success_rate:
            high = mid
        else:
            low = mid

    return high


def print_bulletproof_analysis(params: dict, floor: float):
    """Print bulletproof floor analysis."""
    buffer = params['starting_portfolio'] - floor

    print("\n" + "=" * 60)
    print("BULLETPROOF FLOOR ANALYSIS (95% success target)")
    print("=" * 60)

    print(f"\nMinimum safe portfolio: {format_currency(floor)}")
    print(f"Your planned portfolio: {format_currency(params['starting_portfolio'])}")
    print(f"Your buffer:            {format_currency(buffer)}")
    if floor > 0:
        print(f"Buffer percentage:      {buffer/floor*100:.0f}% above minimum")

    if buffer > 0:
        print(f"\nThis buffer of {format_currency(buffer)} represents:")
        print(f"  - Extra security margin for bad luck")
        print(f"  - Potential for impact investing / giving")
        print(f"  - Flexibility for lifestyle changes")


# =============================================================================
# WINDFALL COMPARISON
# =============================================================================

def compare_with_windfalls(params: dict, num_simulations: int = 1000):
    """Compare outcomes with and without windfalls using identical market conditions."""
    years = params['end_age'] - params['start_age']

    # Generate return sequences ONCE
    all_returns = monte_carlo_returns(
        years, num_simulations,
        mean=params['expected_return'],
        std=params['volatility']
    )

    # Without windfalls
    no_windfall_params = params.copy()
    no_windfall_params['windfalls'] = []
    _, summary_without = run_monte_carlo(no_windfall_params, all_returns=all_returns)

    # With windfalls
    _, summary_with = run_monte_carlo(params, all_returns=all_returns)

    print("\n" + "=" * 60)
    print("WINDFALL COMPARISON")
    print("=" * 60)

    windfalls = params.get('windfalls', [])
    total_windfalls = sum(w['amount'] for w in windfalls)

    print(f"\nWindfall Events:")
    for w in windfalls:
        print(f"  Age {w['age']}: {format_currency(w['amount'])} ({w['name']})")
    print(f"  Total: {format_currency(total_windfalls)}")

    print(f"\n{'Metric':<25} {'Without':>15} {'With':>15}")
    print("-" * 55)
    print(f"{'Success rate':<25} {summary_without.success_rate:>14.1%} {summary_with.success_rate:>14.1%}")
    print(f"{'Median final portfolio':<25} {format_currency(summary_without.median_final):>15} {format_currency(summary_with.median_final):>15}")


# =============================================================================
# EMERGENCY HUSTLE COMPARISON
# =============================================================================

def compare_with_hustle(params: dict, num_simulations: int = 1000):
    """Compare outcomes with and without emergency hustle using identical market conditions."""
    years = params['end_age'] - params['start_age']

    # Generate return sequences ONCE
    all_returns = monte_carlo_returns(
        years,
        num_simulations,
        mean=params['expected_return'],
        std=params['volatility']
    )

    # Without hustle
    no_hustle_params = params.copy()
    no_hustle_params['emergency_hustle'] = {'enabled': False}
    results_without, summary_without = run_monte_carlo(no_hustle_params, all_returns=all_returns)

    # With hustle
    results_with, summary_with = run_monte_carlo(params, all_returns=all_returns)

    # Calculate hustle activation stats
    hustle_activations = sum(1 for r in results_with if r.hustle_activated)
    activation_rate = hustle_activations / num_simulations

    # Get average activation age
    activation_ages = [r.hustle_activation_age for r in results_with if r.hustle_activation_age is not None]
    avg_activation_age = sum(activation_ages) / len(activation_ages) if activation_ages else 0

    # Print comparison
    hustle = params.get('emergency_hustle', {})
    threshold_value = params['starting_portfolio'] * hustle.get('portfolio_threshold', 0.70)

    print("\n" + "=" * 60)
    print("EMERGENCY HUSTLE ANALYSIS")
    print("=" * 60)

    print(f"\nHustle Settings:")
    print(f"  Trigger: Portfolio < {hustle.get('portfolio_threshold', 0.70):.0%} of start ({format_currency(threshold_value)})")
    print(f"  Window:  Age {params['start_age']} to {hustle.get('trigger_age_max', params['start_age'] + 5)}")
    print(f"  Response: {format_currency(hustle.get('extra_income', 40000))}/year for {hustle.get('duration', 3)} years")

    print(f"\n{'Metric':<25} {'Without Hustle':>15} {'With Hustle':>15}")
    print("-" * 55)
    print(f"{'Success rate':<25} {summary_without.success_rate:>14.1%} {summary_with.success_rate:>14.1%}")
    print(f"{'Median final portfolio':<25} {format_currency(summary_without.median_final):>15} {format_currency(summary_with.median_final):>15}")
    print(f"{'5th percentile':<25} {format_currency(summary_without.percentile_5):>15} {format_currency(summary_with.percentile_5):>15}")

    improvement = summary_with.success_rate - summary_without.success_rate
    print(f"\nHustle activation rate:   {activation_rate:.1%} of simulations")
    if activation_ages:
        print(f"Average activation age:   {avg_activation_age:.1f}")
    print(f"\nSuccess rate improvement: {improvement:+.1%} percentage points")

    if improvement > 0:
        print(f"\nThe emergency hustle safety net improves success rate by {improvement:.1%}.")
    else:
        print(f"\nThe hustle didn't trigger often enough to significantly improve outcomes.")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the full analysis."""
    params = DEFAULT_PARAMS

    # Header
    print("\n" + "=" * 60)
    print("FIRE SIMULATION RESULTS")
    print("=" * 60)

    # Your situation
    print(f"\nStarting Portfolio: {format_currency(params['starting_portfolio'])}")
    print(f"Annual Expenses:    {format_currency(params['annual_expenses'])}")

    # Income phases
    income_phases = params.get('income_phases', [])
    if income_phases:
        print("\nIncome Phases:")
        for phase in income_phases:
            net = params['annual_expenses'] - phase['amount']
            print(f"  Age {phase['start_age']}-{phase['end_age']}: {format_currency(phase['amount'])}/yr ({phase['name']}) -> net withdrawal {format_currency(net)}")

    # Windfalls
    windfalls = params.get('windfalls', [])
    if windfalls:
        print("\nWindfall Events:")
        for w in windfalls:
            print(f"  Age {w['age']}: {format_currency(w['amount'])} ({w['name']})")

    # Emergency hustle
    emergency_hustle = params.get('emergency_hustle', {})
    if emergency_hustle.get('enabled', False):
        threshold = emergency_hustle.get('portfolio_threshold', 0.70)
        threshold_value = params['starting_portfolio'] * threshold
        print(f"\nEmergency Hustle:")
        print(f"  If portfolio < {threshold:.0%} of start ({format_currency(threshold_value)}) by age {emergency_hustle.get('trigger_age_max', 52)}")
        print(f"  -> Work {format_currency(emergency_hustle.get('extra_income', 40000))}/yr for {emergency_hustle.get('duration', 3)} years")

    # Initial withdrawal rate (using first income phase)
    initial_income = income_phases[0]['amount'] if income_phases else 0
    withdrawal_rate = calculate_withdrawal_rate(
        params['starting_portfolio'],
        params['annual_expenses'],
        initial_income
    )
    print(f"\nInitial Withdrawal Rate: {withdrawal_rate:.1%}")
    print(f"Time Horizon:            Age {params['start_age']} to {params['end_age']} ({params['end_age']-params['start_age']} years)")
    print(f"Expected Return:         {params['expected_return']:.0%}")
    print(f"Inflation:               {params['inflation']:.0%}")
    print(f"Volatility:              {params['volatility']:.0%}")

    # Run scenarios
    print("\nRunning scenarios...")
    results = run_all_scenarios(params)
    print_scenario_comparison(results, params)

    # Monte Carlo
    print("\nRunning Monte Carlo simulation (1000 runs)...")
    _, mc_summary = run_monte_carlo(params, 1000)
    print_monte_carlo_summary(mc_summary, 1000)

    # Bulletproof floor
    print("\nCalculating bulletproof floor...")
    floor = find_bulletproof_floor(params, 0.95, 500)
    print_bulletproof_analysis(params, floor)

    # Windfall comparison
    if windfalls:
        print("\nComparing with/without windfalls...")
        compare_with_windfalls(params, 500)

    # Emergency hustle comparison
    emergency_hustle = params.get('emergency_hustle', {})
    if emergency_hustle.get('enabled', False):
        print("\nComparing with/without emergency hustle...")
        compare_with_hustle(params, 500)

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
