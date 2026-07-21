# AlphaDesk Portfolio Factor Intelligence

**Status:** Batch 1 shipped (exposures foundation)  
**Scope:** V1 implementation specification  
**Positioning:** An open, transparent multi-factor portfolio analytics system inspired by institutional risk-model architecture. Do not claim equivalence to proprietary Barra, Axioma, or similar commercial models.

## 1. Product Goal

Portfolio Factor Intelligence should explain the underlying sources of portfolio risk and return.

It should answer:

- Which factors is the portfolio exposed to?
- Which holdings create those exposures?
- How much modeled risk comes from common factors versus security-specific risk?
- Which factors drove realized performance?
- How does the portfolio differ from a benchmark?
- What happens under factor and macro stress scenarios?
- How could unwanted exposures be reduced while preserving the investment thesis?

## 2. V1 Scope

V1 focuses on long-only U.S. equities and ETFs.

Core capabilities:

1. Security-level factor exposures
2. Portfolio factor aggregation
3. Factor return estimation
4. Factor covariance estimation
5. Security-specific risk
6. Portfolio risk decomposition
7. Benchmark-relative active risk
8. Factor attribution
9. Factor and historical stress testing
10. Plain-language explanations and Intelligence Cards

## 3. Non-Goals

V1 will not:

- reproduce proprietary Barra or Axioma methodology,
- support all global asset classes,
- model derivatives with full nonlinear Greeks,
- execute trades,
- automatically rebalance portfolios,
- use opaque AI-generated factor exposures,
- optimize taxes or transaction costs,
- calculate intraday risk,
- replace audited institutional risk systems.

## 4. High-Level Architecture

```text
Market, fundamentals, classifications, portfolio data
                         ↓
                Data normalization
                         ↓
            Security characteristics
                         ↓
          Standardized factor exposures
                         ↓
          Factor return estimation
                         ↓
 Factor covariance + security-specific risk
                         ↓
             Versioned factor model
                         ↓
              Portfolio risk engine
                         ↓
 Exposure / risk / attribution / stress APIs
                         ↓
 Web, mobile, Intelligence Cards, Research
```

Suggested module structure:

```text
factor_intelligence/
├── models/
├── data/
├── characteristics/
├── exposures/
├── estimation/
├── covariance/
├── risk/
├── attribution/
├── stress/
├── optimization/
├── api/
├── jobs/
├── validation/
└── tests/
```

Reuse existing AlphaDesk portfolio, security, data-provider, API, job, and visualization abstractions.

## 5. Factor Taxonomy

### Market

- Broad equity market exposure

### Style Factors

Initial V1 factors:

- Size
- Value
- Growth
- Momentum
- Quality
- Profitability
- Leverage
- Low Volatility
- Liquidity
- Dividend Yield

Potential later factors:

- Investment
- Earnings Quality
- Short Interest
- Crowding
- Residual Volatility
- Sentiment
- Analyst Revisions

### Industry Factors

Use the existing AlphaDesk classification hierarchy where possible:

- Sector
- Industry group
- Industry

Industry factors should generally use categorical or binary exposures.

### Macro Sensitivity Factors

Add after the core model is stable:

- Interest-rate sensitivity
- Inflation sensitivity
- USD sensitivity
- Oil sensitivity
- Credit-spread sensitivity
- Economic-growth sensitivity

## 6. Required Data Inputs

### Market Data

- adjusted daily prices,
- total returns,
- market capitalization,
- average daily dollar volume,
- trading history,
- benchmark membership.

### Fundamental Data

- revenue,
- earnings,
- book value,
- assets,
- debt,
- operating income,
- gross profit,
- cash flow,
- dividends,
- analyst estimates when licensed data is available.

### Classification Data

- sector,
- industry,
- security type,
- country,
- currency.

### Portfolio Data

- positions,
- quantities,
- market values,
- cash,
- benchmark,
- effective date.

Every input should include source, effective date, ingestion timestamp, and data-quality status.

## 7. Security Characteristics

Characteristics are raw or transformed measures used to build factor exposures.

