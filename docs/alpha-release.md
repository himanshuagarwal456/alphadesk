# AlphaDesk Alpha Product Delivery Plan

**Version:** 1.0  
**Target:** Invite-only alpha release  
**Product category:** AI-native portfolio intelligence and investment research  
**Primary users:** Serious self-directed investors managing concentrated portfolios  
**Initial asset coverage:** US-listed equities and ETFs  
**Product mode:** Research and decision support only; no automated trade execution

---

# 1. Alpha Objective

The AlphaDesk alpha should allow an invited user to:

1. Create an account and private workspace.
2. Import or manually create a portfolio and watchlist.
3. Run institutional-style research on a company.
4. See the evidence supporting every material conclusion.
5. Create and maintain a living investment thesis.
6. Upload private research documents and connect them to a thesis.
7. Receive intelligence when new information materially changes a thesis.
8. Record an investment decision and later review its outcome.
9. Inspect portfolio exposure, concentration, risks, and affected positions.
10. Submit feedback from inside the product.

The alpha is successful when AlphaDesk becomes part of a user’s recurring investment workflow—not merely something they run once to generate a report.

---

# 2. Alpha Product Promise

> AlphaDesk continuously connects market evidence to your portfolio, maintains your investment theses, and tells you what materially changed and why it matters.

The product should not be positioned as:

- An autonomous trading system.
- A stock-picking chatbot.
- A brokerage replacement.
- A financial adviser.
- A stream of generic market news.
- A collection of disconnected AI agents.

The product should be positioned as a **portfolio intelligence workspace**.

---

# 3. Alpha Scope

## Included

- Invite-only authentication.
- Private user workspaces.
- Portfolio CSV import.
- Manual portfolio and watchlist editing.
- US equities and ETFs.
- On-demand company research.
- Market, sentiment, news, SEC, fundamentals, bull/bear, and risk analysis.
- Source and evidence provenance.
- Living theses and revision history.
- Decision journal.
- Material-change monitoring.
- Intelligence cards and notifications.
- Private PDF, Markdown, text, and CSV research uploads.
- Persistent web application.
- Basic portfolio exposure and concentration analysis.
- Admin operations and product analytics.
- Cost, latency, quality, and failure monitoring.

## Explicitly excluded from the first alpha

- Trade execution.
- Brokerage account synchronization.
- Options strategy generation.
- Options chains and Greeks.
- Full historical backtesting.
- Portfolio optimization or automatic rebalancing.
- Intraday real-time monitoring.
- Native mobile applications.
- Social/community features.
- Team collaboration.
- International exchanges.
- Cryptocurrency.
- Tax-lot optimization.
- Financial-planning workflows.
- A generalized public knowledge graph UI.

These can follow once alpha users demonstrate sustained engagement with the core intelligence loop.

---

# 4. Core User Journeys

## Journey 1: Onboarding

1. User receives an invitation.
2. User creates an account.
3. User accepts research-only terms and disclosures.
4. User creates a workspace.
5. User imports a broker CSV or creates a portfolio manually.
6. AlphaDesk validates symbols, quantities, prices, and average costs.
7. User reviews and confirms the imported portfolio.
8. AlphaDesk creates an initial portfolio overview.
9. User selects which holdings should receive monitoring.

### Acceptance criteria

- A new user can reach a populated portfolio in under 10 minutes.
- Import errors identify the row and corrective action.
- No portfolio becomes active until the user confirms the import.
- User data is isolated from every other workspace.

---

## Journey 2: Research a Company

1. User opens a holding or watchlist company.
2. User selects **Run Research**.
3. AlphaDesk creates a durable research job.
4. Agents collect market, fundamental, sentiment, news, SEC, and macro evidence.
5. Bull, bear, trader, and risk stages reason over structured evidence.
6. AlphaDesk creates:
   - Research summary.
   - Bull case.
   - Bear case.
   - Catalysts.
   - Risks.
   - Valuation or price scenarios.
   - Final rating.
   - Evidence citations.
7. User can inspect each cited source.
8. User can create or update a thesis from the result.

### Acceptance criteria

- Every material factual claim is supported by one or more evidence records.
- Research progress survives browser refresh.
- Failed providers do not destroy the entire run when acceptable alternatives exist.
- The system distinguishes “data unavailable” from an actual zero or negative finding.
- Structured output remains canonical; Markdown is generated only for display or export.

