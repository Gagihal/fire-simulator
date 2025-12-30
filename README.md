# FIRE Simulator

Monte Carlo simulation tool for Financial Independence, Retire Early (FIRE) planning.

## Features

- **Monte Carlo Simulation** - Run thousands of random market scenarios to understand the range of possible outcomes
- **Age-Dependent Income** - Model income that changes over time (side hustles, pensions, etc.)
- **Windfall Events** - Include one-time additions like inheritance or asset liquidation
- **Emergency Hustle** - Model returning to work if portfolio crashes early in retirement
- **Dynamic Spending Rules** - Automatically reduce spending when portfolio drops below thresholds
- **Mortality Modeling** - Uses Finnish male mortality tables to calculate realistic failure rates
- **Interactive Visualization** - HTML dashboard with charts and scenario comparison

## Quick Start

```bash
# Run CLI analysis
python3 run_simulation.py

# Generate data and view visualization
python3 export_data.py
python3 -m http.server 8080 -d visualization
# Open http://localhost:8080
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | Personal parameters and mortality tables |
| `fire_simulator.py` | Core simulation engine |
| `scenarios.py` | Market return generators |
| `run_simulation.py` | CLI runner with analysis |
| `export_data.py` | Export to JSON for visualization |
| `visualization/` | HTML dashboard |

## Configuration

Edit `config.py` to set your parameters:

```python
DEFAULT_PARAMS = {
    'starting_portfolio': 1_200_000,
    'annual_expenses': 32_500,
    'income_phases': [...],
    'windfalls': [...],
    'expected_return': 0.06,
    'inflation': 0.02,
    'volatility': 0.15,
    'start_age': 47,
    'end_age': 95,
    'emergency_hustle': {...},
    'spending_rules': {...},
    'mortality': {...},
}
```

## Example Output

```
Success Rate: 99.8%
Median Final Portfolio: €8,673,090

With mortality modeling:
  Real Failure Rate: 0.10%
  (only counting those who ran out while alive)
```

## Requirements

- Python 3.8+
- No external dependencies (uses only standard library)

## License

MIT
