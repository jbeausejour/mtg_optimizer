# MTG Optimizer Project Guide

## Overview
The MTG Optimizer is a sophisticated web application for Magic: The Gathering card management and purchase optimization. It combines advanced optimization algorithms with real-time price data to help users find the best purchasing strategies across multiple card vendors.

## Technology Stack

### Backend
- **Framework**: Quart (async Python web framework)
- **Database**: SQLAlchemy with async support (asyncmy for MySQL)
- **Task Queue**: Celery with Redis broker
- **Authentication**: JWT-based with quart-jwt-extended
- **Optimization**: PuLP (MILP), DEAP (evolutionary algorithms)
- **Web Scraping**: Selenium, BeautifulSoup, requests, cloudscraper
- **Server**: Uvicorn ASGI server

### Frontend
- **Framework**: React 19.1.0
- **UI Library**: Ant Design (antd) 5.24.9
- **State Management**: React Query (@tanstack/react-query)
- **Charts**: Chart.js with react-chartjs-2
- **HTTP Client**: Axios
- **Build Tool**: Create React App

## Project Structure

### Backend (`/backend/`)
```
app/
├── api/              # API routes (admin, cards, optimization, scans, sites, watchlist)
├── models/           # SQLAlchemy models (users, cards, scans, optimization results)
├── services/         # Business logic layer
├── optimization/     # Advanced optimization algorithms
│   ├── algorithms/   # MILP, NSGA-II/III, MOEA/D, hybrid approaches
│   ├── core/         # Base classes and metrics
│   └── config/       # Algorithm configurations
├── tasks/            # Celery background tasks
├── utils/            # Helpers, data fetchers, validators
├── constants/        # Card mappings, currency constants
└── dto/              # Data Transfer Objects
```

### Frontend (`/frontend/`)
```
src/
├── components/       # Reusable React components
├── pages/           # Main application pages (Dashboard, Optimize, Results, etc.)
├── hooks/           # Custom React hooks
├── utils/           # API config, contexts, utilities
└── App.js           # Main application component
```

## Key Features

### 1. Card Management
- Scryfall API integration for comprehensive card data
- Card search and details display with mana symbols and set symbols
- Buylist creation and management
- Import/export functionality (Excel/CSV)

### 2. Multi-Site Price Scanning
- Automated scraping of multiple card vendors
- Price comparison across sites
- Quality and language filtering
- Real-time price updates via background tasks

### 3. Advanced Optimization Algorithms
- **MILP**: Mixed Integer Linear Programming for exact optimization
- **NSGA-II/III**: Multi-objective evolutionary algorithms
- **MOEA/D**: Decomposition-based evolutionary algorithm
- **Hybrid approaches**: Combining MILP with evolutionary algorithms
- Pareto-optimal solution finding with configurable objectives

### 4. User Management & Authentication
- JWT-based authentication system
- User-specific buylists and optimization results
- Settings and preferences management

### 5. Background Processing
- Celery tasks for long-running operations
- Scheduled cache refreshes
- Watchlist price monitoring

## Development Setup

### Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Database migrations
flask db migrate -m "description"
flask db upgrade

# Start Redis
redis-server

# Start Celery worker
celery -A app.tasks.celery_worker worker --loglevel=info

# Run application
python app.py
```

### Frontend Setup
```bash
# Install dependencies
npm install

# Development server
npm start

# Production build
npm run build
```

## Important Commands

### Backend
- `python app.py` - Start the Quart application
- `celery -A app.tasks.celery_worker worker --loglevel=info` - Start Celery worker
- `flask db migrate -m "message"` - Create new migration
- `flask db upgrade` - Apply migrations
- `pytest` - Run tests

### Frontend
- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run ESLint

## Code Quality & Linting
- **Python**: pylint, black (line length 120), isort, mypy
- **JavaScript**: ESLint with import plugin
- Run linting before committing changes

## Key Database Models
- `User`: Authentication and user profiles
- `Site`: Card vendor configurations
- `UserBuylistCard`: User's desired cards (inherits from BaseCard)
- `Scan` & `ScanResult`: Price scanning results
- `OptimizationResults`: Algorithm results storage
- `Watchlist`: Price monitoring system

## Environment Configuration
- Copy `.env.example` to `.env` and configure:
  - Database connection strings
  - Redis connection details
  - Scryfall API settings
  - JWT secret keys
  - Vendor-specific configurations

## Testing Strategy
- **Backend**: pytest for unit and integration tests
- **Frontend**: React Testing Library for component tests
- **Services**: Comprehensive service layer testing
- **Optimization**: Algorithm performance and correctness tests

## Architecture Notes

### Optimization Engine
The application features a sophisticated optimization system with multiple algorithms:
- Use `USE_NEW_OPTIMIZATION_ARCHITECTURE` flag to switch between implementations
- Algorithms are configured in `optimization/config/algorithm_configs.py`
- Results are post-processed and formatted for frontend display

### Background Tasks
- Celery handles long-running operations like price scanning
- Redis serves as both message broker and cache
- Tasks are defined in `tasks/` directory with proper error handling

### API Design
- RESTful endpoints organized by domain (cards, optimization, scans, etc.)
- Consistent error handling and response formats
- JWT authentication for protected routes

## Common Development Tasks

### Adding New Optimization Algorithm
1. Create algorithm class in `optimization/algorithms/`
2. Register in `optimization/algorithms/factory.py`
3. Add configuration in `optimization/config/algorithm_configs.py`
4. Update tests in `tests/test_optimization.py`

### Adding New Card Vendor
1. Create scraper in `utils/data_fetcher.py`
2. Add site configuration in database
3. Update constants in `constants/`
4. Test scraping functionality

### UI Component Development
1. Create component in `components/`
2. Follow existing patterns for theming and accessibility
3. Use Ant Design components for consistency
4. Add to appropriate page in `pages/`

## Performance Considerations
- Use React Query for efficient data fetching and caching
- Implement virtualization for large card lists
- Optimize database queries with proper indexing
- Use background tasks for expensive operations

## Deployment Notes
- Application is containerized for production deployment
- Redis and database connections are externalized
- Static files are served from `/frontend/build/`
- Environment-specific configurations available

## Troubleshooting
- Check Redis connection for task queue issues
- Monitor Celery worker logs for background task failures
- Verify database migrations are up to date
- Ensure Scryfall API rate limits are respected
- Check browser console for frontend errors

## Contributing
1. Follow existing code style and patterns
2. Run linting and tests before submitting changes
3. Update documentation for new features
4. Consider performance impact of changes
5. Test across different card vendors and edge cases