---

## Journey 3: Maintain a Living Thesis

1. User creates a thesis from a completed research run.
2. AlphaDesk proposes:
   - Core thesis.
   - Bull case.
   - Bear case.
   - Catalysts.
   - Risks.
   - Invalidation conditions.
   - Expected horizon.
   - Confidence.
3. User edits and approves the thesis.
4. Each subsequent research run or material event creates a proposed revision.
5. User can compare revisions.
6. The system records which evidence caused each revision.
7. User can accept, reject, or edit the proposed change.

### Acceptance criteria

- No existing thesis is silently overwritten.
- Every revision has a timestamp, author, reason, and evidence set.
- User-authored text remains distinguishable from AI-authored text.
- Rejected revisions remain available in the audit history.
- A thesis can be active, under review, invalidated, exited, or archived.

---

## Journey 4: Intelligence Monitoring

1. AlphaDesk polls supported sources for monitored holdings.
2. New items are deduplicated and normalized into evidence.
3. A materiality classifier determines whether the information may affect an existing thesis.
4. Only affected theses receive targeted re-analysis.
5. AlphaDesk creates an Intelligence Card when something meaningful changed.
6. User sees:
   - What changed.
   - Why it matters.
   - Which evidence supports it.
   - Which thesis section changed.
   - Which portfolio position is affected.
   - Whether review or action is recommended.
7. User marks the card reviewed, saves it, dismisses it, or opens the thesis.

### Acceptance criteria

- Routine duplicate news does not create repeated cards.
- No card is generated solely because a new article appeared.
- Cards identify the portfolio relevance and thesis impact.
- Monitoring failures are visible to administrators.
- User can pause monitoring at the portfolio or security level.

---

## Journey 5: Private Research

1. User uploads a PDF, Markdown document, text file, or CSV.
2. AlphaDesk validates and scans the file.
3. The system extracts text and metadata.
4. User associates the source with one or more companies or themes.
5. Extracted content becomes private evidence.
6. User can use private evidence in research and thesis revisions.
7. Private evidence is excluded from shared or exported output unless the user explicitly includes it.

### Acceptance criteria

- Private source ownership is enforced in application code and database queries.
- Uploaded documents retain filename, content hash, retrieval time, and permissions.
- The interface clearly labels public and private evidence.
- A user can delete an upload and its derived content.
- Unsupported or image-only documents fail clearly rather than producing fabricated extraction.

---

## Journey 6: Decision Journal

1. User records an intended decision:
   - Buy.
   - Add.
   - Hold.
   - Reduce.
   - Hedge.
   - Exit.
   - Avoid.
2. User records rationale, expected return, horizon, risks, and confidence.
3. AlphaDesk links the decision to the active thesis and evidence snapshot.
4. After the selected review period, AlphaDesk calculates performance.
5. The user records what happened and what was learned.
6. AlphaDesk can incorporate approved lessons into future research context.

### Acceptance criteria

- Journal entries are immutable records with append-only revisions.
- Performance calculations show the benchmark and calculation period.
- AI-generated reflection is clearly labeled and editable.
- Lessons are not injected into future analysis without user approval during alpha.

---

# 5. Alpha Product Surfaces

## 5.1 Intelligence

The default landing page.

### Components

- Material changes requiring review.
- Portfolio-impacting events.
- Thesis changes.
- New filings.
- Upcoming catalysts.
- Risk alerts.
- Recently completed research.
- Cards marked saved, reviewed, or dismissed.

### Intelligence Card contract

Every card should contain:

- Card type.
- Headline.
- “What changed.”
- “Why it matters.”
- Affected company, thesis, and portfolio.
- Materiality.
- Confidence.
- Evidence links.
- Generated time.
- Recommended review action.
- User status.
- Model and run provenance available in details.

---

## 5.2 Portfolio

### Components

- Total portfolio value.
- Cash.
- Long, short, gross, and net exposure.
- Position weights.
- Concentration.
- Unrealized profit and loss.
- Thesis status by holding.
- Monitoring status.
- Latest rating and rating change.
- Risk flags.
- Upcoming catalysts.
- Holdings without an active thesis.

### Alpha limitations

