Build an **AlphaDesk Visualization System** using the existing frontend, data, and design conventions.

The goal is to support a broad set of reusable financial visualizations without creating separate one-off components for every dashboard or research page.

Use Apache Superset as inspiration for chart variety, but design the system specifically for investment research, portfolio intelligence, and AlphaDesk’s visual language.

## Architecture

Create a declarative chart specification:

```text
ChartSpec
- id
- chart_type
- title
- subtitle
- description
- data_source
- x_field
- y_fields
- category_field
- series
- number_format
- time_granularity
- annotations
- benchmark
- interactions
- empty_state
- source_metadata
```

Create a central `ChartRegistry` that maps each `chart_type` to:

- renderer component,
- required fields,
- supported data shapes,
- configuration schema,
- supported interactions,
- default formatting,
- accessibility behavior.

Example chart types:

```text
LINE
AREA
BAR
STACKED_BAR
DONUT
SCATTER
HEATMAP
TREEMAP
WATERFALL
CANDLESTICK
DRAWDOWN
EVENT_TIMELINE
```

Keep chart data separate from presentation:

```text
Data provider
    ↓
Data adapter
    ↓
Normalized chart data
    ↓
ChartSpec
    ↓
Chart renderer
```

Do not make individual chart components responsible for fetching or transforming domain data.

## AlphaDesk Design Language

Create shared visualization tokens for:

- typography,
- grid lines,
- axes,
- tooltip surfaces,
- legends,
- spacing,
- chart height,
- line weight,
- point size,
- positive and negative values,
- benchmark series,
- selected and muted series,
- warning and risk states,
- light and dark themes.

Use green and red only when values genuinely represent positive and negative financial outcomes. Ordinary categorical series should use neutral, restrained colors.

All charts should share:

- consistent titles and subtitles,
- consistent number formatting,
- consistent date formatting,
- unified tooltips,
- source and freshness metadata,
- loading, empty, and error states,
- responsive behavior,
- accessible labels,
- export-ready presentation.

## Standard Interactions

Support these interactions through the shared chart layer rather than implementing them separately:

- hover tooltip,
- legend toggle,
- date-range selection,
- zoom,
- crosshair,
- benchmark overlay,
- event annotations,
- fullscreen view,
- data-table view,
- save to research,
- attach to journal or thesis.

## Initial Implementation

Implement the framework and these first chart types:

1. Time-series line and area
2. Bar and stacked bar
3. Donut allocation
4. Financial waterfall
5. Correlation heatmap
6. Risk-versus-return scatter
7. Drawdown chart
8. Event-annotated price chart

Also create investment-specific wrapper configurations for:

- portfolio performance versus benchmark,
- portfolio allocation,
- revenue and earnings trends,
- margin trends,
- contribution to return,
- correlation matrix.

Do not build a generic dashboard builder yet. First establish the chart specification, registry, data adapters, shared design tokens, and reusable renderers.

The framework must support charts embedded in:

- Intelligence Cards,
- Research reports,
- Portfolio views,
- Morning Brief,
- Knowledge / Learn More panels,
- Thesis and Journal entries.

Preserve existing chart functionality and migrate existing charts incrementally rather than rewriting everything at once.