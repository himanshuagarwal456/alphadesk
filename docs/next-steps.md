AlphaDesk — Product and Implementation Brief

1. Product Goal

AlphaDesk is an AI-native investment intelligence platform for serious self-directed investors.

Its core job is to answer:

1. What changed?
2. Why does it matter to my portfolio?
3. Does it change my thesis, conviction, risk, or expected return?
4. What should I investigate or do next?

AlphaDesk should not behave like a generic chatbot, stock-picking tool, or chronological news feed.

The long-term product vision is:

Institutional-style investment intelligence personalized to an individual investor’s portfolio, theses, and trusted information sources.

⸻

2. Initial End User

Primary user:

* Self-directed investor
* Approximately $100K–$5M invested
* 10–40 meaningful positions
* Uses stocks, ETFs, and possibly options
* Reads earnings, news, newsletters, social media, and research
* Maintains opinions or investment theses
* Does not have time to continuously monitor every source
* Wants evidence-backed portfolio-specific intelligence

Do not initially optimize for:

* Passive index-only investors
* Day traders
* Absolute beginners
* Large institutional hedge funds

Future expansion users:

* Investment clubs
* RIAs
* Small family offices
* Boutique investment firms
* Professional research teams

⸻

3. Core Product Experience

The main product surface should be called Intelligence, not Feed.

Primary navigation:

* Intelligence
* Portfolio
* Narratives
* Research
* Workbench

Intelligence

A personalized stream of:

* Raw evidence
* AI-augmented evidence
* AlphaDesk-generated conclusions
* Thesis changes
* Portfolio risks
* Catalysts
* Opportunities
* Monitoring alerts

The stream should be ranked by:

* Portfolio relevance
* Materiality
* Evidence quality
* Novelty
* Confidence
* Narrative importance
* Freshness

It should not be primarily chronological.

⸻

4. Intelligence Card Model

Every card should answer one primary question:

* What happened?
* Why?
* Why do I care?
* What changed?
* What should I watch?
* What action deserves consideration?

Recommended card structure:

Headline
One primary visualization
Concise explanation
Portfolio impact
Thesis impact
Confidence
Evidence and sources
Next action

Cards should support drill-down into:

* Underlying evidence
* Related companies
* Related narratives
* Historical changes
* Agent reasoning summary
* Source provenance

⸻

5. Evidence and Reasoning Layers

Maintain a strict separation between three layers.

Layer 1 — Evidence

Ground-truth material:

* SEC filings
* Earnings transcripts
* Company presentations
* Market data
* Macro data
* News
* Research reports
* Podcasts
* Social media
* User documents
* Notes
* Spreadsheets

Layer 2 — Augmentation

AI may:

* Summarize
* Extract entities
* Extract metrics
* Build timelines
* Tag narratives
* Normalize events
* Generate charts
* Identify relationships

This layer should not invent investment conclusions.

Layer 3 — Intelligence

Reasoning over evidence to produce:

* Thesis strengthening or weakening
* Portfolio impact
* Risk changes
* Catalyst updates
* Opportunity detection
* Suggested investigation
* Potential actions

Every intelligence claim must reference supporting evidence.

⸻

6. Core Domain Objects

Portfolio

interface Portfolio {
  id: string;
  name: string;
  accounts: Account[];
  positions: Position[];
  cashBalances: CashBalance[];
  createdAt: string;
  updatedAt: string;
}

Position

interface Position {
  id: string;
  portfolioId: string;
  instrumentId: string;
  quantity: number;
  averageCost?: number;
  marketValue?: number;
  portfolioWeight?: number;
  thesisIds: string[];
  openedAt?: string;
  status: "active" | "closed" | "watchlist";
}

Thesis

interface Thesis {
  id: string;
  title: string;
  description: string;
  status: "draft" | "active" | "weakened" | "invalidated" | "closed";
  confidence: number;
  priorConfidence?: number;
  supportingEvidenceIds: string[];
  opposingEvidenceIds: string[];
  relatedInstrumentIds: string[];
  relatedNarrativeIds: string[];
  catalystIds: string[];
  invalidationConditionIds: string[];
  expectedReturn?: number;
  timeHorizon?: string;
  createdAt: string;
  updatedAt: string;
}

Evidence

interface Evidence {
  id: string;
  providerId: string;
  sourceType: string;
  sourceUrl?: string;
  title: string;
  publishedAt?: string;
  retrievedAt: string;
  rawContentRef?: string;
  summary?: string;
  entityIds: string[];
  narrativeIds: string[];
  eventIds: string[];
  sourceQualityScore?: number;
  freshnessScore?: number;
  licenseMetadata?: LicenseMetadata;
}

Narrative

interface Narrative {
  id: string;
  title: string;
  description?: string;
  parentNarrativeId?: string;
  childNarrativeIds: string[];
  relatedInstrumentIds: string[];
  relatedEventIds: string[];
  relatedThesisIds: string[];
  strengthScore?: number;
  momentumScore?: number;
  createdAt: string;
  updatedAt: string;
}