The portfolio page provides analysis and risk visibility. It does not place trades or automatically modify positions.

---

## 5.3 Narratives

Narratives connect evidence across time and, eventually, across companies.

### Alpha scope

- Company-specific narratives.
- Macro regime narrative.
- Portfolio-level risk narrative.
- Evidence timeline.
- Catalyst timeline.
- Risk timeline.
- Changes since the previous research run.

### Deferred

- Fully automated cross-company theme graphs.
- Complex knowledge-graph navigation.
- Industry-wide causal models.

---

## 5.4 Research

### Components

- Search by ticker or company.
- Start a research run.
- View progress.
- View completed reports.
- Compare runs.
- Inspect analyst stages.
- Inspect evidence.
- Save findings into a thesis.
- Export a research report.
- Rerun failed sections where safe.

---

## 5.5 Workbench

The user’s deeper decision workspace.

### Components

- Active thesis editor.
- Thesis version comparison.
- Evidence review.
- Private research.
- Catalyst and risk definitions.
- Invalidation triggers.
- Scenario assumptions.
- Decision journal.
- User notes.
- AI suggestions awaiting approval.

The Workbench should make human judgment primary. AI proposes; the user accepts, edits, or rejects.

---

## 5.6 Settings

- Profile.
- Workspace.
- Portfolio defaults.
- Monitoring frequency.
- Notification preferences.
- Privacy settings.
- Data-source status.
- Research model preferences where exposed.
- Export and deletion controls.
- Terms and disclosures.

---

# 6. Canonical Domain Model

The following entities must exist before the product layer is considered stable.

## Identity and tenancy

- `User`
- `Workspace`
- `WorkspaceMembership`
- `Invitation`

## Instruments and portfolios

- `Instrument`
- `Portfolio`
- `PortfolioSnapshot`
- `Position`
- `Watchlist`
- `WatchlistItem`

## Research execution

- `AnalysisRun`
- `AnalysisStage`
- `AgentRun`
- `ToolCall`
- `PromptVersion`
- `ModelInvocation`
- `RunEvent`

## Knowledge and provenance

- `SourceRecord`
- `Evidence`
- `Claim`
- `Citation`
- `Narrative`
- `Catalyst`
- `Risk`

## Thesis and decisions

- `Thesis`
- `ThesisRevision`
- `ThesisTrigger`
- `Decision`
- `DecisionRevision`
- `OutcomeReview`

## Intelligence

- `IntelligenceCard`
- `CardEvidence`
- `CardStatus`
- `Monitor`
- `MonitorRun`
- `Notification`

## Private research

- `ResearchDocument`
- `DocumentChunk`
- `DocumentPermission`

## Operational records

- `AuditEvent`
- `Feedback`
- `UsageRecord`
- `ProviderHealthEvent`

Every canonical entity should include:

- Stable identifier.
- Schema version.
- Creation and update timestamps.
- Workspace ownership where applicable.
- Provenance.
- Soft-delete or retention state where applicable.

---

# 7. Target Architecture

```text
Web Application
      │
      ▼
API Gateway / FastAPI
      │
      ├── Authentication and Workspace Authorization
      ├── Portfolio Service
      ├── Research Service
      ├── Evidence Service
      ├── Thesis Service
      ├── Intelligence Service
      ├── Journal Service
      └── Admin Service
      │
      ▼
PostgreSQL ───────── Object Storage
      │                    │
      │                    └── Uploaded documents and large raw artifacts
      │
      ▼
Job Queue / Scheduler
      │
      ▼
Research Workers
      │
      ▼
Existing LangGraph Analysis Engine
      │
      ├── Market providers
      ├── News providers
      ├── SEC
      ├── FRED
      ├── Social sources
      ├── User-owned sources
      └── LLM providers
```

## Architectural principles

1. The existing LangGraph system remains the research engine.
2. Agents never write directly to UI models.
3. Providers return normalized source and evidence objects.
4. Structured objects remain canonical.
5. Markdown and HTML are presentation formats only.
6. Every research run is durable and resumable.
7. Every user-owned object has workspace authorization.
8. Monitoring uses targeted re-analysis rather than complete reruns by default.
9. Cards are projections from evidence, thesis changes, and decisions.
10. No model output bypasses schema validation and policy checks.

---

# 8. Implementation Program

