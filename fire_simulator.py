"""
FIRE Simulation Engine

Core logic that simulates portfolio evolution over time with age-dependent
income, windfall events, emergency hustle, and dynamic spending rules.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SimulationResult:
    """Results of a single simulation run."""
    portfolio_values: List[float]
    ages: List[int]
    ruin_age: Optional[int]
    final_portfolio: float
    hustle_activated: bool = False
    hustle_activation_age: Optional[int] = None
    spending_reduced: bool = False
    spending_went_lean: bool = False
    spending_changes: Optional[List[dict]] = None

    @property
    def survived(self) -> bool:
        return self.ruin_age is None


def get_income_for_age(age: int, income_phases: List[dict]) -> float:
    """Get income for a given age from income phases, or 0 if no phase matches."""
    return next((p['amount'] for p in income_phases if p['start_age'] <= age <= p['end_age']), 0.0)


def get_windfall_for_age(age: int, windfalls: List[dict]) -> float:
    """Get total windfall amount for a given age."""
    return sum(w['amount'] for w in windfalls if w['age'] == age)


def simulate_single_year(
    portfolio: float,
    return_rate: float,
    expenses: float,
    income: float
) -> float:
    """
    Simulate one year: apply returns, then withdraw (expenses - income).
    """
    portfolio_after_growth = portfolio * (1 + return_rate)
    net_withdrawal = max(0, expenses - income)
    return portfolio_after_growth - net_withdrawal


def run_simulation(
    starting_portfolio: float,
    annual_expenses: float,
    returns_sequence: List[float],
    start_age: int,
    inflation_rate: float = 0.0,
    income_phases: Optional[List[dict]] = None,
    windfalls: Optional[List[dict]] = None,
    emergency_hustle: Optional[dict] = None,
    spending_rules: Optional[dict] = None
) -> SimulationResult:
    """Run a full retirement simulation over multiple years."""
    portfolio = starting_portfolio
    expenses = annual_expenses
    income_phases = income_phases or []
    windfalls = windfalls or []

    portfolio_values = [portfolio]
    ages = [start_age]
    ruin_age = None

    # Income grows with inflation
    inflation_multiplier = 1.0

    # Emergency hustle state
    hustle_triggered = False
    hustle_activation_age = None
    hustle_years_remaining = 0

    # Spending rules state
    spending_state = 'normal'
    spending_changes = []
    spending_reduced = False
    spending_went_lean = False
    annual_expenses_base = annual_expenses

    for year_index, return_rate in enumerate(returns_sequence):
        # Age at END of this year (year 0 ends at age 48 if start_age=47)
        current_age = start_age + year_index + 1

        windfall = get_windfall_for_age(current_age, windfalls)
        if windfall > 0:
            portfolio += windfall

        base_income = get_income_for_age(current_age, income_phases)
        income = base_income * inflation_multiplier

        # Emergency hustle: return to work if portfolio crashes early
        extra_hustle_income = 0.0
        if emergency_hustle and emergency_hustle.get('enabled', False):
            if (not hustle_triggered and
                current_age <= emergency_hustle.get('trigger_age_max', start_age + 5) and
                portfolio < starting_portfolio * emergency_hustle.get('portfolio_threshold', 0.70)):
                hustle_triggered = True
                hustle_activation_age = current_age
                hustle_years_remaining = emergency_hustle.get('duration', 3)

            if hustle_years_remaining > 0:
                extra_hustle_income = emergency_hustle.get('extra_income', 0) * inflation_multiplier
                hustle_years_remaining -= 1

        # Dynamic spending rules (only when hustle is NOT active)
        # State machine with hysteresis to prevent rapid toggling:
        # - Drop below drop_threshold -> enter reduced/lean
        # - Rise above recovery_threshold -> return to normal
        # - Between thresholds -> stay in current state
        if spending_rules and spending_rules.get('enabled', False) and hustle_years_remaining == 0:
            rules = spending_rules
            drop_threshold = starting_portfolio * rules['drop_threshold']
            recovery_threshold = starting_portfolio * rules['recovery_threshold']

            if portfolio < drop_threshold:
                new_state = 'lean' if current_age >= rules.get('lean_age', 60) else 'reduced'
            elif portfolio >= recovery_threshold:
                new_state = 'normal'
            else:
                new_state = spending_state

            if new_state != spending_state:
                spending_changes.append({
                    'age': current_age,
                    'from': spending_state,
                    'to': new_state,
                    'portfolio': portfolio
                })
                spending_state = new_state

            if spending_state == 'reduced':
                spending_reduced = True
            elif spending_state == 'lean':
                spending_reduced = True
                spending_went_lean = True

            # Apply spending level (all amounts grow with inflation)
            if spending_state == 'lean':
                expenses = rules['lean_spending'] * inflation_multiplier
            elif spending_state == 'reduced':
                expenses = rules['reduced_spending'] * inflation_multiplier
            else:
                expenses = annual_expenses_base * inflation_multiplier

        portfolio = simulate_single_year(portfolio, return_rate, expenses, income + extra_hustle_income)

        portfolio_values.append(portfolio)
        ages.append(current_age)

        if portfolio <= 0:
            ruin_age = current_age
            # Fill remaining years with zero for consistent array length
            remaining_years = len(returns_sequence) - year_index - 1
            portfolio_values.extend([0] * remaining_years)
            ages.extend(range(current_age + 1, current_age + remaining_years + 1))
            break

        # Compound inflation for next year:
        # - expenses: base spending (used when spending_rules disabled or state='normal')
        # - inflation_multiplier: adjusts income and spending_rules amounts
        expenses *= (1 + inflation_rate)
        inflation_multiplier *= (1 + inflation_rate)

    return SimulationResult(
        portfolio_values=portfolio_values,
        ages=ages,
        ruin_age=ruin_age,
        final_portfolio=portfolio_values[-1],
        hustle_activated=hustle_triggered,
        hustle_activation_age=hustle_activation_age,
        spending_reduced=spending_reduced,
        spending_went_lean=spending_went_lean,
        spending_changes=spending_changes if spending_changes else None
    )