Intelligence Card

interface IntelligenceCard {
  id: string;
  cardType:
    | "event"
    | "explanation"
    | "portfolio_impact"
    | "thesis_change"
    | "risk"
    | "catalyst"
    | "opportunity"
    | "watch_item";
  headline: string;
  summary: string;
  portfolioId?: string;
  positionIds: string[];
  thesisIds: string[];
  narrativeIds: string[];
  evidenceIds: string[];
  confidence: number;
  materialityScore: number;
  relevanceScore: number;
  noveltyScore: number;
  visualizationIntent?: VisualizationIntent;
  suggestedActions?: SuggestedAction[];
  createdAt: string;
}

⸻

7. Visualization System

Do not allow LLMs to generate arbitrary charts directly.

Use this pipeline:

Evidence
→ Structured facts
→ Visualization intent
→ Deterministic chart selection
→ Validated chart specification
→ Rendered card

Visualization Intent

interface VisualizationIntent {
  analyticalQuestion:
    | "trend"
    | "comparison"
    | "composition"
    | "relationship"
    | "distribution"
    | "change"
    | "flow"
    | "timeline"
    | "geography"
    | "risk"
    | "scenario";
  entities: string[];
  metrics: MetricReference[];
  dimensions: string[];
  timeWindow?: TimeWindow;
  comparisonMode?: string;
  preferredTemplate?: string;
  explanation?: string;
}

Basic chart-selection rules

Time trend                  → line chart
Categorical comparison      → bar chart
Ranked comparison           → horizontal bar chart
Composition over time       → stacked bar or stacked area
Single-period composition   → treemap, bar, or limited pie
Two-variable relationship   → scatter plot
Distribution                → histogram or box plot
Change between two periods  → slope chart or variance bar
Bridge from old to new      → waterfall
Portfolio concentration     → treemap or ranked bar
Correlation matrix          → heatmap
Options chain               → heatmap
Narrative evolution         → timeline
Supply chain                → network or Sankey
Scenario comparison         → table or small multiples
Geographic exposure         → map

Chart validation rules

Before rendering, validate:

* Axis units
* Date ordering
* Currency consistency
* Percentage scaling
* Missing data
* Sample size
* Source timestamps
* Baseline selection
* Whether dual axes are necessary
* Whether chart type matches the analytical question
* Whether the chart exaggerates differences
* Whether a table would be clearer

Default to one primary chart per card.

Use domain templates instead of arbitrary layouts:

* Earnings
* Company
* Macro
* Portfolio
* Risk
* Narrative
* Options
* Supply chain
* ETF
* Scenario
* Thesis evolution

⸻

8. Knowledge Providers

Treat every source as a pluggable knowledge provider.

interface KnowledgeProvider {
  id: string;
  name: string;
  providerType: "free" | "paid" | "user_owned" | "private";
  search(query: ProviderQuery): Promise<ProviderResult[]>;
  fetch(ref: ProviderReference): Promise<ProviderDocument>;
  normalize(document: ProviderDocument): Promise<Evidence[]>;
  getLicenseMetadata(): Promise<LicenseMetadata>;
  healthCheck(): Promise<ProviderHealth>;
}

Initial provider categories:

Public

* SEC
* FRED
* Company investor-relations sites
* Public market data
* RSS feeds
* Public news

User-owned

* Uploaded PDFs
* Google Drive
* Email newsletters
* Notes
* Spreadsheets
* Saved web pages

Paid subscriptions

Future support may include user-authorized access to:

* Seeking Alpha
* Tegus
* AlphaSense
* BamSEC
* FactSet
* Capital IQ
* Research newsletters
* Alternative-data providers

Important:

* Do not bypass publisher authentication or licensing.
* Track source ownership and licensing.
* Prevent unauthorized redistribution.
* Preserve provenance on all derived content.

Long-term possibility:

* Dataset and knowledge-provider marketplace
* Provider SDK
* Revenue sharing
* Private providers
* Community-built connectors

Do not build the marketplace before the provider abstraction is stable.

⸻

9. Living Thesis and Position Lifecycle

AlphaDesk should model positions, not only securities.

Lifecycle:

Idea
→ Research
→ Thesis
→ Position
→ Monitoring
→ Thesis updates
→ Resize / hedge / hold / exit
→ Post-decision review

The product should continuously evaluate:

* What changed?
* Has expected return changed?
* Has risk changed?
* Has valuation changed?
* Has consensus changed?
* Has the narrative strengthened or weakened?
* Has an invalidation condition triggered?
* Does the position still deserve its current size?

⸻

10. Decision Journal

Every meaningful user decision should create a journal record.