## Phase 0 — Scope Freeze and SEC Stabilization

**Goal:** Protect the existing foundation before product expansion.

### Deliverables

- Merge SEC routing correction.
- Mocked SEC tests:
  - CIK lookup.
  - Symbol normalization.
  - Filing-form filtering.
  - Filing-date cutoff.
  - Official URL generation.
  - Evidence capture.
  - Missing user-agent failure.
- Regression test preventing SEC from being selected for unsupported statement tools.
- Add `SEC_USER_AGENT` to `.env.example`.
- Copy default configuration per graph instance.
- Document alpha scope and non-goals.
- Create an architecture decision record for the canonical evidence layer.

### Exit criteria

- Existing test suite passes.
- SEC tests do not make live network calls.
- No known provider-routing regression.
- Alpha scope is approved and committed under `docs/`.

---

## Phase 1 — Canonical Knowledge Foundation

**Goal:** Establish the structures every later feature will use.

### Deliverables

- Implement:
  - `Instrument`
  - `SourceRecord`
  - `Evidence`
  - `Claim`
  - `AnalysisRun`
  - `Decision`
  - `Thesis`
  - `ThesisRevision`
  - `ThesisTrigger`
  - `IntelligenceCard`
- Add stable IDs and schema versions.
- Add public/private/licensed ownership classifications.
- Add evidence confidence and source timestamps.
- Add canonical structured fields to graph state.
- Preserve current Markdown outputs for compatibility.
- Add renderers from structured models to Markdown and feed cards.
- Begin removal of regex-based extraction.

### Exit criteria

- A research run can produce structured evidence and a structured final decision.
- Existing CLI and static feed continue working.
- No newly implemented feature parses its own canonical data from Markdown.
- All domain models have serialization and validation tests.

---

## Phase 2 — SEC Company Facts and Evidence Adapters

**Goal:** Make official company facts available as traceable evidence.

### Deliverables

Normalize an initial set of SEC metrics:

- Revenue.
- Net income.
- Operating income.
- Total assets.
- Total liabilities.
- Diluted EPS.
- Operating cash flow.
- Capital expenditure where classification is reliable.

Each fact retains:

- Taxonomy concept.
- Normalized metric.
- Value and unit.
- Start and end dates.
- Fiscal year and period.
- Form.
- Filing date.
- Accession number.
- SEC source link.
- Retrieval timestamp.

### Exit criteria

- No look-ahead data is returned for historical research dates.
- Duplicate and amended facts are handled deterministically.
- Fundamentals UI consumes Evidence, not raw SEC responses.
- Every displayed metric links to an official source record.

---

## Phase 3 — Persistence and Application Services

**Goal:** Convert the local engine into a durable multi-user product.

### Deliverables

- PostgreSQL.
- Versioned database migrations.
- Repository interfaces.
- Workspace-level row ownership.
- Persistent analysis runs.
- Persistent portfolio snapshots.
- Persistent evidence, theses, journal entries, and cards.
- Object storage for documents and raw artifacts.
- FastAPI application.
- API versioning.
- Durable job status:
  - Queued.
  - Running.
  - Partially completed.
  - Completed.
  - Failed.
  - Cancelled.
- Run-event stream for UI progress.
- Compatibility exporters for existing JSON and Markdown formats.

### Exit criteria

- A process restart does not lose a research run.
- Two users cannot access each other’s data.
- Existing file outputs remain available as exports.
- Database migrations can be applied and rolled back in a test environment.
- API integration tests cover the critical user journeys.

---

## Phase 4 — Authentication, Authorization, and Alpha Administration

> **Delivery note:** Deferred until after the product surfaces and evals
> (see §12 order 12). Build portfolio, thesis/journal, private research, and
> the web app against workspace-scoped APIs first.

**Goal:** Safely invite real users.

### Deliverables

- Invite-only signup.
- Email verification or managed identity provider.
- Secure session handling.
- Workspace ownership.
- Role model:
  - Owner.
  - Member, reserved for later.
  - Administrator.
- Password reset or identity-provider equivalent.
- Terms and disclosure acceptance.
- Admin console:
  - Invite user.
  - Disable user.
  - Inspect job failures.
  - Inspect provider status.
  - Inspect usage and estimated cost.
  - View user feedback.
