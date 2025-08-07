#!/bin/bash
# setup-superclaude.sh - Set up SuperClaude configuration for MTG Optimizer

set -e

echo "Setting up SuperClaude configuration for MTG Optimizer..."

# Create .claude directory structure
mkdir -p .claude/{commands,workflows,shared}

# Create project-specific commands directory
mkdir -p .claude/commands/{optimization,scraping,testing,deployment}

echo "✅ Created .claude directory structure"

# Create optimization-specific commands
cat > .claude/commands/optimization/analyze-algorithm.md << 'EOF'
# Analyze Optimization Algorithm Performance

Analyze the performance and effectiveness of MTG optimization algorithms:

1. **Algorithm Comparison**: Compare MILP vs NSGA-II vs MOEA/D performance
2. **Pareto Front Analysis**: Evaluate quality of Pareto-optimal solutions
3. **Scalability Testing**: Test with increasing card set sizes
4. **Objective Trade-offs**: Analyze cost vs vendor count vs quality trade-offs
5. **Parameter Tuning**: Suggest optimal algorithm parameters
6. **Performance Metrics**: Execution time, memory usage, solution quality

Focus on:
- Solution convergence rates
- Multi-objective optimization effectiveness  
- Large dataset handling (1000+ cards)
- Real-world constraint satisfaction

Generate actionable recommendations for algorithm improvements.
EOF

cat > .claude/commands/optimization/tune-parameters.md << 'EOF'
# Tune Optimization Algorithm Parameters

Optimize algorithm parameters for better MTG card optimization:

1. **Current Parameters Review**: Analyze existing parameter configurations
2. **Performance Baseline**: Establish current performance metrics
3. **Parameter Space Exploration**: Test different parameter combinations
4. **Objective Weighting**: Optimize multi-objective weights (cost, vendor count, quality)
5. **Constraint Tuning**: Adjust algorithm constraints for real-world scenarios
6. **Validation Testing**: Test parameter changes with historical data

Parameters to focus on:
- MILP solver settings (timeout, gap tolerance)
- NSGA-II population size, crossover/mutation rates
- MOEA/D decomposition method, neighbor size
- Hybrid algorithm switching thresholds

Provide parameter recommendations with performance justification.
EOF

# Create scraping-specific commands  
cat > .claude/commands/scraping/debug-scraper.md << 'EOF'
# Debug Card Vendor Scraper Issues

Diagnose and fix web scraping issues for card vendors:

1. **Scraper Health Check**: Test all vendor scrapers for functionality
2. **Anti-Bot Detection**: Identify if scrapers are being blocked
3. **Rate Limiting Analysis**: Check if rate limits are being respected
4. **Data Quality Validation**: Verify scraped price data accuracy
5. **Error Pattern Analysis**: Identify common failure patterns
6. **Stealth Improvements**: Enhance scraper stealth capabilities

Focus on:
- Selenium WebDriver configurations
- cloudscraper effectiveness
- undetected-chromedriver setup
- Request headers and timing
- Proxy usage optimization
- Data validation pipelines

Generate specific fixes for identified issues.
EOF

cat > .claude/commands/scraping/add-vendor.md << 'EOF'
# Add New Card Vendor Scraper

Create a new scraper for a card vendor website:

1. **Site Analysis**: Analyze target vendor website structure
2. **Anti-Bot Assessment**: Evaluate anti-bot measures and bypass strategies
3. **Data Extraction Strategy**: Plan price and inventory data extraction
4. **Scraper Implementation**: Build robust scraper with error handling
5. **Rate Limiting**: Implement appropriate request throttling
6. **Testing Suite**: Create comprehensive tests for the new scraper
7. **Integration**: Integrate with existing scraping infrastructure

Include:
- Site-specific configurations
- Data normalization procedures
- Error handling and retry logic
- Quality validation checks
- Performance monitoring

Ensure compliance with robots.txt and terms of service.
EOF

# Create testing commands
cat > .claude/commands/testing/test-optimization.md << 'EOF'
# Test Optimization Algorithms Comprehensively

Create and run comprehensive tests for MTG optimization algorithms:

1. **Unit Tests**: Test individual algorithm components
2. **Integration Tests**: Test algorithm integration with data layer
3. **Performance Tests**: Benchmark algorithm execution times
4. **Accuracy Tests**: Validate solution quality with known datasets
5. **Edge Case Testing**: Test with extreme scenarios (empty lists, single vendor, etc.)
6. **Regression Testing**: Ensure changes don't break existing functionality

Test scenarios:
- Small buylist (< 10 cards)
- Medium buylist (10-100 cards)  
- Large buylist (100+ cards)
- Single vendor optimization
- Multi-vendor optimization
- Quality constraints
- Budget constraints

Generate test reports with performance metrics and recommendations.
EOF

# Create deployment commands
cat > .claude/commands/deployment/deploy-staging.md << 'EOF'
# Deploy to Staging Environment

Deploy MTG Optimizer to staging environment with full validation:

1. **Pre-deployment Checks**: Verify build quality and test coverage
2. **Environment Preparation**: Ensure staging environment is ready
3. **Database Migration**: Run database migrations safely
4. **Application Deployment**: Deploy backend and frontend components
5. **Service Health Checks**: Verify all services are running correctly
6. **Integration Testing**: Run end-to-end tests in staging
7. **Performance Validation**: Check optimization algorithm performance
8. **Rollback Plan**: Prepare rollback procedures if needed

Validation steps:
- Redis connectivity
- MySQL database access
- Celery task queue functionality
- Scryfall API integration
- Web scraping capabilities
- Frontend build integrity

