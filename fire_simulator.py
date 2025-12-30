"""
FIRE Simulation Engine

This is the core logic that simulates how your portfolio evolves over time.
Now supports age-dependent income and multiple windfall events.
"""

from dataclasses import dataclass
from typing import List, Optional


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SimulationResult:
    """
    Holds the results of a single simulation run.

    A 'dataclass' is a convenient way to bundle related data together.
    Instead of passing around separate variables, we pack them into one object.
    """
    portfolio_values: List[float]  # Portfolio value at each year
    ages: List[int]                # Corresponding ages
    ruin_age: Optional[int]        # Age when money ran out (None if survived)
    final_portfolio: float         # Ending portfolio value
    hustle_activated: bool = False          # Whether emergency hustle was triggered
    hustle_activation_age: Optional[int] = None  # Age when hustle triggered
    # Spending adjustment tracking
    spending_reduced: bool = False           # Was spending ever reduced?
    spending_went_lean: bool = False         # Did we enter lean mode?
    spending_changes: Optional[List[dict]] = None  # History of spending state changes

    @property
    def survived(self) -> bool:
        """Did the portfolio last the entire simulation?"""
        return self.ruin_age is None


# =============================================================================
# INCOME & WINDFALL HELPERS
# =============================================================================

def get_income_for_age(age: int, income_phases: List[dict]) -> float:
    """Get income for a given age from income phases, or 0 if no phase matches."""
    return next((p['amount'] for p in income_phases if p['start_age'] <= age <= p['end_age']), 0.0)


def get_windfall_for_age(age: int, windfalls: List[dict]) -> float:
    """Get total windfall amount for a given age (could be multiple windfalls)."""
    return sum(w['amount'] for w in windfalls if w['age'] == age)


# =============================================================================
# CORE SIMULATION LOGIC
# =============================================================================

def simulate_single_year(
    portfolio: float,
    return_rate: float,
    expenses: float,
    income: float
) -> float:
    """
    Simulate one year of retirement.

    The order matters here:
    1. Portfolio grows (or shrinks) based on market returns
    2. You withdraw what you need to live on (expenses minus any income)

    Args:
        portfolio: Current portfolio value
        return_rate: Investment return this year (e.g., 0.06 for 6%)
        expenses: Annual spending
        income: Non-portfolio income (dividends, side work, pension)

    Returns:
        New portfolio value after growth and withdrawal
    """
    # Step 1: Apply investment returns
    portfolio_after_growth = portfolio * (1 + return_rate)

    # Step 2: Calculate how much you need to withdraw
    # If income covers expenses, withdrawal is zero (can't be negative)
    net_withdrawal = max(0, expenses - income)

    # Step 3: Subtract withdrawal from portfolio
    new_portfolio = portfolio_after_growth - net_withdrawal

    return new_portfolio


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
    """
    Run a full retirement simulation over multiple years.

    Args:
        starting_portfolio: How much you start with
        annual_expenses: Base annual spending (will grow with inflation)
        returns_sequence: List of annual returns, one per year
        start_age: Your age at the start
        inflation_rate: Annual inflation (expenses grow by this)
        income_phases: List of {start_age, end_age, amount, name}
        windfalls: List of {age, amount, name}
        emergency_hustle: Dict with {enabled, trigger_age_max, portfolio_threshold,
                          extra_income, duration}
        spending_rules: Dict with {enabled, drop_threshold, recovery_threshold,
                        reduced_spending, lean_spending, lean_age}

    Returns:
        SimulationResult with full history and outcomes
    """
    portfolio = starting_portfolio
    expenses = annual_expenses
    income_phases = income_phases or []
    windfalls = windfalls or []

    portfolio_values = [portfolio]  # Track history, starting with initial value
    ages = [start_age]
    ruin_age = None

    # Track inflation-adjusted base for income (income also grows with inflation)
    inflation_multiplier = 1.0

    # Emergency hustle tracking
    hustle_triggered = False
    hustle_activation_age = None
    hustle_years_remaining = 0

    # Dynamic spending rules tracking
    spending_state = 'normal'  # 'normal', 'reduced', or 'lean'
    spending_changes = []
    spending_reduced = False
    spending_went_lean = False
    annual_expenses_base = annual_expenses  # Store original for reference

    # Loop through each year of retirement
    for year_index, return_rate in enumerate(returns_sequence):
        current_age = start_age + year_index + 1

        # Check for windfalls at this age
        windfall = get_windfall_for_age(current_age, windfalls)
        if windfall > 0:
            portfolio += windfall

        # Get income for this age (base amount, then apply inflation)
        base_income = get_income_for_age(current_age, income_phases)
        income = base_income * inflation_multiplier

        # Emergency hustle logic
        extra_hustle_income = 0.0
        if emergency_hustle and emergency_hustle.get('enabled', False):
            # Check if we should trigger hustle
            if (not hustle_triggered and
                current_age <= emergency_hustle.get('trigger_age_max', start_age + 5) and
                portfolio < starting_portfolio * emergency_hustle.get('portfolio_threshold', 0.70)):
                # Trigger the hustle!
                hustle_triggered = True
                hustle_activation_age = current_age
                hustle_years_remaining = emergency_hustle.get('duration', 3)

            # Add hustle income if active
            if hustle_years_remaining > 0:
                extra_hustle_income = emergency_hustle.get('extra_income', 0) * inflation_multiplier
                hustle_years_remaining -= 1

        # Dynamic spending rules (only apply when hustle is NOT active)
        if spending_rules and spending_rules.get('enabled', False) and hustle_years_remaining == 0:
            rules = spending_rules
            # Calculate inflation-adjusted thresholds (thresholds are in today's euros)
            drop_threshold = starting_portfolio * rules['drop_threshold']
            recovery_threshold = starting_portfolio * rules['recovery_threshold']

            # Determine appropriate spending level based on portfolio
            if portfolio < drop_threshold:
                # Below drop threshold - need to reduce spending
                if current_age >= rules.get('lean_age', 60):
                    new_state = 'lean'
                else:
                    new_state = 'reduced'
            elif portfolio >= recovery_threshold:
                # Above recovery threshold - can return to normal
                new_state = 'normal'
            else:
                # In the hysteresis zone - keep current state
                new_state = spending_state

            # Track state changes
            if new_state != spending_state:
                spending_changes.append({
                    'age': current_age,
                    'from': spending_state,
                    'to': new_state,
                    'portfolio': portfolio
                })
                spending_state = new_state

            # Track if we ever reduced or went lean
            if spending_state == 'reduced':
                spending_reduced = True
            elif spending_state == 'lean':
                spending_reduced = True
                spending_went_lean = True

            # Apply spending based on state (all amounts grow with inflation)
            if spending_state == 'lean':
                expenses = rules['lean_spending'] * inflation_multiplier
            elif spending_state == 'reduced':
                expenses = rules['reduced_spending'] * inflation_multiplier
            else:
                expenses = annual_expenses_base * inflation_multiplier

        # Simulate this year (income includes regular + hustle)
        portfolio = simulate_single_year(portfolio, return_rate, expenses, income + extra_hustle_income)

        # Track the results
        portfolio_values.append(portfolio)
        ages.append(current_age)

        # Check for ruin (money ran out)
        if portfolio <= 0:
            ruin_age = current_age
            # Fill remaining years with zero for consistent array length
            remaining_years = len(returns_sequence) - year_index - 1
            portfolio_values.extend([0] * remaining_years)
            ages.extend(range(current_age + 1, current_age + remaining_years + 1))
            break

        # Apply inflation for next year
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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_withdrawal_rate(portfolio: float, expenses: float, income: float) -> float:
    """
    Calculate the withdrawal rate - a key FIRE metric.

    The "4% rule" says withdrawing 4% of your portfolio annually is safe.
    Lower = safer. Higher = riskier.
    """
    net_withdrawal = max(0, expenses - income)
    if portfolio <= 0:
        return float('inf')
    return net_withdrawal / portfolio