- Audit logging for sensitive actions.

### Exit criteria

- Authorization tests cover every protected resource.
- No cross-workspace access through predictable IDs.
- Secrets are not exposed to the frontend.
- Admin actions are audited.
- Account deletion and data-export paths are documented.

---

## Phase 5 — Portfolio Product

> **Status:** Backend product surface landed on `main` (CSV preview/confirm,
> current-book editing, watchlists, exposure summary, thesis coverage,
> monitoring pause controls). Persistent web portfolio page remains Phase 9.

**Goal:** Give alpha users a usable portfolio-centered starting point.

### Deliverables

- CSV import interface.
- Mapping and validation preview.
- Manual position editing.
- Watchlists.
- Portfolio snapshots.
- Exposure and concentration cards.
- Thesis coverage status.
- Monitoring controls.
- Position-level company navigation.
- Portfolio-aware research context.
- User correction workflow for unsupported CSV formats.

### Exit criteria

- Supported CSV imports have at least 95% row-level parsing success on the test fixture set.
- User can correct errors before confirming.
- Portfolio calculations are deterministic and unit-tested.
- The UI distinguishes missing market price from zero market value.
- Portfolio remains research-only and cannot execute transactions.

---

## Phase 6 — Living Thesis and Decision Journal

> **Status:** Backend product surface landed on `main` (create-from-run as
> proposal, accept/edit/reject, revision diff, evidence selection, journal
> linked to thesis/portfolio snapshots, outcome review with benchmark-relative
> returns, lesson-reuse flag). Workbench UI remains Phase 9.

**Goal:** Deliver AlphaDesk’s core differentiating workflow.

### Deliverables

- Create thesis from a research run.
- Human-editable thesis.
- Revision comparison.
- Bull case.
- Bear case.
- Catalysts.
- Risks.
- Invalidation conditions.
- Expected horizon.
- Confidence.
- Evidence selection.
- Proposed AI revisions.
- Accept/edit/reject workflow.
- Decision journal linked to thesis and portfolio snapshot.
- Outcome-review workflow.
- Benchmark-relative results.

### Exit criteria

- Every active thesis has a current revision and revision history.
- Thesis revisions can be traced to evidence.
- AI cannot silently change user-authored thesis content.
- Decision records preserve the state known when the decision was made.
- Users can disable future lesson reuse.

---

## Phase 7 — User-Owned Research

**Goal:** Allow users to incorporate information AlphaDesk does not possess publicly.

### Deliverables

- PDF ingestion for digitally generated PDFs.
- Markdown and text ingestion.
- CSV ingestion.
- Malware and file-type validation.
- Content hashing and deduplication.
- Company and theme association.
- Private Evidence records.
- Source browser.
- Document deletion.
- Private/public visibility enforcement.
- Full-text retrieval.
- Optional semantic retrieval only after deterministic retrieval works.

### Exit criteria

- Private evidence cannot leak into another workspace.
- Public exports exclude private evidence by default.
- Unsupported documents fail visibly.
- User can inspect the extracted text used by the system.
- Deleting a source prevents its use in future runs.

---

## Phase 8 — Monitoring and Material-Change Intelligence

> **Delivery note:** Deferred until after evaluations (see §12 order 11). Ship
> the complete research → thesis → journal product loop first, then measure
> quality, then add continuous monitoring.

**Goal:** Move from one-time research to continuous portfolio intelligence.

### Initial monitoring scope

- New SEC filings.
- Material company news.
- Selected macro changes.
- Price movement relative to thesis targets or risks.
- User-defined thesis triggers.

### Processing pipeline

```text
Poll sources
    ↓
Detect new records
    ↓
Normalize evidence
    ↓
Deduplicate
    ↓
Classify materiality
    ↓
Identify affected thesis
    ↓
Run targeted analysis
    ↓
Propose thesis change
    ↓
Create Intelligence Card
```

### Deliverables

- Scheduler.
- Monitor definitions.
- Provider polling.
- Deduplication.
- Trigger evaluation.
- Materiality classifier.
- Targeted re-analysis.
- Intelligence Card generation.
- In-app notification center.
- Optional email digest.
- Monitoring health interface.

### Exit criteria