Generate deployment report with health status.
EOF

# Create workflow files
cat > .claude/workflows/optimization-development.md << 'EOF'
# Optimization Algorithm Development Workflow

Complete workflow for developing and improving MTG optimization algorithms:

## Phase 1: Analysis & Planning
1. `/sc:analyze --focus optimization --persona-architect`
2. Review current algorithm performance metrics
3. Identify optimization opportunities
4. Plan algorithm improvements

## Phase 2: Implementation
1. `/sc:design --api --bounded-context --persona-architect` 
2. Implement algorithm improvements
3. `/sc:build --tdd --coverage --persona-backend`
4. Add comprehensive tests

## Phase 3: Validation
1. `/sc:test --integration --performance --persona-qa`
2. Run benchmark comparisons
3. Validate with real buylist data
4. Performance regression testing

## Phase 4: Documentation & Deployment
1. `/sc:document --type technical --persona-scribe`
2. Update algorithm documentation
3. `/sc:deploy --staging --validate --persona-devops`
4. Monitor performance in staging

## Tools & Personas
- 🏗️ architect: System design and trade-offs
- 💻 backend: Algorithm implementation  
- 🧪 qa: Testing and validation
- 📝 scribe: Documentation
- 🚀 devops: Deployment and monitoring
EOF

cat > .claude/workflows/scraper-maintenance.md << 'EOF'
# Web Scraper Maintenance Workflow

Systematic workflow for maintaining and improving MTG card vendor scrapers:

## Phase 1: Health Assessment
1. `/sc:scan --validate --deps --persona-security`
2. Check all vendor scrapers functionality
3. Analyze error rates and patterns
4. Review anti-bot detection incidents

## Phase 2: Issue Resolution  
1. `/sc:troubleshoot --investigate --prod --persona-analyzer`
2. Debug specific scraper failures
3. Update scraper configurations
4. Improve stealth capabilities

## Phase 3: Enhancement
1. `/sc:improve --performance --threshold 95% --persona-performance`
2. Optimize scraping efficiency
3. Add new vendor support
4. Enhance data validation

## Phase 4: Testing & Monitoring
1. `/sc:test --e2e --strict --persona-qa`
2. Validate scraper improvements
3. Set up monitoring alerts
4. Update documentation

## Tools & Personas
- 🔒 security: Anti-bot and compliance
- 🔍 analyzer: Problem investigation
- ⚡ performance: Speed optimization
- 🧪 qa: Testing and validation
EOF

# Create MTG-specific context file
cat > .claude/shared/mtg-context.yml << 'EOF'
# MTG-Specific Context for SuperClaude

mtg_domain:
  card_attributes:
    - name
    - mana_cost
    - type_line
    - set_code
    - rarity
    - price
    - quality_condition
    - language
    - foil_status
  
  optimization_objectives:
    primary: "minimize_total_cost"
    secondary: "minimize_vendor_count"
    tertiary: "maximize_card_quality"
    
  constraints:
    budget: "user_defined_maximum"
    quality: "condition_preferences"
    language: "preferred_languages"
    vendor: "shipping_preferences"

vendor_ecosystem:
  major_vendors:
    - "tcgplayer"
    - "cardkingdom" 
    - "channelfireball"
    - "starcitygames"
    - "coolstuffinc"
  
  scraping_challenges:
    - "anti_bot_detection"
    - "dynamic_content_loading"
    - "rate_limiting"
    - "session_management"
    - "captcha_systems"

algorithm_types:
  exact_methods:
    - "mixed_integer_linear_programming"
    - "constraint_programming"
  
  metaheuristics:
    - "nsga_ii"        # Non-dominated Sorting Genetic Algorithm II
    - "nsga_iii"       # Non-dominated Sorting Genetic Algorithm III  
    - "moead"          # Multi-Objective Evolutionary Algorithm based on Decomposition
    - "hybrid_approaches"

technical_context:
  async_patterns: "throughout_application"
  task_queue: "celery_with_redis"
  optimization_library: "pulp_for_milp_deap_for_evolutionary"
  web_scraping: "selenium_beautifulsoup_cloudscraper"
EOF

# Make setup script executable
chmod +x setup-superclaude.sh

echo ""
echo "🎉 SuperClaude configuration setup complete!"
echo ""
echo "Created files:"
echo "  📁 .claude/project-context.yml      - Main project configuration"
echo "  📁 .claude/commands/optimization/   - Optimization-specific commands"
echo "  📁 .claude/commands/scraping/       - Web scraping commands"
echo "  📁 .claude/commands/testing/        - Testing commands"
echo "  📁 .claude/commands/deployment/     - Deployment commands"
echo "  📁 .claude/workflows/               - Development workflows"
echo "  📁 .claude/shared/mtg-context.yml   - MTG domain context"
echo ""
echo "Next steps:"
echo "  1. Ensure SuperClaude is installed: python3 SuperClaude install"
echo "  2. Start Claude Code in your project directory: claude"
echo "  3. Try optimization commands: /sc:load --deep --summary"
echo "  4. Use workflows: /sc:analyze --focus optimization --persona-architect"
echo ""
echo "Available SuperClaude commands for MTG Optimizer:"
echo "  🎯 /sc:load        - Load project context"
echo "  🔍 /sc:analyze     - Analyze algorithms/scrapers"
echo "  🏗️ /sc:build       - Implement features"
echo "  🧪 /sc:test        - Test algorithms/scrapers"
echo "  📊 /sc:improve     - Optimize performance"
echo "  🚀 /sc:deploy      - Deploy to environments"
echo ""