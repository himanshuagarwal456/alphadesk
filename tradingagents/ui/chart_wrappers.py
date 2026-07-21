"""Investment-specific configurations built on the generic chart contract."""

from __future__ import annotations

from .chart_spec import BenchmarkSpec, ChartSpec, ChartType


def portfolio_performance(*, date_field="date", portfolio_field="portfolio", benchmark_field="benchmark"):
    return ChartSpec(
        id="portfolio-performance", chart_type=ChartType.LINE,
        title="Portfolio performance", subtitle="Versus benchmark",
        x_field=date_field, y_fields=[portfolio_field, benchmark_field],
        benchmark=BenchmarkSpec(field=benchmark_field), number_format="percent",
        interactions={"date_range": True, "zoom": True, "crosshair": True},
    )


def portfolio_allocation(*, category_field="symbol", value_field="weight"):
    return ChartSpec(
        id="portfolio-allocation", chart_type=ChartType.DONUT, title="Portfolio allocation",
        category_field=category_field, y_fields=[value_field], number_format="percent",
    )


def revenue_earnings_trends(*, date_field="period", revenue_field="revenue", earnings_field="earnings"):
    return ChartSpec(
        id="revenue-earnings", chart_type=ChartType.BAR, title="Revenue and earnings",
        x_field=date_field, y_fields=[revenue_field, earnings_field], number_format="currency_compact",
    )


def margin_trends(*, date_field="period", fields=("gross_margin", "operating_margin")):
    return ChartSpec(
        id="margin-trends", chart_type=ChartType.LINE, title="Margin trends",
        x_field=date_field, y_fields=list(fields), number_format="percent",
    )


def contribution_to_return(*, category_field="symbol", value_field="contribution"):
    return ChartSpec(
        id="return-contribution", chart_type=ChartType.WATERFALL,
        title="Contribution to return", x_field=category_field, y_fields=[value_field],
        number_format="percent",
    )


def correlation_matrix(*, fields: list[str] | None = None):
    return ChartSpec(
        id="correlation-matrix", chart_type=ChartType.HEATMAP,
        title="Correlation matrix", y_fields=fields or [], number_format="decimal_2",
    )