- No duplicate alert for the same evidence and thesis impact.
- Every card includes evidence and portfolio relevance.
- Users can dismiss, save, or mark a card reviewed.
- Monitoring can be paused.
- Provider failures retry within defined budgets.
- No complete deep research run is launched for immaterial routine news.

---

## Phase 9 — Persistent Web Experience

**Goal:** Replace the generated HTML proof of concept with a product-quality application.

### Deliverables

- Responsive desktop web application.
- Global navigation.
- Intelligence surface.
- Portfolio surface.
- Narratives surface.
- Research surface.
- Workbench.
- Company detail pages.
- Thesis detail.
- Evidence drawer.
- Research progress.
- Journal.
- Settings.
- Empty states.
- Loading and failure states.
- Basic accessibility.
- Product analytics.
- Feedback capture.
- Existing feed JSON supported as a compatibility projection during migration.

### Exit criteria

- All core user journeys can be completed without the CLI.
- Browser refresh does not lose state.
- Long-running research displays durable progress.
- Every source link is accessible from the relevant output.
- UI handles unavailable, partial, and stale data explicitly.
- No regex parsing is required to render canonical decisions.

---

## Phase 10 — Quality, Evaluation, and Model Governance

**Goal:** Make AI quality measurable before real users depend on it.

### Evaluation dataset

Build a dated evaluation set containing:

- 25–50 securities.
- Large, mid, and small caps.
- Profitable and unprofitable companies.
- High- and low-news names.
- Earnings periods.
- Filing events.
- Bull and bear regimes.
- Known data-availability edge cases.

### Evaluation dimensions

- Factual accuracy.
- Citation correctness.
- Date correctness.
- Look-ahead prevention.
- Evidence coverage.
- Relevance.
- Internal consistency.
- Rating consistency.
- Risk identification.
- Portfolio awareness.
- Unsupported-claim rate.
- Material-change precision.
- Material-change recall.
- Output stability.
- Cost.
- Latency.

### Deliverables

- Versioned prompts.
- Model and provider metadata stored per run.
- Golden regression runs.
- Human review rubric.
- Automated contract checks.
- Hallucination and unsupported-claim tests.
- Cost and token budgets.
- Provider fallback policy.
- Prompt-injection tests for news and uploaded documents.
- Model-change approval checklist.

### Alpha quality gates

- No unsupported numerical claim in the reviewed golden set.
- Every material factual claim has evidence.
- Historical runs respect their cutoff date.
- Structured output success exceeds 95% for the selected production model.
- The product exposes uncertainty when evidence is incomplete.
- Model or prompt changes cannot ship without evaluation comparison.

---

## Phase 11 — Reliability, Security, and Operations

**Goal:** Make the product safe enough for invite-only external use.

### Reliability

- Structured application logs.
- Trace ID per request and research run.
- Job retries.
- Timeouts.
- Circuit breakers.
- Provider rate limiting.
- Dead-letter handling.
- Database backups.
- Object-storage backups.
- Health endpoints.
- Error tracking.
- Uptime monitoring.
- Run-cost monitoring.

### Security

- Encryption in transit.
- Encryption at rest.
- Managed secrets.
- Dependency scanning.
- Container scanning.
- File-upload scanning.
- Input validation.
- Strict workspace authorization.
- Audit events.
- Data-retention policy.
- User export and deletion.
- Prompt-injection boundaries.
- Restricted tool permissions.
- HTML and Markdown sanitization.

### Suggested alpha service objectives

- 99% monthly application availability, excluding planned maintenance.
- At least 95% successful research completion excluding provider-wide outages.
- No loss of completed research or user-edited thesis data.
- Critical security issues resolved before launch.
- Research-run status visible within five seconds of submission.
- User-facing error messages for all expected failure classes.

---

## Phase 12 — Legal, Disclosure, and User Trust

**Goal:** Clearly communicate what the product does and does not do.

### Required product controls

- Research-only disclosure.
- No promise of returns.
- No automated execution.
- Source dates and freshness.
- AI-generated-content labeling.
- Explanation of data-provider limitations.
- User responsibility for decisions.
- Privacy policy.
- Terms of use.
- Data deletion and export policy.
- Clear distinction between:
  - Facts.
  - Derived metrics.
  - AI interpretations.
  - User-authored content.
- Legal review before moving beyond a small, controlled alpha.

---