```text
Size
- log(market_cap)

Value
- book_to_price
- earnings_yield
- free_cash_flow_yield

Growth
- revenue_growth
- earnings_growth
- forward_growth_estimate

Momentum
- 12_month_return_excluding_recent_month
- 6_month_return
- short_term_reversal

Quality
- return_on_equity
- return_on_assets
- gross_profitability
- earnings_stability

Leverage
- debt_to_assets
- debt_to_equity
- net_debt_to_ebitda

Low Volatility
- historical_volatility
- market_beta
- residual_volatility

Liquidity
- average_daily_dollar_volume
- turnover
- days_traded

Dividend Yield
- trailing_dividend_yield
```

Characteristic calculations must be point-in-time, deterministic, versioned, tested, documented, and protected against look-ahead bias.

## 8. Exposure Construction

For each model date:

1. Calculate raw characteristics.
2. Winsorize extreme values.
3. Standardize within the eligible universe.
4. Apply documented missing-data rules.
5. Combine descriptors into factor scores.
6. Neutralize factors where required.
7. Add industry dummy exposures.
8. Store the security-factor exposure matrix.

Suggested entity:

```text
SecurityFactorExposure
- model_version_id
- effective_date
- security_id
- factor_id
- raw_value
- normalized_exposure
- confidence
- source_quality
```

Missing-data priority:

1. Use valid point-in-time data.
2. Use documented industry-median imputation.
3. Reduce exposure confidence.
4. Exclude low-quality securities from factor-return estimation.
5. Preserve them in portfolio analysis with coverage warnings.

## 9. Factor Return Estimation

Estimate daily factor returns using cross-sectional regression of security returns against prior-period factor exposures.

```text
security return
    =
factor exposures × factor returns
    +
specific return
```

V1 requirements:

- weighted least squares,
- market-cap or robust regression weights,
- style and industry factors,
- outlier controls,
- minimum universe coverage,
- diagnostics,
- residual storage,
- no future information.

Suggested entity:

```text
FactorReturn
- model_version_id
- factor_id
- return_date
- factor_return
- standard_error
- t_statistic
- observation_count
- regression_quality
```

## 10. Factor Covariance

Estimate factor covariance using a rolling history of factor returns.

V1 approach:

- exponentially weighted covariance,
- configurable half-life,
- shrinkage toward a stable target,
- annualization,
- positive-semidefinite validation.

Suggested entity:

```text
FactorCovariance
- model_version_id
- effective_date
- factor_id_1
- factor_id_2
- covariance
```

Requirements:

- symmetric matrix,
- positive semidefinite,
- positive diagonal,
- versioned parameters,
- failed validation blocks model activation.

## 11. Security-Specific Risk

Estimate security-specific risk from residual returns.

V1 approach:

- exponentially weighted residual variance,
- minimum observation threshold,
- shrinkage toward industry or universe estimates,
- confidence adjustment,
- annualization.

Suggested entity:

```text
SecuritySpecificRisk
- model_version_id
- effective_date
- security_id
- specific_variance
- specific_volatility
- observation_count
- confidence
```

## 12. Factor Model Versioning

Every analysis must reference an immutable model version.

```text
FactorModelVersion
- id
- name
- version
- universe
- effective_date
- methodology_version
- data_cutoff
- factor_definitions
- estimation_parameters
- status
- created_at
```

Statuses:

```text
BUILDING
VALIDATING
ACTIVE
FAILED
ARCHIVED
```

Never overwrite a historical model version.

## 13. Portfolio Factor Exposure

```text
portfolio factor exposure
    =
sum(position weight × security factor exposure)
```

Support:

- portfolio exposure,
- benchmark exposure,
- active exposure,
- unmodeled holdings,
- cash,
- coverage percentage.

Suggested entity:

```text
PortfolioFactorExposure
- portfolio_id
- model_version_id
- effective_date
- factor_id
- portfolio_exposure
- benchmark_exposure
- active_exposure
- coverage
```

## 14. Portfolio Risk Decomposition

Calculate:

- total modeled variance,
- total modeled volatility,
- common-factor variance,
- specific variance,
- marginal contribution to risk,
- component contribution to risk,
- percentage contribution to risk,
- contribution by factor,
- contribution by holding.

Conceptually:

```text
portfolio variance
    =
factor exposure × factor covariance × factor exposure
    +
weighted specific variance
```

Suggested outputs:

```text
PortfolioRiskResult
- portfolio_id
- model_version_id
- effective_date
- total_variance
- total_volatility
- factor_variance
- specific_variance
- coverage
```

```text
FactorRiskContribution
- factor_id
- exposure
- marginal_risk
- component_risk
- percentage_of_total_risk
```

```text
SecurityRiskContribution
- security_id
- portfolio_weight
- marginal_risk
- component_risk
- percentage_of_total_risk
```

Risk contributions must reconcile to total modeled risk within tolerance.

## 15. Benchmark-Relative Active Risk

When a benchmark is selected, calculate:

- active weights,
- active factor exposures,
- tracking error,
- factor contribution to tracking error,
- specific contribution to tracking error,
- holdings driving active risk.

Example:

> Relative to SPY, the portfolio’s active risk is primarily driven by overweight Technology, Growth, Momentum, and AMD-specific risk.

## 16. Performance Attribution

Explain realized return using:

```text
factor contribution
    =
portfolio factor exposure × realized factor return
```

Include:

- factor contribution,
- specific contribution,
- total explained return,
- unexplained residual,
- benchmark-relative attribution.

Support:

- daily,
- monthly,
- quarter-to-date,
- year-to-date,
- custom periods.

Clearly distinguish predicted risk contribution from realized return attribution.

## 17. Stress Testing

### Factor Shocks

Examples:

- Market: -10%
- Momentum: -2 standard deviations
- Growth: -2 standard deviations
- Value: +2 standard deviations
- Volatility: +3 standard deviations

### Historical Scenarios

Potential scenarios:

- COVID crash,
- 2022 rate shock,
- 2008 financial crisis,
- inflation shock,
- technology selloff.

Historical scenarios must have documented dates and mappings.

### Custom Scenario

```json
{
  "MARKET": -0.08,
  "GROWTH": -0.04,
  "MOMENTUM": -0.03,
  "TECHNOLOGY": -0.06
}
```

Results should show:

- estimated portfolio impact,
- contribution by factor,
- contribution by holding,
- model uncertainty,
- coverage limitations.

Stress results are scenarios, not forecasts.

## 18. Optimization Interface

Optimization is a later extension.

Potential objectives:

- minimize total risk,
- minimize active risk,
- reduce selected factor exposure,
- preserve target holdings,
- reach a target factor profile.

Potential constraints:

- maximum position weight,
- turnover limit,
- sector bounds,
- factor bounds,
- benchmark-relative bounds,
- minimum holdings,
- restricted securities,
- tax-lot constraints later.

The optimizer must consume the risk-model interface instead of duplicating calculations.

## 19. Core Domain Models

```text
FactorDefinition
FactorDescriptorDefinition
FactorModelVersion
SecurityCharacteristic
SecurityFactorExposure
FactorReturn
FactorCovariance
SecuritySpecificRisk
PortfolioFactorExposure
PortfolioRiskResult
FactorRiskContribution
SecurityRiskContribution
FactorAttributionResult
StressScenario
StressScenarioResult
```

### FactorDefinition

```text
- id
- code
- name
- category
- description
- exposure_type
- unit
- status
```

Categories:

```text
MARKET
STYLE
SECTOR
INDUSTRY
COUNTRY
CURRENCY
MACRO
```

Exposure types:

```text
CONTINUOUS
CATEGORICAL
BINARY
```

## 20. Services

### FactorDataService

Provides point-in-time market, fundamental, classification, and benchmark data.

### CharacteristicEngine

Calculates raw security characteristics.

### ExposureEngine

Normalizes characteristics and builds security factor exposures.

### FactorReturnEstimator

Runs cross-sectional regressions and stores factor returns and residuals.

### RiskModelEstimator

Builds covariance and specific-risk estimates.

### PortfolioFactorService

Aggregates security exposures into portfolio and active exposures.

### PortfolioRiskService

Calculates total, factor, specific, marginal, and component risk.

### AttributionService

Calculates factor and specific realized-return attribution.

### StressTestService

Applies factor, macro, custom, and historical shocks.

### FactorExplanationService

Produces plain-language explanations from deterministic outputs. AI must never invent exposures, contributions, or risk values.

## 21. API Design

```http
GET /api/v1/factor-models
GET /api/v1/factor-models/{version_id}
GET /api/v1/factors
```

