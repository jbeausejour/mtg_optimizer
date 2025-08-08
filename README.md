# MTG Optimizer

A sophisticated web application for Magic: The Gathering card management and purchase optimization. Combines advanced optimization algorithms with real-time price data to help users find the best purchasing strategies across multiple card vendors.

## Features

- **Card Management**: Comprehensive card database with Scryfall API integration
- **Multi-Site Price Scanning**: Automated price comparison across multiple vendors
- **Advanced Optimization**: MILP, NSGA-II/III, MOEA/D algorithms for optimal purchasing
- **User Management**: JWT-based authentication with personal buylists
- **Real-time Updates**: Background processing for price monitoring and cache updates

## Technology Stack

### Backend
- **Framework**: Quart (async Python)
- **Database**: SQLAlchemy with async MySQL support
- **Task Queue**: Celery with Redis
- **Authentication**: JWT with quart-jwt-extended
- **Optimization**: PuLP (MILP), DEAP (evolutionary algorithms)
- **Web Scraping**: Selenium, BeautifulSoup, cloudscraper

### Frontend
- **Framework**: React 19.1.0
- **UI**: Ant Design 5.24.9
- **State Management**: React Query
- **Charts**: Chart.js with react-chartjs-2
- **Build Tool**: Create React App

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Redis
- MySQL

### Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database and Redis settings

# Run database migrations
flask db upgrade

# Start Redis server
redis-server

# Start Celery worker
celery -A app.tasks.celery_worker worker --loglevel=info

# Run application
python app.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

## Project Structure

```
mtg_optimizer/
├── backend/
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── models/           # Database models
│   │   ├── services/         # Business logic
│   │   ├── optimization/     # Optimization algorithms
│   │   ├── tasks/           # Celery background tasks
│   │   └── utils/           # Utilities and helpers
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Application pages
│   │   ├── hooks/          # Custom hooks
│   │   └── utils/          # Frontend utilities
│   └── package.json
└── README.md
```

## Key Commands

### Development
```bash
# Backend
python app.py                                           # Start backend server
celery -A app.tasks.celery_worker worker --loglevel=info  # Start task worker
flask db migrate -m "description"                      # Create migration
flask db upgrade                                        # Apply migrations

# Frontend
npm start                                              # Start dev server
npm run build                                         # Production build
npm test                                              # Run tests
```

### Code Quality
```bash
# Python (line length 120)
pylint app/
black app/
isort app/
mypy app/

# JavaScript
npm run lint
```

## Optimization Algorithms

The application features multiple optimization strategies:

- **MILP**: Mixed Integer Linear Programming for exact solutions
- **NSGA-II/III**: Multi-objective evolutionary algorithms
- **MOEA/D**: Decomposition-based evolutionary optimization
- **Hybrid**: Combined MILP and evolutionary approaches

Configure algorithms in `backend/app/optimization/config/algorithm_configs.py`.

## API Endpoints

### Cards
- `GET /api/cards/search` - Search cards
- `GET /api/cards/{id}` - Get card details
- `POST /api/cards/buylist` - Create/update buylist

### Optimization
- `POST /api/optimization/run` - Run optimization
- `GET /api/optimization/results/{id}` - Get results

### Price Scanning
- `POST /api/scans/trigger` - Start price scan
- `GET /api/scans/status/{id}` - Check scan status

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=mysql+asyncmy://user:pass@localhost/mtg_optimizer

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET_KEY=your-secret-key

# Scryfall API
SCRYFALL_API_BASE=https://api.scryfall.com
```

### Algorithm Configuration
Modify `backend/app/optimization/config/algorithm_configs.py` to:
- Adjust algorithm parameters
- Enable/disable specific algorithms
- Configure optimization objectives

## Development Guidelines

1. **Code Style**: Follow existing patterns and linting rules
2. **Testing**: Write tests for new features and algorithms
3. **Documentation**: Update relevant documentation
4. **Performance**: Consider impact on optimization and UI responsiveness
5. **Security**: Never commit API keys or sensitive data

## Deployment

The application is containerized for production:

1. Build frontend: `npm run build`
2. Configure production environment variables
3. Run database migrations
4. Start Redis and Celery workers
5. Deploy with your preferred container orchestration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following code style guidelines
4. Run tests and linting
5. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check existing GitHub issues
2. Create new issue with detailed description
3. Include relevant logs and configuration details