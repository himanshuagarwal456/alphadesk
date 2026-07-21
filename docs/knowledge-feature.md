Implement the **Learn More / Knowledge & Context** feature for AlphaDesk using the existing repository architecture and conventions.

## Product Description

AlphaDesk should not become a financial encyclopedia.

The purpose of Learn More is to help the user understand:

- what a financial concept means,
- why it matters for the current Intelligence Card, company, thesis, holding, or portfolio,
- and where to find trusted external reading.

Example:

```text
Intelligence Card:
AMD gross margin improved.

Learn More:
- What gross margin means
- Why it matters for AMD
- How it affects the user's thesis
- Related concepts
- Trusted external resources
```

AlphaDesk should create its own concise explanations. External publishers such as SEC Investor.gov, FINRA, CFA Institute, Investopedia, and company filings should be linked as resources. Do not scrape or republish article bodies.

## Architecture

### Concept

Represents a financial concept.

```text
Concept
- id
- slug
- title
- short_definition
- beginner_explanation
- intermediate_explanation
- advanced_explanation
- quant_explanation
- difficulty
- estimated_read_time
- tags
- status
- version
```

Examples:

- Gross Margin
- Free Cash Flow
- Concentration Risk
- Volatility
- Operating Leverage
- Pricing Power

### Knowledge Resource

Represents an external learning resource.

```text
KnowledgeResource
- id
- title
- provider
- url
- resource_type
- difficulty
- estimated_read_time
- access_type
- quality_score
- last_verified_at
- status
```

Store metadata and outbound links only.

### Concept–Resource Relationship

```text
ConceptResource
- concept_id
- resource_id
- relevance_score
- display_order
```

### Intelligence Card–Concept Relationship

```text
IntelligenceCardConcept
- intelligence_card_id
- concept_id
- relevance_score
- context_reason
- display_order
```

This allows an Intelligence Card to expose one or more related concepts without changing the existing card-generation architecture.

### User Learning Progress

```text
UserConceptProgress
- user_id
- concept_id
- view_count
- first_viewed_at
- last_viewed_at
- status
- saved
```

Statuses:

```text
NOT_STARTED
VIEWED
COMPLETED
```

### Knowledge Context Service

Create a service responsible for building the Learn More response.

Inputs may include:

```text
user_id
concept_id
intelligence_card_id
holding_id
portfolio_id
research_id
```

Output:

```text
KnowledgeContext
- concept
- personalized_explanation
- why_it_matters
- portfolio_example
- related_concepts
- external_resources
- user_progress
```

Canonical concept definitions should be stored in the database.

Only contextual sections such as `why_it_matters` and `portfolio_example` may later be generated dynamically using the Investor Profile and available portfolio evidence.

## User Experience

Add a **Learn More** action to Intelligence Cards.

Open the content in a drawer or side panel containing:

```text
Concept title

TL;DR

Why it matters here

Personalized explanation

Portfolio or company example

Related concepts

Further reading

Save / Mark complete
```

The backend, not the frontend, should choose the appropriate explanation level.

Future controls may include:

```text
Explain more simply
Explain in more depth
Show the math
```

## Initial Implementation

Start with approximately 20 core concepts covering:

- portfolio risk,
- company fundamentals,
- valuation,
- research quality,
- investment thesis and catalysts.

Implement the feature by extending existing AlphaDesk models, APIs, services, and UI patterns. Avoid parallel abstractions and unrelated refactoring.