def format_currency(amount: float) -> str:
    """Format a number as euros with thousands separators."""
    return f"€{amount:,.0f}"


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    from config import DEFAULT_PARAMS

    params = DEFAULT_PARAMS
    years = params['end_age'] - params['start_age']

    # Create a sequence of returns (same return every year for now)
    steady_returns = [params['expected_return']] * years

    result = run_simulation(
        starting_portfolio=params['starting_portfolio'],
        annual_expenses=params['annual_expenses'],
        returns_sequence=steady_returns,
        start_age=params['start_age'],
        inflation_rate=params['inflation'],
        income_phases=params.get('income_phases'),
        windfalls=params.get('windfalls'),
        spending_rules=params.get('spending_rules')
    )

    print("=== Basic Simulation Test (Age-Dependent Income) ===\n")
    print(f"Starting Portfolio: {format_currency(params['starting_portfolio'])}")
    print(f"Annual Expenses: {format_currency(params['annual_expenses'])}")

    print("\nIncome Phases:")
    for phase in params.get('income_phases', []):
        print(f"  Age {phase['start_age']}-{phase['end_age']}: {format_currency(phase['amount'])}/year ({phase['name']})")

    print("\nWindfall Events:")
    for w in params.get('windfalls', []):
        print(f"  Age {w['age']}: {format_currency(w['amount'])} ({w['name']})")

    print(f"\nSimulation: Age {params['start_age']} to {params['end_age']} ({years} years)")
    print(f"Returns: {params['expected_return']:.0%} nominal, {params['inflation']:.0%} inflation")
    print()
    print(f"Survived: {'Yes' if result.survived else 'No'}")
    print(f"Final Portfolio: {format_currency(result.final_portfolio)}")

    # Show snapshots at key ages
    print("\nPortfolio snapshots:")
    for age in [47, 55, 58, 65, 75, 85, 95]:
        if age in result.ages:
            idx = result.ages.index(age)
            income = get_income_for_age(age, params.get('income_phases', []))
            print(f"  Age {age}: {format_currency(result.portfolio_values[idx]):>15}  (income: {format_currency(income)}/yr)")
