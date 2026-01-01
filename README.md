# FIRE Simulator

Monte Carlo simulation tool for Financial Independence, Retire Early (FIRE) planning.

**Live demo:** http://77.42.45.226/fire/

## Features

- **Monte Carlo Simulation** - Run up to 100,000 random market scenarios
- **Historical Backtesting** - Test against every historical market period (1872-2022)
- **Age-Dependent Income** - Model income that changes over time (side hustles, pensions, etc.)
- **Windfall Events** - Include one-time additions like inheritance or asset liquidation
- **Emergency Hustle** - Model returning to work if portfolio crashes early in retirement
- **Dynamic Spending Rules** - Automatically reduce spending when portfolio drops below thresholds
- **Advanced Mortality Modeling** - Two-dimension model with health class and medical advances
- **Dynamic Simulation Endpoint** - Automatically calculates how long to simulate based on longevity
- **Interactive Web App** - Adjust all parameters in real-time with built-in tooltips explaining each setting

## Quick Start

### Option 1: Interactive Web App (Recommended)

```bash
# Install dependencies
pip install flask flask-cors

# Start the API server
python3 api.py
# Open http://localhost:5000
```

### Option 2: Command Line

```bash
# Run CLI analysis
python3 run_simulation.py

# Generate static visualization
python3 export_data.py
python3 -m http.server 8080 -d visualization
# Open http://localhost:8080
```

## Files

| File | Purpose |
|------|---------|
| `api.py` | Flask API for interactive web app |
| `config.py` | Default parameters and mortality tables |
| `fire_simulator.py` | Core simulation engine |
| `scenarios.py` | Market return generators |
| `run_simulation.py` | CLI runner with analysis |
| `export_data.py` | Export to JSON for static visualization |
| `visualization/interactive.html` | Interactive web frontend |
| `visualization/index.html` | Static visualization (uses data.json) |

## Web App Parameters

All parameters are adjustable in the UI. Each section has a **[?] tooltip** that explains what the parameters mean and how to use them - click the icon next to any section header for detailed help.

| Category | Parameters |
|----------|------------|
| Portfolio | Starting portfolio, annual expenses |
| Income | Income phases by age range (pensions, side income, etc.) |
| Windfalls | One-time events (inheritance, asset liquidation) |
| Time | Start age (end age calculated automatically with mortality) |
| Investment | Expected return, inflation, volatility |
| Hustle Rules | Trigger age, duration, portfolio threshold |
| Spending Rules | Drop/recovery thresholds, lean mode age |
| Mortality | Health class, medical advances scenario |

Euro values are entered in thousands (€k) for readability.

## Mortality Modeling

The simulator includes a sophisticated two-dimension mortality model:

### Dimension 1: Personal Health

Choose your health classification:

| Health Class | Description | Effect |
|-------------|-------------|--------|
| **Excellent** | Non-smoker, healthy weight, regular exercise, family longevity | 70% lower mortality at age 45, converging to average by 100 |
| **Average** | General population baseline | Standard mortality rates |
| **Impaired** | Chronic conditions, smoking, obesity | 50% higher mortality at age 45, converging by 100 |

### Dimension 2: Medical Advances

Choose your assumption about future medical progress:

| Scenario | Description | Life Expectancy Impact |
|----------|-------------|----------------------|
| **Conservative** | Improvement slows from historical rates | +1-2 years |
| **Moderate** | Continue recent trends (post-2010) | +2-3 years |
| **Optimistic** | AI, gene therapy, etc. accelerate advances | +4-5 years |

### Dynamic Simulation Endpoint

Instead of manually choosing "simulate until age 95", the system automatically calculates when to end the simulation based on your longevity settings:

- Simulation runs until survival probability drops below 1%
- Hard cap at age 110 (mortality table extends to supercentenarian data)
- Example results for starting age 47:

| Health | Tech | Simulates To | Life Expectancy |
|--------|------|--------------|-----------------|
| Impaired | Conservative | Age 93 | 28.3 years |
| Average | Moderate | Age 96 | 31.7 years |
| Excellent | Optimistic | Age 99 | 36.8 years |

This ensures the simulation captures realistic longevity scenarios without requiring users to guess an appropriate end age.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/simulate` | POST | Run Monte Carlo simulation |
| `/api/simulate-historical` | POST | Run historical backtest (without mortality) |
| `/api/simulate-historical-mortality` | POST | Run historical backtest with mortality |
| `/api/fire-assessment` | POST | Calculate when you'll reach FIRE |
| `/api/legacy-tradeoff` | POST | Security vs. giving trade-off: how much safety does each €100k buy, and what's the opportunity cost in giving capacity? |
| `/api/stress-scenarios` | POST | Run 8 pessimistic scenarios (Japan Lost Decades, 1970s Stagflation, Great Depression, etc.) |
| `/api/calculate-end-age` | POST | Get dynamic end age for mortality settings |
| `/api/defaults` | GET | Get default parameter values |
| `/` | GET | Serve interactive web app |

### Mortality Parameters (for POST endpoints)

```json
{
  "mortality": {
    "enabled": true,
    "health_class": "excellent",  // "excellent", "average", or "impaired"
    "tech_scenario": "moderate"   // "conservative", "moderate", or "optimistic"
  }
}
```

When `mortality.enabled` is `true` and `end_age` is not provided, the API automatically calculates the simulation endpoint based on longevity settings.

## Deployment (Hetzner/Linux)

```bash
# Clone and setup
git clone <repo-url>
cd fire-simulator
pip install flask flask-cors

# Run with systemd (production)
sudo cp fire-simulator.service /etc/systemd/system/
sudo systemctl enable fire-simulator
sudo systemctl start fire-simulator

# Nginx config (reverse proxy)
location /fire/ {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Example Output

```
=== Results (ignoring mortality) ===
Success rate: 99.8%
Median final portfolio: €8,673,090

=== Results (with mortality) ===
Health class: excellent, Tech scenario: moderate
Simulating to age 99 (1% survival threshold)
Life expectancy: 36.8 years from age 47

Survived to 99 with money: 12 (1.2%)
Died with money (before 99): 976 (97.6%)
Ran out of money while alive: 12 (1.2%)

REAL FAILURE RATE: 1.20%
```

**What counts as failure?** A simulation "fails" when the portfolio is depleted (can't cover next year's expenses) while the person is still alive. Running out of money after death doesn't count as failure - the "real failure rate" only measures scenarios where you outlived your money.

## Requirements

- Python 3.8+
- Flask, Flask-CORS (for web app only)

## License

MIT
