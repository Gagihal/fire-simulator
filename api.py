#!/usr/bin/env python3
"""
Flask API for FIRE Simulator

Provides endpoints to run Monte Carlo simulations with custom parameters.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import copy

import time

from config import DEFAULT_PARAMS, FINNISH_MALE_MORTALITY
from export_data import (
    run_monte_carlo, run_historical_sequence, find_required_portfolio,
    calculate_legacy_tradeoff, calculate_dynamic_end_age,
    run_simulation_with_custom_returns
)
from stress_scenarios import (
    STRESS_SCENARIOS, generate_scenario_returns, get_all_scenario_ids,
    get_scenario_metadata
)

app = Flask(__name__, static_folder='visualization')
CORS(app)


# =============================================================================
# HELPER FUNCTIONS - Reduce code duplication in API endpoints
# =============================================================================

def _merge_user_params(user_params: dict, include_market_params: bool = True) -> dict:
    """
    Merge user parameters with defaults.

    Args:
        user_params: Parameters from API request
        include_market_params: Whether to include expected_return, inflation, volatility
                              (False for historical endpoints which use actual returns)

    Returns:
        Merged parameters dict
    """
    params = copy.deepcopy(DEFAULT_PARAMS)

    # Core parameters
    if 'starting_portfolio' in user_params:
        params['starting_portfolio'] = int(user_params['starting_portfolio'])
    if 'annual_expenses' in user_params:
        params['annual_expenses'] = int(user_params['annual_expenses'])
    if 'start_age' in user_params:
        params['start_age'] = int(user_params['start_age'])
    if 'end_age' in user_params:
        params['end_age'] = int(user_params['end_age'])

    # Market parameters (only for Monte Carlo, not historical)
    if include_market_params:
        if 'expected_return' in user_params:
            params['expected_return'] = float(user_params['expected_return'])
        if 'inflation' in user_params:
            params['inflation'] = float(user_params['inflation'])
        if 'volatility' in user_params:
            params['volatility'] = float(user_params['volatility'])

    # List parameters (replace entirely)
    if 'income_phases' in user_params:
        params['income_phases'] = user_params['income_phases']
    if 'windfalls' in user_params:
        params['windfalls'] = user_params['windfalls']

    # Nested configs (merge keys)
    if 'emergency_hustle' in user_params:
        for key, value in user_params['emergency_hustle'].items():
            params['emergency_hustle'][key] = value
    if 'spending_rules' in user_params:
        for key, value in user_params['spending_rules'].items():
            params['spending_rules'][key] = value
    if 'mortality' in user_params:
        if 'mortality' not in params:
            params['mortality'] = {}
        for key, value in user_params['mortality'].items():
            params['mortality'][key] = value

    return params


def _apply_dynamic_end_age(params: dict, user_params: dict) -> dict:
    """
    Calculate and apply dynamic end_age when mortality is enabled and no explicit end_age given.

    When mortality modeling is enabled, we calculate the simulation endpoint based on
    when survival probability drops below 1%. This replaces the need for users to
    guess an appropriate end_age.

    Args:
        params: Merged parameters dict
        user_params: Original user parameters (to check if end_age was explicitly set)

    Returns:
        Updated params with dynamic end_age info added
    """
    mortality_config = params.get('mortality', {})
    mortality_enabled = mortality_config.get('enabled', False)

    # Only calculate dynamic end_age if:
    # 1. Mortality is enabled
    # 2. User did NOT explicitly set end_age
    if mortality_enabled and 'end_age' not in user_params:
        health_class = mortality_config.get('health_class', 'average')
        tech_scenario = mortality_config.get('tech_scenario', 'moderate')
        start_age = params['start_age']

        # Calculate dynamic end age
        dynamic_info = calculate_dynamic_end_age(
            start_age=start_age,
            mortality_table=FINNISH_MALE_MORTALITY,
            health_class=health_class,
            tech_scenario=tech_scenario,
            survival_threshold=0.01,  # 1% survival threshold
            hard_cap=110
        )

        # Update end_age with calculated value
        params['end_age'] = dynamic_info['end_age']

        # Store the dynamic calculation info for the response
        params['_dynamic_end_age_info'] = dynamic_info

    return params


@app.route('/api/simulate', methods=['POST'])
def simulate():
    """Run a simulation with custom parameters."""
    try:
        user_params = request.get_json() or {}
        params = _merge_user_params(user_params, include_market_params=True)
        params = _apply_dynamic_end_age(params, user_params)

        num_simulations = min(int(user_params.get('num_simulations', 1000)), 100000)
        result = run_monte_carlo(params, num_simulations)

        # Add dynamic end_age info to response if calculated
        if '_dynamic_end_age_info' in params:
            result['dynamic_end_age'] = params['_dynamic_end_age_info']

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/fire-assessment', methods=['POST'])
def fire_assessment():
    """
    FIRE assessment with projection: when will I reach FIRE?

    Takes current situation (age, portfolio, income, expenses) and projects
    when portfolio will be large enough to sustain expenses at target certainty.
    Post-FIRE income (pensions, part-time work, rentals) reduces the required portfolio.
    """
    try:
        user_params = request.get_json() or {}

        current_age = int(user_params.get('current_age', 40))
        portfolio = int(user_params.get('portfolio', 0))
        income = int(user_params.get('annual_income', 0))
        expenses = int(user_params.get('annual_expenses', 30000))
        post_fire_income = int(user_params.get('post_fire_income', 0))
        target_certainty = float(user_params.get('target_certainty', 0.95))
        expected_return = float(user_params.get('expected_return', 0.06))
        inflation = float(user_params.get('inflation', 0.02))
        volatility = float(user_params.get('volatility', 0.15))
        end_age = int(user_params.get('end_age', 95))

        # Annual savings = income - expenses
        annual_savings = income - expenses

        # Build params for FIRE assessment
        # Post-FIRE income is modeled as a permanent income phase from start_age to end_age
        def build_sim_params(start_age, start_portfolio):
            income_phases = []
            if post_fire_income > 0:
                income_phases = [{
                    'name': 'Post-FIRE income',
                    'start_age': start_age,
                    'end_age': end_age,
                    'amount': post_fire_income
                }]
            return {
                'starting_portfolio': start_portfolio,
                'annual_expenses': expenses,
                'start_age': start_age,
                'end_age': end_age,
                'expected_return': expected_return,
                'inflation': inflation,
                'volatility': volatility,
                'income_phases': income_phases,
                'windfalls': [],
                'emergency_hustle': {'enabled': False},
                'spending_rules': {'enabled': False},
                'mortality': {'enabled': False}
            }

        # Check if already FIRE with current portfolio
        sim_params = build_sim_params(current_age, portfolio)
        result = run_monte_carlo(sim_params, num_simulations=1000)
        success_rate = result['summary']['success_rate']
        fire_achieved = success_rate >= target_certainty

        response = {
            'fire_achieved': fire_achieved,
            'current_success_probability': success_rate,
            'target_certainty': target_certainty,
            'current_age': current_age,
            'current_portfolio': portfolio,
            'annual_income': income,
            'annual_expenses': expenses,
            'annual_savings': annual_savings,
            'post_fire_income': post_fire_income,
            'median_final': result['summary']['median_final'],
            'percentile_5_final': result['summary']['percentile_5_final'],
            'percentile_95_final': result['summary']['percentile_95_final']
        }

        if fire_achieved:
            response['fire_age'] = current_age
            response['years_to_fire'] = 0
        else:
            # Find required portfolio for FIRE
            required = find_required_portfolio(sim_params, target_certainty)
            response['required_portfolio'] = required
            response['additional_needed'] = required - portfolio

            # Project when we'll reach required portfolio
            # Simple projection: portfolio grows by (return * portfolio) + savings each year
            # Using real return (nominal - inflation) for projection
            real_return = expected_return - inflation

            if annual_savings <= 0 and real_return <= 0:
                # Can't reach FIRE - no savings and no growth
                response['fire_age'] = None
                response['years_to_fire'] = None
                response['projection_note'] = 'Cannot reach FIRE with negative savings and no real returns'
            else:
                # Project year by year until we hit required portfolio
                projected_portfolio = portfolio
                years = 0
                max_years = 60  # Safety limit

                while projected_portfolio < required and years < max_years:
                    # Portfolio grows by return, then add savings
                    projected_portfolio = projected_portfolio * (1 + real_return) + annual_savings
                    years += 1

                if years >= max_years:
                    response['fire_age'] = None
                    response['years_to_fire'] = None
                    response['projection_note'] = f'FIRE not reachable within {max_years} years'
                else:
                    response['fire_age'] = current_age + years
                    response['years_to_fire'] = years
                    response['projected_portfolio_at_fire'] = int(projected_portfolio)

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/simulate-historical', methods=['POST'])
def simulate_historical():
    """
    Run simulation against all historical market periods (1872-2022).

    Uses Shiller's S&P 500 data to test the retirement plan against every
    possible starting year in history. This preserves sequence-of-returns
    risk and shows actual worst-case scenarios.

    Note: Historical returns are real (inflation-adjusted), so income phases
    and expenses should be specified in today's dollars.
    """
    try:
        user_params = request.get_json() or {}
        # Historical uses actual returns, not Monte Carlo market params
        params = _merge_user_params(user_params, include_market_params=False)

        # Disable mortality for plain historical simulation
        params['mortality'] = {'enabled': False}

        result = run_historical_sequence(params)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/simulate-historical-mortality', methods=['POST'])
def simulate_historical_mortality():
    """
    Run historical simulation WITH mortality modeling.

    Same as /api/simulate-historical but includes mortality modeling
    to show real failure rate (failures where person would have lived).
    """
    try:
        user_params = request.get_json() or {}
        # Historical uses actual returns, not Monte Carlo market params
        params = _merge_user_params(user_params, include_market_params=False)

        # Force mortality enabled for this endpoint
        params['mortality']['enabled'] = True

        # Apply dynamic end_age for mortality-enabled historical simulation
        params = _apply_dynamic_end_age(params, user_params)

        result = run_historical_sequence(params)

        # Add dynamic end_age info to response if calculated
        if '_dynamic_end_age_info' in params:
            result['dynamic_end_age'] = params['_dynamic_end_age_info']

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/legacy-tradeoff', methods=['POST'])
def legacy_tradeoff():
    """
    Calculate the security vs. giving capacity trade-off curve.

    Shows how different portfolio levels affect:
    - Success rate (personal security)
    - Expected final portfolio (legacy/giving potential)

    This helps answer: "How much safety am I buying with each extra €100k,
    and what's the opportunity cost in terms of giving capacity?"
    """
    try:
        user_params = request.get_json() or {}
        params = _merge_user_params(user_params, include_market_params=True)

        # Get number of simulations per point (lower for speed)
        num_sims = min(int(user_params.get('num_simulations', 500)), 2000)

        result = calculate_legacy_tradeoff(params, num_simulations=num_sims)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stress-scenarios', methods=['POST'])
def stress_scenarios():
    """
    Run all stress test scenarios at once.

    Tests the retirement plan against 8 pessimistic scenarios:
    - Japan Lost Decades
    - Sequence Risk (Early Crash)
    - Climate Transition Shock
    - 1970s Stagflation
    - Great Depression
    - Secular Stagnation
    - Rising Rates Regime
    - Euro Crisis (Finland-specific)

    Returns dict mapping scenario_id to simulation results.
    Each result includes the standard simulation output plus
    scenario metadata (name, description, likelihood, commentary).

    Request body: Same as /api/simulate

    Response:
    {
        "scenarios": {
            "japan_lost_decades": {
                "metadata": {...},
                "results": {...}  # Same as run_monte_carlo output
            },
            ...
        },
        "params": {...},  # User parameters
        "total_time_seconds": 1.5
    }
    """
    try:
        start_time = time.time()
        user_params = request.get_json() or {}

        # Merge user params with defaults
        params = _merge_user_params(user_params, include_market_params=True)
        params = _apply_dynamic_end_age(params, user_params)

        # Get simulation settings
        years = params['end_age'] - params['start_age']
        num_sims_per_scenario = min(
            int(user_params.get('num_simulations_per_scenario', 500)),
            2000
        )

        # User's market assumptions (for scenarios that use them)
        mean = params.get('expected_return', 0.06)
        std = params.get('volatility', 0.15)

        # Run all scenarios
        scenario_results = {}
        for scenario_id in get_all_scenario_ids():
            # Generate returns for this scenario
            all_returns = generate_scenario_returns(
                scenario_id, years, num_sims_per_scenario, mean, std
            )

            # Run simulation with custom returns
            results = run_simulation_with_custom_returns(
                params, all_returns, scenario_id
            )

            # Get scenario metadata
            metadata = get_scenario_metadata(scenario_id)

            scenario_results[scenario_id] = {
                'metadata': metadata,
                'results': results
            }

        elapsed = time.time() - start_time

        response = {
            'scenarios': scenario_results,
            'params': {
                'starting_portfolio': params['starting_portfolio'],
                'annual_expenses': params['annual_expenses'],
                'start_age': params['start_age'],
                'end_age': params['end_age'],
                'num_simulations_per_scenario': num_sims_per_scenario,
                'expected_return': mean,
                'volatility': std,
            },
            'total_time_seconds': round(elapsed, 2)
        }

        # Add dynamic end_age info if calculated
        if '_dynamic_end_age_info' in params:
            response['dynamic_end_age'] = params['_dynamic_end_age_info']

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/defaults', methods=['GET'])
def get_defaults():
    """Return default parameters so frontend can initialize inputs."""
    return jsonify(DEFAULT_PARAMS)


@app.route('/api/calculate-end-age', methods=['POST'])
def calculate_end_age():
    """
    Calculate dynamic end_age based on mortality settings.

    This endpoint allows the frontend to get the calculated simulation endpoint
    without running a full simulation. Useful for showing the user what age
    their selected settings will simulate to.

    Request body:
        start_age: int - Age at retirement/simulation start
        health_class: str - "excellent", "average", or "impaired"
        tech_scenario: str - "conservative", "moderate", or "optimistic"

    Returns:
        end_age: int - Calculated simulation end age
        survival_at_end: float - Survival probability at end age (%)
        life_expectancy: float - Expected years of life from start_age
        survival_percentiles: dict - Survival % at key ages (75, 80, 85, 90, 95, 100, 105)
    """
    try:
        user_params = request.get_json() or {}

        start_age = int(user_params.get('start_age', DEFAULT_PARAMS['start_age']))
        health_class = user_params.get('health_class', 'average')
        tech_scenario = user_params.get('tech_scenario', 'moderate')

        result = calculate_dynamic_end_age(
            start_age=start_age,
            mortality_table=FINNISH_MALE_MORTALITY,
            health_class=health_class,
            tech_scenario=tech_scenario,
            survival_threshold=0.01,
            hard_cap=110
        )

        result['start_age'] = start_age
        result['health_class'] = health_class
        result['tech_scenario'] = tech_scenario

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