interface DecisionJournalEntry {
  id: string;
  portfolioId: string;
  positionId?: string;
  thesisId?: string;
  decisionType:
    | "open"
    | "add"
    | "trim"
    | "hold"
    | "hedge"
    | "close"
    | "watch";
  rationale: string;
  confidence?: number;
  expectedReturn?: number;
  timeHorizon?: string;
  evidenceIds: string[];
  catalystIds: string[];
  riskIds: string[];
  invalidationConditionIds: string[];
  decidedAt: string;
}

Future reviews should compare:

* Original thesis
* Current thesis
* Confidence change
* Catalysts realized
* Risks realized
* Outcome
* Decision quality independent of outcome

⸻

11. Recommended Near-Term Roadmap

Milestone 1 — Core Intelligence Loop

Build:

* Portfolio import or manual portfolio creation
* Positions
* Thesis creation
* Evidence ingestion from a small set of providers
* Basic intelligence-card generation
* Portfolio-aware ranking
* Evidence drill-down

Success condition:

A user can import a portfolio and receive useful, evidence-backed cards explaining what changed and why it matters.

Milestone 2 — Living Thesis

Build:

* Thesis objects
* Supporting and opposing evidence
* Catalysts
* Invalidation conditions
* Confidence history
* Thesis diff
* Position-to-thesis relationships

Success condition:

A user can understand how and why a thesis changed over time.

Milestone 3 — Visualization Engine

Build:

* Visualization intent schema
* Deterministic chart selector
* Chart-spec validator
* Initial templates:
    * earnings
    * company
    * portfolio
    * macro
    * thesis
* One-chart-per-card rendering

Success condition:

Charts are consistently appropriate, readable, and traceable to source data.

Milestone 4 — Decision Journal

Build:

* Decision entry creation
* Position lifecycle events
* Decision review
* Thesis state at decision time

Success condition:

Users can review not only portfolio performance, but how their reasoning evolved.

Milestone 5 — User-Owned Sources

Build:

* Provider abstraction
* File upload
* PDF and document ingestion
* Google Drive or newsletter connector
* Provenance and permissions

Success condition:

AlphaDesk can reason across both public evidence and the user’s private research.

⸻

12. Suggested Repository Documentation

Create or maintain:

docs/
  product.md
  architecture.md
  roadmap.md
  visualization-system.md
  data-provider-model.md
  thesis-and-position-model.md
  anti-goals.md
  next-steps.md

docs/product.md

Contains:

* Product vision
* Target user
* Primary jobs-to-be-done
* Core UX
* Product principles

docs/architecture.md

Contains:

* System components
* Service boundaries
* Domain entities
* Event flows
* Storage decisions
* Agent orchestration
* Provenance model

docs/roadmap.md

Contains:

* Ordered milestones
* Current milestone
* Dependencies
* Definition of done
* Deferred work

docs/anti-goals.md

AlphaDesk is not:

* A high-frequency trading system
* An autonomous execution bot
* A generic financial chatbot
* A social investing network
* A stock-tip application
* A replacement for all institutional terminals
* A system that hides evidence behind unexplained AI output
* A marketplace before the provider layer is proven
* A product optimized for every retail investor

⸻

13. Architecture Principles

1. Evidence must be immutable or versioned.
2. AI-derived claims must reference evidence.
3. Agents should output structured contracts.
4. Agents should not directly render UI.
5. Chart selection should be deterministic where possible.
6. Portfolio, thesis, evidence, and narrative objects should remain separate.
7. All generated intelligence should be reproducible or auditable.
8. Provider licensing and permissions must propagate to derived content.
9. User-specific private data must never leak across tenants.
10. Generated recommendations should be framed as decision support, not autonomous investment advice.

⸻

14. Open Questions for Repository Review

The Cursor agent should inspect the current repository and answer:

1. What is the existing frontend and backend stack?
2. Where are agent outputs currently defined?
3. Are agent responses structured or primarily prose?
4. What portfolio and position models already exist?
5. Is there an event or job-processing layer?
6. How is generated feed content stored?
7. What visualization library is currently used?
8. Are charts generated from validated data or directly from model output?
9. What data providers are currently integrated?
10. Is source provenance stored?
11. Is there already a thesis or research-session model?
12. What parts of this brief conflict with the existing architecture?
13. What is the smallest milestone that can be implemented without large refactoring?
14. Which files should change first?
15. What technical debt would block the living-thesis or visualization systems?

⸻

15. Immediate Cursor Task

Review this brief against the repository.

Produce:

1. Current-state architecture summary
2. Gap analysis
3. Conflicts with existing implementation
4. Recommended implementation sequence
5. Exact files to add or modify
6. Proposed schemas and migrations
7. Tests required
8. First implementation PR scope

Do not immediately rewrite the entire system.

Prefer the smallest vertical slice that demonstrates:

Evidence
→ Portfolio relevance
→ Structured intelligence card
→ Correct visualization
→ Source drill-down

The first PR should be independently testable and should move the repository toward the long-term architecture without requiring a full migration.