# 9. Alpha Analytics and Success Metrics

## Activation

- Invitation accepted.
- Portfolio created.
- First research run completed.
- First thesis created.
- Monitoring enabled.

### Target

At least 60% of accepted invitees complete a portfolio import and one research run.

## Engagement

- Weekly active users.
- Research runs per user.
- Theses created.
- Evidence opened.
- Intelligence cards reviewed.
- Journal entries created.
- User documents uploaded.

## Retention

- Week-1 retention.
- Week-4 retention.
- Percentage of users returning before making an investment decision.
- Percentage of monitored holdings with reviewed intelligence.

## Value metrics

- Time saved per research session.
- Number of external tools replaced.
- Percentage of cards rated useful.
- Percentage of thesis revisions accepted or edited.
- Research Replacement Rate.
- Users who state AlphaDesk changed or strengthened a decision.

## Quality metrics

- Unsupported-claim rate.
- Citation-error rate.
- Duplicate-card rate.
- Materiality false-positive rate.
- Research failure rate.
- Median and 95th-percentile run time.
- Average LLM and provider cost per user.
- User-reported trust score.

---

# 10. Alpha Feedback System

Every major surface should include contextual feedback.

## Intelligence Card feedback

- Useful.
- Not useful.
- Already knew this.
- Not material.
- Incorrect.
- Missing evidence.
- Too late.

## Research feedback

- Strong analysis.
- Important factor missed.
- Evidence issue.
- Rating disagreement.
- Too verbose.
- Too shallow.

## Thesis feedback

- Accepted.
- Edited.
- Rejected.
- Reason for rejection.

## Operational feedback

- Bug.
- Data problem.
- Feature request.
- Confusing workflow.
- Provider outage.

Feedback must record the associated card, run, thesis revision, model version, and UI context.

---

# 11. Alpha Rollout Plan

## Internal dogfood

**Users:** Founder and trusted internal users.

### Purpose

- Validate portfolio imports.
- Validate evidence.
- Identify provider failures.
- Tune cost and latency.
- Test thesis workflow.

### Exit gate

- Complete critical user journeys without database intervention.
- No critical data-isolation issue.
- No known silent research corruption.

---

## Design-partner alpha

**Users:** 5–10 highly engaged investors.

### Operation

- Direct onboarding.
- Weekly interview.
- Shared issue channel.
- Manual review of selected research runs.
- Tight usage limits.
- Rapid product iteration.

### Exit gate

- At least five users return weekly for four weeks.
- At least three users create and maintain multiple theses.
- Intelligence cards demonstrate repeated value.
- Research quality is trusted enough for users to compare against their own work.

---

## Expanded alpha

**Users:** 20–50 invited investors.

### Operation

- Self-service onboarding.
- In-product support and feedback.
- Weekly product digest.
- Defined incident and support process.
- Cost controls per workspace.

### Exit gate for beta

- Week-4 retention above 30%.
- At least 40% of active users review intelligence weekly.
- At least 30% maintain one or more active theses.
- More than 70% of reviewed cards are useful or partially useful.
- Research completion rate above 95%, excluding external provider outages.
- No high-severity privacy or authorization incident.
- Cost per engaged user is understood and supportable.

---

# 12. Recommended Delivery Sequence

Phase numbers in §8 remain stable labels for scope. **Delivery order** below is
product-first: finish the core research product before invite-only auth and
before continuous monitoring.

| Order | Workstream (phase) | Critical outcome |
|---:|---|---|
| 1 | SEC hardening (0) | Existing integration is safe to extend |
| 2 | Canonical domain models (1) | Stable knowledge contracts |
| 3 | Structured graph outputs (1) | No Markdown-as-database pattern |
| 4 | SEC facts and evidence (2) | Trusted official fundamentals |
| 5 | PostgreSQL and services (3) | Durable multi-user product foundation |
| 6 | Portfolio product (5) | User-specific product foundation |
| 7 | Living thesis and journal (6) | Core differentiated workflow |
| 8 | Private research (7) | User-owned context |
| 9 | Persistent frontend (9) | Complete user experience |
| 10 | Evaluations and model governance (10) | Measurable AI quality |
| 11 | Monitoring and intelligence (8) | Recurring product value after the loop works |
| 12 | Authentication and tenancy (4) | External users can be invited safely |
| 13 | Reliability, security, and operations (11) | Alpha launch ops readiness |
| 14 | Legal, disclosure, and user trust (12) | Trust and compliance surface |

