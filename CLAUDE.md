# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is Freqtrade, a free and open-source cryptocurrency trading bot written in Python. The bot supports multiple exchanges, backtesting, strategy optimization, and machine learning-powered trading via FreqAI.

## Development Commands

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --random-order --cov=freqtrade --cov-config=.coveragerc tests/

# Run specific test file
pytest tests/test_<file_name>.py

# Run specific test method
pytest tests/test_<file_name>.py::test_<method_name>
```

### Code Quality
```bash
# Run linting (Ruff)
ruff check .

# Format code
ruff format .

# Type checking
mypy freqtrade

# Run all pre-commit hooks
pre-commit run -a
```

### Package Management
The project uses `uv` for dependency management:
```bash
# Install dependencies
uv sync

# Install with all extras (for development)
uv sync --all-extras

# Install without dev dependencies
uv sync --no-dev --all-extras
```

### Running Freqtrade
```bash
# Start trading (dry-run or live based on config)
freqtrade trade --config user_data/config.json --strategy <StrategyName>

# Start backtesting
freqtrade backtesting --config user_data/config.json --strategy <StrategyName>

# Start hyperopt
freqtrade hyperopt --config user_data/config.json --strategy <StrategyName>

# Start web UI
freqtrade webserver --config user_data/config.json
```

### Docker Development
```bash
# Build and run with docker-compose
docker-compose up --build

# Run specific freqtrade command in container
docker-compose exec freqtrade freqtrade <command>
```

## Architecture Overview

### Core Components

1. **FreqtradeBot** (`freqtrade/freqtradebot.py`): Main trading logic and execution engine
2. **Strategy Interface** (`freqtrade/strategy/interface.py`): Base class for all trading strategies
3. **Exchange Layer** (`freqtrade/exchange/`): Handles communication with cryptocurrency exchanges
4. **Data Management** (`freqtrade/data/`): Historical data handling, backtesting data, and data providers
5. **Persistence** (`freqtrade/persistence/`): Database models and trade/order storage
6. **FreqAI** (`freqtrade/freqai/`): Machine learning framework for predictive trading

### Key Directories

- `freqtrade/commands/`: CLI command implementations
- `freqtrade/optimize/`: Backtesting and hyperparameter optimization
- `freqtrade/rpc/`: REST API, Telegram bot, and web interface
- `freqtrade/plugins/`: Pairlist management and trade protections
- `freqtrade/templates/`: Strategy and configuration templates
- `user_data/`: User configurations, strategies, and data storage

### FreqAI Architecture

FreqAI uses a modular approach:
- **Data Kitchen**: Feature engineering and data preparation
- **Data Drawer**: Historical data management and caching
- **Base Models**: Abstract classes for different model types (Classifier, Regressor, RL)
- **Prediction Models**: Concrete implementations (XGBoost, LightGBM, PyTorch, etc.)

### Strategy Development

Strategies inherit from `IStrategy` and implement:
- `populate_indicators()`: Technical indicator calculation
- `populate_entry_trend()`: Entry signal logic
- `populate_exit_trend()`: Exit signal logic
- Optional: `custom_entry_price()`, `custom_exit_price()`, `custom_stoploss()`

## Code Standards

### Style Guidelines
- Line length: 100 characters
- Use Ruff for linting and formatting
- Type hints required for all functions
- Docstrings follow reST format
- Import sorting via isort with black profile

### Testing Requirements
- Unit tests required for new features
- Maintain test coverage
- Use pytest fixtures for common test data
- Mock external dependencies (exchanges, APIs)

### Git Workflow
- Create PRs against `develop` branch, not `stable`
- Use meaningful commit messages
- Run pre-commit hooks before committing
- All code must pass CI checks (tests, linting, type checking)

## Important Notes

### FreqAI Development
- Models are stored in `user_data/models/`
- Feature engineering happens in the strategy's `populate_any_indicators()`
- Shapley values are available for model interpretability via `freqtrade/freqai/shapley/`

### Exchange Integration
- New exchanges extend `Exchange` base class
- Test against both live and sandbox environments
- Handle exchange-specific quirks in dedicated exchange files

### Configuration
- JSON schema validation in `freqtrade/config_schema/`
- Environment variable support in `freqtrade/configuration/environment_vars.py`
- Template configurations in `config_examples/`

### Performance Considerations
- Use vectorized operations in pandas for indicator calculations
- Implement caching for expensive computations
- Consider memory usage in long-running backtests
- Use proper database indexing for trade queries