```http
GET /api/v1/portfolios/{portfolio_id}/factor-exposures
```

Parameters:

```text
as_of
model_version
benchmark_id
```

```http
GET /api/v1/portfolios/{portfolio_id}/factor-risk
GET /api/v1/portfolios/{portfolio_id}/active-risk
GET /api/v1/portfolios/{portfolio_id}/factor-attribution
```

Attribution parameters:

```text
start_date
end_date
benchmark_id
model_version
```

```http
POST /api/v1/portfolios/{portfolio_id}/stress-tests
```

Example request:

```json
{
  "scenario_id": "growth-selloff",
  "factor_shocks": {
    "MARKET": -0.08,
    "GROWTH": -0.04,
    "MOMENTUM": -0.03
  }
}
```

## 22. Pipeline and Scheduling

```text
Market-data ingestion
        ↓
Fundamental/classification refresh
        ↓
Characteristic calculation
        ↓
Exposure generation
        ↓
Factor-return estimation
        ↓
Covariance and specific-risk update
        ↓
Validation
        ↓
Model activation
        ↓
Portfolio analysis refresh
```

Requirements:

- idempotent jobs,
- retry-safe stages,
- lineage metadata,
- immutable model versions,
- validation gates,
- failure alerts,
- no partial activation.

## 23. Validation

### Exposure Validation

- distribution checks,
- missing-data rates,
- factor correlations,
- outlier rates,
- industry neutrality where required,
- coverage thresholds.

### Regression Validation

- observation count,
- multicollinearity,
- residual distribution,
- factor-return stability,
- condition number,
- explanatory power.

### Covariance Validation

- symmetry,
- positive semidefinite,
- diagonal positivity,
- stable eigenvalues,
- reasonable annualized volatility.

### Portfolio Validation

- weights reconcile,
- coverage is disclosed,
- risk contributions reconcile,
- benchmark weights reconcile,
- active weights behave correctly.

## 24. Caching and Reproducibility

Cache key:

```text
portfolio_id
portfolio_snapshot_id
benchmark_id
model_version_id
effective_date
analysis_type
parameters_hash
```

Every result must be reproducible from:

- portfolio snapshot,
- benchmark snapshot,
- model version,
- data cutoff,
- calculation parameters.

## 25. User Interface

Recommended page sections:

1. Risk summary
2. Factor exposure profile
3. Factor contribution to risk
4. Holdings driving exposure
5. Active exposure versus benchmark
6. Return attribution
7. Stress tests
8. Coverage and methodology

Required visualizations:

- horizontal factor exposure bars,
- portfolio-versus-benchmark exposure bars,
- factor contribution-to-risk waterfall,
- common versus specific risk donut,
- holding contribution-to-risk bars,
- factor correlation heatmap,
- risk-versus-return scatter,
- attribution over time,
- scenario-loss waterfall,
- exposure history lines.

Use the shared AlphaDesk `ChartSpec` and visualization design language.

Selecting a factor should reveal:

- definition,
- portfolio exposure,
- benchmark exposure,
- active exposure,
- risk contribution,
- recent factor performance,
- holdings driving exposure,
- related Intelligence Cards,
- Learn More content.

## 26. Intelligence Integration

Generate Intelligence Cards for changes such as:

- Growth exposure increased materially.
- AMD now contributes more than 20% of modeled risk.
- Security-specific risk rose above a threshold.
- Active Technology exposure exceeded a user limit.
- Momentum was the largest negative contributor this month.
- Stress loss under a rate shock increased materially.

Every card should contain:

- deterministic evidence,
- why it matters,
- factors and holdings involved,
- model version,
- confidence and coverage,
- link to the analysis page.

## 27. Knowledge & Context Integration

Every factor should link to a concept.

Example:

```text
Momentum

TL;DR:
Securities with strong intermediate-term performance have sometimes continued
to outperform, though momentum can reverse sharply.

Your portfolio:
AMD and NVDA create most of your positive Momentum exposure.

Risk implication:
Momentum accounts for 14% of modeled portfolio variance.
```

LLMs may translate structured model results into plain language but must cite the underlying calculated outputs.

## 28. Observability

Events:

```text
factor_model_build_started
factor_model_build_completed
factor_model_build_failed
factor_analysis_viewed
factor_drilldown_opened
stress_test_run
benchmark_changed
factor_alert_created
factor_explanation_opened
```

Operational metrics:

- data freshness,
- security coverage,
- model-build duration,
- failed calculations,
- covariance validation failures,
- API latency,
- cache hit rate,
- portfolio value modeled.

## 29. Testing

### Unit Tests

- descriptor calculations,
- winsorization,
- standardization,
- missing-data handling,
- exposure aggregation,
- covariance calculations,
- specific-risk calculations,
- marginal and component risk,
- attribution reconciliation,
- stress calculations.

### Property Tests

- covariance symmetry,
- positive-semidefinite output,
- risk contribution reconciliation,
- invariance to equivalent portfolio scaling,
- deterministic output for identical inputs.

### Integration Tests

- end-to-end model build,
- model activation,
- exposure API,
- risk API,
- active risk,
- attribution,
- stress tests,
- caching and version selection.

### Backtests

- exposure stability,
- factor-return behavior,
- realized versus predicted volatility,
- forecast bias,
- coverage history,
- exposure turnover.

## 30. Limitations and Disclosures

The product must state:

- This is an AlphaDesk model, not Barra or Axioma.
- Factor definitions may differ from commercial systems.
- Results are estimates based on available data.
- Missing data and model coverage affect accuracy.
- Factor relationships change over time.
- Stress tests are scenarios, not forecasts.
- Unmodeled risks may be material.
- Results are research and decision-support tools, not investment advice.

## 31. Phased Implementation

### Batch 1 — Factor Foundation

Implement:

1. Factor definitions and immutable model versions
2. Point-in-time characteristic engine
3. Exposure normalization pipeline
4. Security and portfolio factor-exposure APIs

Initial factors:

- Size
- Value
- Growth
- Momentum
- Quality
- Low Volatility
- Liquidity
- Sector/industry

Deliverable:

A user can inspect transparent security and portfolio factor exposures.

### Batch 2 — Risk Model

Implement:

1. Daily factor-return estimation
2. Factor covariance estimation
3. Security-specific risk
4. Portfolio risk decomposition

Deliverable:

A user can see total modeled volatility, common-factor risk, specific risk, and contributions by factor and holding.

### Batch 3 — Benchmark and Attribution

Implement:

1. Benchmark exposure
2. Active risk and tracking error
3. Realized factor attribution
4. Factor and holding drill-down UI

### Batch 4 — Stress and Intelligence

Implement:

1. Factor shocks
2. Historical and custom scenarios
3. Factor-change Intelligence Cards
4. Knowledge & Context integration

### Batch 5 — Optimization

Implement later:

1. Optimization service contract
2. Factor constraints
3. Turnover and position constraints
4. Proposed-trade comparison

Do not implement automatic execution.

## 32. V1 Acceptance Criteria

V1 is complete when:

- point-in-time exposures are available for supported U.S. equities,
- portfolio exposures reconcile to security weights,
- model versions are reproducible,
- covariance and specific risk pass validation,
- total risk decomposes into common and specific risk,
- factor and security risk contributions reconcile,
- benchmark-relative active risk is available,
- realized factor attribution is available,
- stress scenarios can be run,
- coverage and limitations are visible,
- results integrate with AlphaDesk visualizations and Intelligence Cards.

## 33. Cursor Execution Guidance

1. Reuse existing AlphaDesk portfolio, security, data-provider, job, API, and visualization abstractions.
2. Do not create a second portfolio model.
3. Use point-in-time data and prevent look-ahead bias.
4. Keep factor calculations deterministic.
5. Version methodology, parameters, data cutoff, and outputs.
6. Keep model calculations separate from AI explanations.
7. Add tests with every batch.
8. Implement only the current 3–4 target batch.
9. Do not claim commercial-model equivalence.
10. Document assumptions and limitations.

Recommended first implementation target:

```text
1. Define FactorDefinition and FactorModelVersion
2. Implement characteristics for the eight initial factors
3. Build normalization and exposure generation
4. Add security and portfolio factor-exposure APIs
```

Do not begin covariance, specific risk, attribution, stress testing, or optimization until the exposure foundation is validated.