Rationale:

- Auth (phase 4) stays after the product surfaces are real so tenancy is wired
  to finished APIs/UI rather than stubs.
- Monitoring (phase 8) stays after evals so material-change alerts are gated on
  measured quality, not shipped on an unfinished research loop.

Several workstreams can overlap after the canonical schemas stabilize:

- Frontend design can proceed against mocked API contracts and `X-Workspace-Id`.
- Evaluation datasets can be assembled throughout product development.
- Security and observability basics should be added continuously; full auth and
  ops hardening still land late in this sequence.

---

# 13. Definition of Alpha Ready

AlphaDesk is ready for external alpha users only when all of the following are true:

## User experience

- User can onboard without engineering help.
- User can import or create a portfolio.
- User can run research.
- User can inspect evidence.
- User can create and revise a thesis.
- User can record a decision.
- User can receive and review material-change intelligence.
- User can upload private research.
- User can submit feedback.

## Data and AI quality

- Material claims have citations.
- Historical runs prevent look-ahead.
- Structured outputs are canonical.
- Provider failure modes are explicit.
- Model and prompt versions are recorded.
- Core evaluation suite passes.

## Security and privacy

- Authentication is enabled.
- Workspace authorization is tested.
- Private evidence remains private.
- Secrets are managed outside source code.
- File uploads are validated.
- Terms and disclosures are accepted.
- Data deletion and export exist.

## Reliability

- Jobs are durable.
- Failed jobs can retry.
- Research progress survives refresh and restart.
- Backups exist.
- Provider health is observable.
- Errors are tracked.
- Administrators can manage invitations and failures.

## Product operations

- Usage and cost are measurable.
- Feedback is linked to product artifacts.
- Support process exists.
- Incident response owner is defined.
- Alpha limitations are clearly documented.

---

# 14. Estimated Delivery

These are planning estimates rather than commitments.

## With one full-time engineer

Approximately **5–8 months** for a credible external alpha, assuming significant reuse of managed infrastructure and a narrow frontend.

## With two engineers

Approximately **3–5 months**:

- Engineer 1: domain, backend, orchestration, persistence.
- Engineer 2: frontend, portfolio/thesis UX, integration (auth later).

## With three engineers

Approximately **12–16 weeks**:

- AI/domain engineer.
- Backend/platform engineer.
- Frontend/product engineer.

The founder or product lead should continuously own:

- User interviews.
- Thesis workflow.
- Quality evaluation.
- Alpha support.
- Product analytics.
- Scope control.

---

# 15. First Five Implementation PRs

## PR 1 — SEC Reliability

Harden SEC routing, user-agent configuration, filing cutoff behavior, evidence capture, and mocked regression tests.

## PR 2 — Domain Foundation

Introduce `Instrument`, `SourceRecord`, `Evidence`, `Claim`, `AnalysisRun`, and initial ownership/provenance contracts.

## PR 3 — Structured Output Preservation

Store research plans, trader proposals, portfolio decisions, and sentiment reports as canonical structured graph-state objects while retaining Markdown renderers.

## PR 4 — SEC Evidence Adapter

Convert filing metadata and SEC company facts into normalized Source and Evidence records.

## PR 5 — Thesis Foundation

Introduce `Thesis`, `ThesisRevision`, `ThesisTrigger`, and a compatibility workflow for creating a thesis from an existing completed research run.

---

# 16. Product North Star After Alpha

After proving alpha retention, the product can expand toward:

- Multi-company narratives.
- Theme and supply-chain knowledge graphs.
- Earnings and filing replay.
- Portfolio-level allocation recommendations.
- Deterministic risk policies.
- Options research and visualization.
- Broker synchronization.
- Historical decision replay.
- Backtesting with dated knowledge snapshots.
- Advisor and family-office workspaces.
- Collaboration and approval workflows.
- Paid institutional datasets.

These should not delay the alpha’s central loop:

```text
Portfolio
    ↓
Evidence
    ↓
Research
    ↓
Living Thesis
    ↓
Material Change
    ↓
Intelligence
    ↓
Human Decision
    ↓
Outcome and Learning
```