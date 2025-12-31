#!/usr/bin/env python3
"""
Flask API for FIRE Simulator

Provides endpoints to run Monte Carlo simulations with custom parameters.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import copy

from fire_simulator import run_simulation
from scenarios import monte_carlo_returns
from config import DEFAULT_PARAMS, FINNISH_MALE_MORTALITY
from export_data import (
    sample_death_age, calculate_survival_probability,
    get_life_expectancy, calculate_percentile_trajectories,
    get_failure_examples, get_close_call_examples
)

app = Flask(__name__, static_folder='visualization')
CORS(app)


def run_simulation_with_params(params: dict, num_simulations: int = 1000) -> dict:
    """
    Run Monte Carlo simulation and return results in JSON format.

    This is essentially a refactored version of export_data.run_and_export()
    that returns data instead of writing to a file.
    """
    years = params['end_age'] - params['start_age']
    start_age = params['start_age']
    end_age = params['end_age']

    # Mortality settings
    mortality_config = params.get('mortality', {})
    mortality_enabled = mortality_config.get('enabled', False)
    healthy_factor = mortality_config.get('healthy_lifestyle_factor', 1.0)

    if mortality_enabled:
        survival_to_end = calculate_survival_probability(
            start_age, end_age, FINNISH_MALE_MORTALITY, healthy_factor
        )
        life_expectancy = get_life_expectancy(
            start_age, FINNISH_MALE_MORTALITY, healthy_factor
        )
    else:
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
    death_ages = []

    for returns in all_returns:
        if mortality_enabled:
            death_age = sample_death_age(
                start_age, end_age, FINNISH_MALE_MORTALITY, healthy_factor
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

    # Mortality-adjusted stats
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
                    died_with_money += 1
                else:
                    ran_out_of_money += 1

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

    # Build response
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
            "healthy_lifestyle_factor": healthy_factor if mortality_enabled else None,
            "survived_to_end": survived_to_end_count,
            "died_with_money": died_with_money,
            "ran_out_of_money": ran_out_of_money,
            "real_failure_rate": real_failure_rate,
            "avg_death_age": avg_death_age,
            "death_before_end_rate": death_before_end_rate,
            "theoretical_survival_to_end": survival_to_end if mortality_enabled else 1.0,
            "life_expectancy": life_expectancy if mortality_enabled else None
        }
    }


@app.route('/api/simulate', methods=['POST'])
def simulate():
    """
    Run a simulation with custom parameters.

    Accepts JSON body with optional overrides for any DEFAULT_PARAMS values.
    """
    try:
        user_params = request.get_json() or {}

        # Start with defaults
        params = copy.deepcopy(DEFAULT_PARAMS)

        # Override with user values - Portfolio & Expenses
        if 'starting_portfolio' in user_params:
            params['starting_portfolio'] = int(user_params['starting_portfolio'])
        if 'annual_expenses' in user_params:
            params['annual_expenses'] = int(user_params['annual_expenses'])

        # Time horizon
        if 'start_age' in user_params:
            params['start_age'] = int(user_params['start_age'])
        if 'end_age' in user_params:
            params['end_age'] = int(user_params['end_age'])

        # Investment assumptions
        if 'expected_return' in user_params:
            params['expected_return'] = float(user_params['expected_return'])
        if 'inflation' in user_params:
            params['inflation'] = float(user_params['inflation'])
        if 'volatility' in user_params:
            params['volatility'] = float(user_params['volatility'])

        # Income phases
        if 'income_phases' in user_params:
            params['income_phases'] = user_params['income_phases']

        # Windfalls
        if 'windfalls' in user_params:
            params['windfalls'] = user_params['windfalls']

        # Emergency hustle - merge with defaults
        if 'emergency_hustle' in user_params:
            for key, value in user_params['emergency_hustle'].items():
                params['emergency_hustle'][key] = value

        # Spending rules - merge with defaults
        if 'spending_rules' in user_params:
            for key, value in user_params['spending_rules'].items():
                params['spending_rules'][key] = value

        # Mortality - merge with defaults
        if 'mortality' in user_params:
            if 'mortality' not in params:
                params['mortality'] = {}
            for key, value in user_params['mortality'].items():
                params['mortality'][key] = value

        # Get simulation count (default 1000, max 100000)
        num_simulations = min(int(user_params.get('num_simulations', 1000)), 100000)

        # Run simulation
        result = run_simulation_with_params(params, num_simulations)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/defaults', methods=['GET'])
def get_defaults():
    """Return default parameters so frontend can initialize inputs."""
    return jsonify(DEFAULT_PARAMS)


@app.route('/')
def index():
    """Serve the interactive HTML page."""
    return send_from_directory('visualization', 'interactive.html')


@app.route('/<path:path>')
def static_files(path):
    """Serve static files from visualization folder."""
    return send_from_directory('visualization', path)


if __name__ == '__main__':
    print("Starting FIRE Simulator API on http://localhost:5000")
    app.run(debug=True, port=5000)
