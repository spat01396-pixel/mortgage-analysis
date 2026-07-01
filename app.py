import dash
from dash import html, dcc, Input, Output, State, ctx, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from mortgage_engine import MortgageCalculator
from dash.exceptions import PreventUpdate

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@300;400;500&family=Outfit:wght@300;400;500;600&display=swap",
    ],
    suppress_callback_exceptions=True,
)

C = {
    "obsidian": "#0d0f14",
    "surface": "#13161e",
    "panel": "#1a1e28",
    "border": "#252a38",
    "border2": "#2e3447",
    "gold": "#c9a84c",
    "gold_dim": "#9b7e38",
    "platinum": "#e8e4dc",
    "muted": "#6b7280",
    "green": "#4ade80",
    "red": "#f87171",
    "blue": "#60a5fa",
    "purple": "#a78bfa",
    "teal": "#2dd4bf",
    "orange": "#fb923c",
}

BAND_COLORS = [
    "rgba(96,165,250,0.06)",
    "rgba(201,168,76,0.06)",
    "rgba(74,222,128,0.06)",
    "rgba(248,113,113,0.06)",
]

SCENARIO_COLORS = [C["gold"], C["blue"], C["purple"]]
SCENARIO_LABELS = ["A", "B", "C"]

# Default calculator state used when store is empty
DEFAULT_CALC = {
    "scenario_name": "My Scenario",
    "price": 600000,
    "buy_costs": 25000,
    "loan": 540000,
    "rate": 5,
    "tenure": 25,
    "prepayment_rules": [],
    "variable_rates": [],
    "rent": 0,
    "tax": 0,
    "maint": 0,
    "rent_year": 1,
    "tax_mode": "simple",
    "rent_growth": 2,
    "sell_year": 10,
    "sell_price": 2,
    "selling_costs": 5000,
    "inflation": 2,
}


# ─────────────────────────────────────────────
# CHART HELPERS
# ─────────────────────────────────────────────
def chart_layout(title, y_prefix="£", subtitle=None):
    title_text = f"<b>{title}</b>"
    if subtitle:
        title_text += (
            f"<br><span style='font-size:11px;color:#6b7280'>{subtitle}</span>"
        )
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono, monospace", color="#6b7280", size=11),
        title=dict(
            text=title_text,
            font=dict(family="DM Serif Display, serif", color=C["platinum"], size=15),
            x=0,
            pad=dict(l=6),
        ),
        margin=dict(l=52, r=24, t=60, b=44),
        xaxis=dict(
            gridcolor="rgba(37,42,56,0.6)",
            linecolor=C["border"],
            tickfont=dict(family="DM Mono, monospace", size=10, color=C["muted"]),
            zeroline=False,
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor="rgba(37,42,56,0.6)",
            linecolor=C["border"],
            tickfont=dict(family="DM Mono, monospace", size=10, color=C["muted"]),
            zeroline=False,
            tickprefix=y_prefix,
            tickformat=",.0f",
            showgrid=True,
        ),
        hoverlabel=dict(
            bgcolor="#1e2433",
            bordercolor=C["gold"],
            font=dict(family="DM Mono, monospace", size=11, color=C["platinum"]),
        ),
        legend=dict(
            bgcolor="rgba(13,15,20,0.7)",
            bordercolor=C["border"],
            borderwidth=1,
            font=dict(family="DM Mono, monospace", size=10, color=C["muted"]),
            x=1,
            xanchor="right",
            y=1,
            yanchor="top",
        ),
        transition=dict(duration=350, easing="cubic-in-out"),
        hovermode="x unified",
    )


# ─────────────────────────────────────────────
# DROPDOWN HELPER — native select via dbc.Select (dark-styled, Dash-readable)
# ─────────────────────────────────────────────
_SELECT_STYLE = {
    "backgroundColor": "#13161e",
    "color": "#e8e4dc",
    "border": "1px solid #252a38",
    "borderRadius": "6px",
    "fontSize": "0.8rem",
    "padding": "5px 8px",
    "height": "34px",
    "width": "100%",
    "cursor": "pointer",
}


def dark_dropdown(id_, options, value, **kwargs):
    """Native <select> that Dash tracks reliably, styled to match dark theme."""
    return dbc.Select(
        id=id_,
        options=options,
        value=value,
        style=_SELECT_STYLE,
        **kwargs,
    )


# ─────────────────────────────────────────────
# FIELD / CARD / KPI HELPERS
# ─────────────────────────────────────────────
def field(label, id_, value, suffix="", flex=1):
    has_suffix = bool(suffix)
    inner = [
        dbc.Input(
            id=id_,
            type="number",
            value=value,
            className="input-dark with-suffix" if has_suffix else "input-dark",
            style={"borderRadius": "6px 0 0 6px" if has_suffix else "6px"},
        )
    ]
    if has_suffix:
        inner.append(html.Span(suffix, className="input-suffix"))
    return html.Div(
        [
            html.Span(label, className="field-label"),
            html.Div(inner, style={"display": "flex"}),
        ],
        style={"flex": flex, "minWidth": 0},
    )


def sc_field(label, id_type, index, value, suffix="", flex=1):
    has_suffix = bool(suffix)
    inner = [
        dbc.Input(
            id={"type": id_type, "index": index},
            type="number",
            value=value,
            className="input-dark with-suffix" if has_suffix else "input-dark",
            style={"borderRadius": "6px 0 0 6px" if has_suffix else "6px"},
        )
    ]
    if has_suffix:
        inner.append(html.Span(suffix, className="input-suffix"))
    return html.Div(
        [
            html.Span(label, className="field-label"),
            html.Div(inner, style={"display": "flex"}),
        ],
        style={"flex": flex, "minWidth": 0},
    )


def card(header_label, body_children, header_extra=None, style=None):
    header_row = [
        html.Div(className="card-header-dot"),
        html.Span(header_label, className="card-header-label"),
    ]
    if header_extra:
        header_row.append(html.Div(header_extra, style={"marginLeft": "auto"}))
    return html.Div(
        [
            html.Div(header_row, className="card-header-dark"),
            html.Div(body_children, className="card-body-dark"),
        ],
        className="card-dark",
        style=style or {},
    )


def kpi_card(label, id_):
    return html.Div(
        [
            html.Div(label, className="kpi-label"),
            html.Div("-", id=id_, className="kpi-value"),
        ],
        className="kpi-card",
        style={"flex": 1},
    )


def chart_wrap(graph_id, height="340px"):
    return dcc.Graph(
        id=graph_id,
        config={"displayModeBar": False},
        style={"height": height},
        responsive=True,
    )


def run_calc(
    price,
    buy_costs,
    loan,
    rate,
    tenure,
    prepayment_rules,
    rates,
    rent,
    tax,
    maint,
    rent_year,
    tax_mode,
    sell_year,
    sell_price,
    selling_costs,
    inflation,
    rent_growth,
):
    clean_rates = []
    for r in rates or []:
        if not (isinstance(r, dict) and "year" in r and "rate" in r):
            continue
        entry = {"year": int(r["year"]), "rate": float(r["rate"])}
        if r.get("new_tenure_years"):
            entry["new_tenure_years"] = float(r["new_tenure_years"])
        clean_rates.append(entry)
    clean_prepay = [
        {
            "start_year": int(p.get("start_year") or 1),
            "stop_year": int(p["stop_year"]) if p.get("stop_year") else None,
            "type": p.get("type", "fixed"),
            "amount": float(p.get("amount") or 0),
            "pct": float(p.get("pct") or 0),
        }
        for p in (prepayment_rules or [])
        if isinstance(p, dict)
    ]
    calc = MortgageCalculator(
        price,
        loan or 1,
        rate or 1,
        tenure or 1,
        prepayment_rules=clean_prepay,
        variable_rates=clean_rates,
    )
    result = calc.summary()
    sell = calc.selling_analysis(
        sell_year or 1, sell_price or 0, inflation or 0, selling_costs or 0
    )
    rental_df = None
    if rent and rent > 0:
        rental_df = calc.rental_cashflow_over_time(
            rent,
            tax or 0,
            maint or 0,
            rent_year or 1,
            tax_mode or "simple",
            rent_growth or 0,
        )
    return calc, result, sell, rental_df


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
sidebar = html.Div(
    [
        html.Div(
            [
                html.Div("Mortgage", className="sidebar-logo-mark"),
                html.Div(
                    "Navigator",
                    className="sidebar-logo-mark",
                    style={"color": C["platinum"]},
                ),
                html.Div("Strategy Platform", className="sidebar-logo-sub"),
            ],
            className="sidebar-logo",
        ),
        html.Div(
            [
                html.Button(
                    [html.I(className="bi bi-calculator"), " Calculator"],
                    id="nav-calc",
                    className="nav-item-btn active",
                ),
                html.Button(
                    [html.I(className="bi bi-layers"), " Compare"],
                    id="nav-compare",
                    className="nav-item-btn",
                ),
                html.Button(
                    [html.I(className="bi bi-book"), " Glossary"],
                    id="nav-gloss",
                    className="nav-item-btn",
                ),
            ],
            className="sidebar-nav",
        ),
        html.Div("v1.0 · 2025", className="sidebar-footer"),
    ],
    className="sidebar",
)


# ─────────────────────────────────────────────
# TOP BAR
# ─────────────────────────────────────────────
topbar = html.Div(
    [
        html.Div("Mortgage Strategy Dashboard", className="topbar-title"),
        dbc.Row(
            [
                dbc.Col(
                    html.Span("Select Currency", className="currency-label"),
                    width="auto",
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="currency-selector",
                        options=[
                            {"label": "£ GBP", "value": "£"},
                            {"label": "$ USD", "value": "$"},
                            {"label": "€ EUR", "value": "€"},
                            {"label": "₹ INR", "value": "₹"},
                        ],
                        value="£",
                        clearable=False,
                        searchable=False,
                        className="currency-dropdown",
                    ),
                    width="auto",
                ),
            ],
            align="center",
            className="g-2",
        ),
    ],
    className="topbar d-flex justify-content-between align-items-center",
)


# ─────────────────────────────────────────────
# CALCULATOR LAYOUT
# ─────────────────────────────────────────────
def calculator_layout(currency, state=None):
    s = state or DEFAULT_CALC

    return html.Div(
        [
            # ── ROW 1: Core + Prepayment ──────────────
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                className="section-label", children="Loan Parameters"
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Scenario name",
                                        className="field-label",
                                        style={"marginBottom": "4px"},
                                    ),
                                    html.Div(
                                        [
                                            dbc.Input(
                                                id="calc-scenario-name",
                                                value=s.get(
                                                    "scenario_name", "My Scenario"
                                                ),
                                                className="input-dark",
                                                style={
                                                    "fontSize": "0.78rem",
                                                    "padding": "5px 10px",
                                                    "width": "180px",
                                                },
                                            ),
                                            html.Button(
                                                [
                                                    html.I(
                                                        className="bi bi-plus-circle"
                                                    ),
                                                    " Add to Comparison",
                                                ],
                                                id="add-to-comparison-btn",
                                                className="btn-gold",
                                                style={
                                                    "fontSize": "0.68rem",
                                                    "padding": "4px 10px",
                                                },
                                            ),
                                            html.Div(
                                                id="add-to-comparison-feedback",
                                                style={
                                                    "fontFamily": "DM Mono, monospace",
                                                    "fontSize": "0.65rem",
                                                    "color": C["green"],
                                                    "alignSelf": "center",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                            "gap": "8px",
                                        },
                                    ),
                                ],
                                style={"display": "flex", "flexDirection": "column"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "flex-end",
                            "gap": "12px",
                            "marginBottom": "12px",
                            "flexWrap": "wrap",
                        },
                    ),
                    html.Div(
                        [
                            card(
                                "Core Mortgage",
                                html.Div(
                                    [
                                        field(
                                            "Market Price",
                                            "price",
                                            s["price"],
                                            currency,
                                        ),
                                        field(
                                            "Loan Amount", "loan", s["loan"], currency
                                        ),
                                        field(
                                            "Buy Costs",
                                            "buy_costs",
                                            s["buy_costs"],
                                            currency,
                                        ),
                                        field("Annual Rate", "rate", s["rate"], "%"),
                                        field(
                                            "Initial Tenure",
                                            "tenure",
                                            s["tenure"],
                                            "yrs",
                                        ),
                                    ],
                                    style={"display": "flex", "gap": "14px"},
                                ),
                                style={"flex": 1},
                            ),
                            card(
                                "Prepayment Rules",
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                field(
                                                    "Start Yr", "prepay_start", None, ""
                                                ),
                                                field(
                                                    "Stop Yr", "prepay_stop", None, ""
                                                ),
                                                html.Div(
                                                    [
                                                        html.Span(
                                                            "Type",
                                                            className="field-label",
                                                        ),
                                                        dark_dropdown(
                                                            "prepay_type_input",
                                                            options=[
                                                                {
                                                                    "label": "Fixed Amount",
                                                                    "value": "fixed",
                                                                },
                                                                {
                                                                    "label": "% of Balance",
                                                                    "value": "percent",
                                                                },
                                                            ],
                                                            value="fixed",
                                                        ),
                                                    ],
                                                    style={"flex": 1, "minWidth": 0},
                                                ),
                                                field(
                                                    "Amount",
                                                    "prepay_amount",
                                                    None,
                                                    currency,
                                                ),
                                                field(
                                                    "% Bal",
                                                    "prepay_pct_input",
                                                    None,
                                                    "%",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Span(
                                                            "\u00a0",
                                                            className="field-label",
                                                        ),
                                                        html.Button(
                                                            "Add",
                                                            id="add_prepay",
                                                            className="btn-gold",
                                                        ),
                                                    ],
                                                    style={"flex": 0.5},
                                                ),
                                            ],
                                            style={
                                                "display": "flex",
                                                "gap": "10px",
                                                "marginBottom": "14px",
                                            },
                                        ),
                                        html.Div(className="divider"),
                                        html.Div(
                                            id="prepay_table",
                                            children=html.Div(
                                                "No rules added",
                                                style={
                                                    "fontFamily": "DM Mono, monospace",
                                                    "fontSize": "0.7rem",
                                                    "color": C["muted"],
                                                    "textAlign": "center",
                                                    "padding": "12px 0",
                                                },
                                            ),
                                            style={
                                                "maxHeight": "110px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    ]
                                ),
                                style={"flex": 1},
                            ),
                        ],
                        style={"display": "flex", "gap": "16px"},
                    ),
                ],
                style={"marginBottom": "16px"},
            ),
            # ── ROW 2: KPIs ───────────────────────────
            html.Div(
                [
                    kpi_card("Monthly EMI", "emi"),
                    kpi_card("Total Interest", "interest"),
                    kpi_card("Effective Interest Rate", "eff_interest_rate"),
                    kpi_card("Payoff Years", "years"),
                ],
                style={"display": "flex", "gap": "14px", "marginBottom": "16px"},
            ),
            # ── ROW 3: Rental + Variable Rates ────────
            html.Div(
                [
                    card(
                        "Rental Analysis",
                        html.Div(
                            [
                                field("Monthly Rent", "rent", s["rent"], currency),
                                field("Tax Rate", "tax", s["tax"], "%"),
                                field("Maintenance", "maint", s["maint"], "%"),
                                html.Div(
                                    [
                                        html.Span("Tax Mode", className="field-label"),
                                        dark_dropdown(
                                            "tax_mode",
                                            options=[
                                                {"label": "Simple", "value": "simple"},
                                                {
                                                    "label": "UK (Section 24)",
                                                    "value": "uk",
                                                },
                                                {"label": "Harsh", "value": "harsh"},
                                            ],
                                            value=s["tax_mode"],
                                        ),
                                    ],
                                    style={"flex": 1, "minWidth": 0},
                                ),
                                field("Start Year", "rent_year", s["rent_year"], ""),
                                field(
                                    "Annual Growth",
                                    "rent_growth",
                                    s["rent_growth"],
                                    "%",
                                ),
                            ],
                            style={
                                "display": "flex",
                                "gap": "12px",
                                "flexWrap": "wrap",
                            },
                        ),
                        style={"flex": 1.4},
                    ),
                    card(
                        "Variable Rate Overrides",
                        html.Div(
                            [
                                html.Div(
                                    [
                                        field("Year", "var_year", None),
                                        field("Rate", "var_rate", None, "%"),
                                        field("New Tenure", "var_tenure", None, "yrs"),
                                        html.Div(
                                            [
                                                html.Span(
                                                    "\u00a0", className="field-label"
                                                ),
                                                html.Button(
                                                    "Add",
                                                    id="add_rate",
                                                    className="btn-gold",
                                                ),
                                            ],
                                            style={
                                                "flex": "0 0 auto",
                                                "whiteSpace": "nowrap",
                                            },
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "gap": "10px",
                                        "marginBottom": "6px",
                                    },
                                ),
                                html.Div(
                                    "Leave New Tenure blank to keep paying off on the current schedule; "
                                    "set it to remortgage onto a fresh term (e.g. a new 20-year deal) from that year.",
                                    style={
                                        "fontFamily": "DM Mono, monospace",
                                        "fontSize": "0.62rem",
                                        "color": C["muted"],
                                        "marginBottom": "8px",
                                    },
                                ),
                                html.Div(className="divider"),
                                html.Div(
                                    id="rate_table",
                                    children=html.Div(
                                        "No overrides added",
                                        style={
                                            "fontFamily": "DM Mono, monospace",
                                            "fontSize": "0.7rem",
                                            "color": C["muted"],
                                            "textAlign": "center",
                                            "padding": "12px 0",
                                        },
                                    ),
                                    style={"maxHeight": "110px", "overflowY": "auto"},
                                ),
                            ]
                        ),
                        style={"flex": 1},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "marginBottom": "16px"},
            ),
            # ── ROW 4: Analysis Tabs ───────────────────
            html.Div(
                [
                    html.Div(
                        [
                            html.Button(
                                "Loan Amortisation",
                                id="tab-amort",
                                className="tab-btn active",
                                **{"data-tab": "amort"},
                            ),
                            html.Button(
                                "Rental Projection",
                                id="tab-rental",
                                className="tab-btn",
                                **{"data-tab": "rental"},
                            ),
                            html.Button(
                                "EMI & Rates",
                                id="tab-emi",
                                className="tab-btn",
                                **{"data-tab": "emi"},
                            ),
                            html.Button(
                                "Prepayments",
                                id="tab-prepay",
                                className="tab-btn",
                                **{"data-tab": "prepay"},
                            ),
                            html.Button(
                                "Exit Strategy",
                                id="tab-exit",
                                className="tab-btn",
                                **{"data-tab": "exit"},
                            ),
                        ],
                        className="tab-bar",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    chart_wrap("balance_chart", "380px"),
                                    html.Div(
                                        [
                                            html.Div(
                                                chart_wrap(
                                                    "interest_principal_chart", "320px"
                                                ),
                                                style={"flex": 1, "minWidth": 0},
                                            ),
                                            html.Div(
                                                chart_wrap(
                                                    "cumulative_interest_chart", "320px"
                                                ),
                                                style={"flex": 1, "minWidth": 0},
                                            ),
                                        ],
                                        style={"display": "flex", "gap": "0px"},
                                    ),
                                ],
                                id="panel-amort",
                                style={"padding": "20px"},
                            ),
                            html.Div(
                                [
                                    chart_wrap("rental_chart", "320px"),
                                    html.Div(
                                        [
                                            html.Div(
                                                chart_wrap(
                                                    "cumulative_cashflow_chart", "300px"
                                                ),
                                                style={"flex": 1, "minWidth": 0},
                                            ),
                                            html.Div(
                                                chart_wrap(
                                                    "rent_breakdown_chart", "300px"
                                                ),
                                                style={"flex": 1, "minWidth": 0},
                                            ),
                                        ],
                                        style={"display": "flex", "gap": "0px"},
                                    ),
                                    html.Div(id="rental_summary"),
                                ],
                                id="panel-rental",
                                style={"padding": "20px", "display": "none"},
                            ),
                            html.Div(
                                chart_wrap("emi_chart", "420px"),
                                id="panel-emi",
                                style={"padding": "20px", "display": "none"},
                            ),
                            html.Div(
                                chart_wrap("prepayment_chart", "420px"),
                                id="panel-prepay",
                                style={"padding": "20px", "display": "none"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            field(
                                                "Year of Sale",
                                                "sell_year",
                                                s["sell_year"],
                                            ),
                                            field(
                                                "Property Price Growth (Annual)",
                                                "sell_price",
                                                s["sell_price"],
                                                "%",
                                            ),
                                            field(
                                                "Selling Costs",
                                                "selling_costs",
                                                s["selling_costs"],
                                                currency,
                                            ),
                                            field(
                                                "Annual Inflation",
                                                "inflation",
                                                s["inflation"],
                                                "%",
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "gap": "14px",
                                            "background": C["surface"],
                                            "borderRadius": "8px",
                                            "padding": "16px",
                                            "marginBottom": "20px",
                                            "border": f"1px solid {C['border']}",
                                        },
                                    ),
                                    html.Div(id="selling_output"),
                                ],
                                id="panel-exit",
                                style={"padding": "20px", "display": "none"},
                            ),
                        ],
                        style={
                            "background": C["panel"],
                            "borderRadius": "0 0 10px 10px",
                            "border": f"1px solid {C['border']}",
                            "borderTop": "none",
                        },
                    ),
                ],
                style={"marginBottom": "24px"},
            ),
        ],
        className="page-inner",
    )


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# SCENARIO RULE TABLE HELPERS (multi-rule prepayment / variable rate)
# ─────────────────────────────────────────────
def _sc_rule_row(left_text, right_text, delete_id):
    return html.Div(
        [
            html.Div(
                [
                    html.Span(left_text, className="rate-year"),
                    html.Span(f"  {right_text}", className="rate-val"),
                ]
            ),
            html.Button(
                html.I(className="bi bi-x"),
                className="btn-ghost",
                id=delete_id,
                style={"padding": "2px 6px"},
            ),
        ],
        className="rate-row",
    )


def sc_prepay_table(idx, rules, currency):
    rules = rules or []
    if not rules:
        return html.Div(
            "No rules added",
            style={
                "fontFamily": "DM Mono, monospace",
                "fontSize": "0.68rem",
                "color": C["muted"],
                "textAlign": "center",
                "padding": "8px 0",
            },
        )
    rows = []
    for ri, r in enumerate(rules):
        yr_range = f"YR {r.get('start_year', 1)}"
        yr_range += f"\u2013{r['stop_year']}" if r.get("stop_year") else "\u2192\u221e"
        val = (
            f"{r.get('pct', 0)}% bal"
            if r.get("type") == "percent"
            else f"{currency}{r.get('amount', 0):,.0f}/yr"
        )
        rows.append(
            _sc_rule_row(
                yr_range, val, {"type": "sc-prepay-delete", "index": f"{idx}:{ri}"}
            )
        )
    return html.Div(rows)


def sc_rate_table(idx, rates):
    rates = rates or []
    if not rates:
        return html.Div(
            "No overrides added",
            style={
                "fontFamily": "DM Mono, monospace",
                "fontSize": "0.68rem",
                "color": C["muted"],
                "textAlign": "center",
                "padding": "8px 0",
            },
        )
    rows = []
    for ri, r in enumerate(rates):
        label = f"{r.get('rate')}%"
        if r.get("new_tenure_years"):
            label += f" \u2192 {r['new_tenure_years']:g}yr term"
        rows.append(
            _sc_rule_row(
                f"YR {r.get('year')}",
                label,
                {"type": "sc-rate-delete", "index": f"{idx}:{ri}"},
            )
        )
    return html.Div(rows)


def scenario_input_col(
    idx, color, label, currency, prefill=None, show_rental_exit=False
):
    accent = color
    p = prefill or {}
    re_style = {} if show_rental_exit else {"display": "none"}
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        f"Scenario {label}",
                        style={
                            "fontFamily": "DM Serif Display, serif",
                            "fontSize": "1rem",
                            "color": accent,
                        },
                    ),
                    dbc.Input(
                        id={"type": "sc-name", "index": idx},
                        value=p.get("name", f"Scenario {label}"),
                        className="input-dark",
                        style={
                            "fontSize": "0.72rem",
                            "padding": "4px 8px",
                            "border": f"1px solid {accent}44",
                            "marginTop": "6px",
                        },
                    ),
                ],
                style={
                    "borderBottom": f"2px solid {accent}",
                    "paddingBottom": "10px",
                    "marginBottom": "16px",
                },
            ),
            html.Div(
                "Core Mortgage",
                className="field-label",
                style={"marginBottom": "8px", "color": C["muted"]},
            ),
            html.Div(
                [
                    sc_field(
                        "Price", "sc-price", idx, p.get("price", 600000), currency
                    ),
                    sc_field(
                        "Buy Costs",
                        "sc-buy-costs",
                        idx,
                        p.get("buy_costs", 25000),
                        currency,
                    ),
                    sc_field("Loan", "sc-loan", idx, p.get("loan", 540000), currency),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "8px"},
            ),
            html.Div(
                [
                    sc_field("Rate", "sc-rate", idx, p.get("rate", 5), "%"),
                    sc_field("Tenure", "sc-tenure", idx, p.get("tenure", 25), "yrs"),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "16px"},
            ),
            html.Div(
                "Prepayment Rules",
                className="field-label",
                style={"marginBottom": "8px", "color": C["muted"]},
            ),
            html.Div(
                [
                    sc_field("Start Yr", "sc-prepay-start-input", idx, 1),
                    sc_field("Stop Yr", "sc-prepay-stop-input", idx, None),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "6px"},
            ),
            html.Div(
                [
                    sc_field("Fixed/yr", "sc-prepay-amount-input", idx, 0, currency),
                    sc_field("% Bal", "sc-prepay-pct-input", idx, 0, "%"),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "6px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Type", className="field-label"),
                            dark_dropdown(
                                {"type": "sc-prepay-type", "index": idx},
                                options=[
                                    {"label": "Fixed Amount", "value": "fixed"},
                                    {"label": "% of Balance", "value": "percent"},
                                ],
                                value="fixed",
                            ),
                        ],
                        style={"flex": 1, "minWidth": 0},
                    ),
                    html.Button(
                        [html.I(className="bi bi-plus-lg"), " Add"],
                        id={"type": "sc-prepay-add", "index": idx},
                        className="btn-gold",
                        style={
                            "alignSelf": "flex-end",
                            "fontSize": "0.72rem",
                            "padding": "5px 10px",
                            "flex": "0 0 auto",
                            "whiteSpace": "nowrap",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "8px",
                    "marginBottom": "8px",
                    "alignItems": "flex-end",
                },
            ),
            html.Div(
                id={"type": "sc-prepay-table", "index": idx},
                children=sc_prepay_table(idx, p.get("prepayment_rules"), currency),
                style={
                    "maxHeight": "90px",
                    "overflowY": "auto",
                    "marginBottom": "16px",
                },
            ),
            html.Div(
                "Variable Rate Overrides",
                className="field-label",
                style={"marginBottom": "8px", "color": C["muted"]},
            ),
            html.Div(
                [
                    sc_field("Year", "sc-rate-year-input", idx, None),
                    sc_field("Rate", "sc-rate-val-input", idx, None, "%"),
                ],
                style={
                    "display": "flex",
                    "gap": "8px",
                    "marginBottom": "6px",
                },
            ),
            html.Div(
                [
                    sc_field("New Tenure", "sc-rate-tenure-input", idx, None, "yrs"),
                    html.Button(
                        [html.I(className="bi bi-plus-lg"), " Add"],
                        id={"type": "sc-rate-add", "index": idx},
                        className="btn-gold",
                        style={
                            "alignSelf": "flex-end",
                            "fontSize": "0.72rem",
                            "padding": "5px 10px",
                            "flex": "0 0 auto",
                            "whiteSpace": "nowrap",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "8px",
                    "marginBottom": "8px",
                    "alignItems": "flex-end",
                },
            ),
            html.Div(
                id={"type": "sc-rate-table", "index": idx},
                children=sc_rate_table(idx, p.get("variable_rates")),
                style={
                    "maxHeight": "90px",
                    "overflowY": "auto",
                    "marginBottom": "16px",
                },
            ),
            html.Div(
                [
                    html.Div(
                        "Rental",
                        className="field-label",
                        style={"marginBottom": "8px", "color": C["muted"]},
                    ),
                    html.Div(
                        [
                            sc_field(
                                "Rent/mo", "sc-rent", idx, p.get("rent", 0), currency
                            ),
                            sc_field("Tax", "sc-tax", idx, p.get("tax", 0), "%"),
                        ],
                        style={"display": "flex", "gap": "8px", "marginBottom": "8px"},
                    ),
                    html.Div(
                        [
                            sc_field("Maint", "sc-maint", idx, p.get("maint", 0), "%"),
                            sc_field(
                                "Growth",
                                "sc-rent-growth",
                                idx,
                                p.get("rent_growth", 2),
                                "%",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "8px",
                            "marginBottom": "16px",
                        },
                    ),
                    html.Div(
                        "Exit Strategy",
                        className="field-label",
                        style={"marginBottom": "8px", "color": C["muted"]},
                    ),
                    html.Div(
                        [
                            sc_field(
                                "Sale Yr", "sc-sell-year", idx, p.get("sell_year", 10)
                            ),
                            sc_field(
                                "Price Gr",
                                "sc-sell-price",
                                idx,
                                p.get("sell_price", 2),
                                "%",
                            ),
                        ],
                        style={"display": "flex", "gap": "8px", "marginBottom": "8px"},
                    ),
                    html.Div(
                        [
                            sc_field(
                                "Inflation",
                                "sc-inflation",
                                idx,
                                p.get("inflation", 2),
                                "%",
                            ),
                            sc_field(
                                "Sell Cost",
                                "sc-sell-cost",
                                idx,
                                p.get("selling_costs", 5000),
                                currency,
                            ),
                        ],
                        style={"display": "flex", "gap": "8px"},
                    ),
                ],
                id={"type": "sc-rental-exit-wrap", "index": idx},
                style=re_style,
            ),
        ],
        style={
            "flex": 1,
            "minWidth": 0,
            "background": C["panel"],
            "border": f"1px solid {C['border2']}",
            "borderRadius": "10px",
            "padding": "18px",
        },
    )


def scenario_comparison_layout(scenarios_data, currency, show_rental_exit=False):
    """scenarios_data: list of prefill dicts (may be empty)"""
    n = len(scenarios_data)

    if n == 0:
        empty_state = html.Div(
            [
                html.I(
                    className="bi bi-layers",
                    style={
                        "fontSize": "2.5rem",
                        "color": C["muted"],
                        "display": "block",
                        "marginBottom": "12px",
                    },
                ),
                html.Div(
                    "No scenarios yet",
                    style={
                        "fontFamily": "DM Serif Display, serif",
                        "fontSize": "1.1rem",
                        "color": C["muted"],
                    },
                ),
                html.Div(
                    'Add scenarios from the Calculator tab using the "Add to Comparison" button, or use the button below.',
                    style={
                        "fontFamily": "Outfit, sans-serif",
                        "fontSize": "0.82rem",
                        "color": C["muted"],
                        "marginTop": "6px",
                        "maxWidth": "380px",
                        "textAlign": "center",
                    },
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
                "justifyContent": "center",
                "padding": "60px 20px",
                "background": C["panel"],
                "border": f"1px solid {C['border2']}",
                "borderRadius": "12px",
                "marginBottom": "20px",
            },
        )
        cols_section = empty_state
    else:
        cols = [
            scenario_input_col(
                i,
                SCENARIO_COLORS[i],
                SCENARIO_LABELS[i],
                currency,
                scenarios_data[i],
                show_rental_exit,
            )
            for i in range(n)
        ]
        cols_section = html.Div(
            cols,
            id="sc-cols",
            style={
                "display": "flex",
                "gap": "14px",
                "marginBottom": "20px",
                "alignItems": "flex-start",
            },
        )

    btn_row = html.Div(
        [
            html.Button(
                [html.I(className="bi bi-plus-lg"), " Add Blank Scenario"],
                id="sc-add-btn",
                className="btn-gold",
                disabled=n >= 3,
                style={"opacity": "0.4" if n >= 3 else "1"},
            ),
            html.Button(
                [html.I(className="bi bi-dash-lg"), " Remove Last"],
                id="sc-remove-btn",
                className="btn-ghost",
                disabled=n == 0,
                style={"opacity": "0.4" if n == 0 else "1", "marginLeft": "8px"},
            ),
            html.Span(
                f"{n}/3 scenarios",
                style={
                    "fontFamily": "DM Mono, monospace",
                    "fontSize": "0.7rem",
                    "color": C["muted"],
                    "marginLeft": "12px",
                    "alignSelf": "center",
                },
            ),
            html.Button(
                [
                    html.I(
                        className=(
                            "bi bi-eye-slash" if show_rental_exit else "bi bi-eye"
                        )
                    ),
                    " Hide Rental & Exit" if show_rental_exit else " Add Rental & Exit",
                ],
                id="sc-toggle-rental-exit-btn",
                className="btn-ghost",
                style={"marginLeft": "12px"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "16px"},
    )

    return html.Div(
        [
            html.Div("Scenario Comparison", className="section-label"),
            html.Div(
                [
                    html.Div(
                        "Compare Scenarios",
                        style={
                            "fontFamily": "DM Serif Display, serif",
                            "fontSize": "1.6rem",
                            "color": C["platinum"],
                        },
                    ),
                    html.Div(
                        "Add up to 3 scenarios from the Calculator or manually here.",
                        style={
                            "fontFamily": "Outfit, sans-serif",
                            "fontSize": "0.85rem",
                            "color": C["muted"],
                            "marginTop": "4px",
                        },
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            btn_row,
            cols_section if n > 0 else cols_section,
            # Always render sc-cols so pattern callbacks can still resolve (hidden when empty)
            html.Div(id="sc-cols", style={"display": "none"}) if n == 0 else html.Div(),
            html.Button(
                [html.I(className="bi bi-bar-chart-line"), " Run Comparison"],
                id="sc-run-btn",
                className="btn-gold",
                disabled=n == 0,
                style={
                    "marginBottom": "24px",
                    "fontSize": "0.85rem",
                    "padding": "8px 20px",
                    "opacity": "0.4" if n == 0 else "1",
                },
            ),
            html.Div(id="sc-results"),
        ],
        className="page-inner",
    )


# ─────────────────────────────────────────────
# GLOSSARY (unchanged, abbreviated for brevity)
# ─────────────────────────────────────────────
def glossary_layout():
    def g_term(label, definition, tag="input"):
        tag_colors = {
            "input": (C["gold"], "#3a2e10"),
            "output": ("#60a5fa", "#0f1f3a"),
            "plot": ("#a78bfa", "#1e1530"),
        }
        tag_color, tag_bg = tag_colors.get(tag, tag_colors["input"])
        return html.Div(
            [
                html.Div(
                    [
                        html.Span(
                            label,
                            style={
                                "fontFamily": "DM Mono, monospace",
                                "fontSize": "0.75rem",
                                "fontWeight": "500",
                                "color": C["platinum"],
                                "flex": 1,
                            },
                        ),
                        html.Span(
                            tag.upper(),
                            style={
                                "fontFamily": "DM Mono, monospace",
                                "fontSize": "0.58rem",
                                "color": tag_color,
                                "background": tag_bg,
                                "border": f"1px solid {tag_color}44",
                                "borderRadius": "4px",
                                "padding": "2px 7px",
                                "letterSpacing": "1px",
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "marginBottom": "6px",
                    },
                ),
                html.Div(
                    definition,
                    style={
                        "fontFamily": "Outfit, sans-serif",
                        "fontSize": "0.85rem",
                        "color": "#8a93a8",
                        "lineHeight": "1.7",
                    },
                ),
            ],
            style={
                "background": C["panel"],
                "border": f"1px solid {C['border']}",
                "borderRadius": "8px",
                "padding": "14px 16px",
                "marginBottom": "8px",
            },
        )

    def g_section(icon, title, subtitle, items):
        return html.Div(
            [
                html.Div(
                    [
                        html.I(
                            className=f"bi {icon}",
                            style={
                                "color": C["gold"],
                                "fontSize": "1rem",
                                "marginRight": "10px",
                            },
                        ),
                        html.Span(
                            title,
                            style={
                                "fontFamily": "DM Serif Display, serif",
                                "fontSize": "1.1rem",
                                "color": C["platinum"],
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "marginBottom": "4px",
                    },
                ),
                html.Div(
                    subtitle,
                    style={
                        "fontFamily": "Outfit, sans-serif",
                        "fontSize": "0.78rem",
                        "color": C["muted"],
                        "marginBottom": "14px",
                        "paddingLeft": "26px",
                    },
                ),
                *items,
            ],
            style={
                "background": C["surface"],
                "border": f"1px solid {C['border2']}",
                "borderRadius": "10px",
                "padding": "18px 20px",
                "marginBottom": "16px",
            },
        )

    return html.Div(
        [
            # Header
            html.Div(
                [
                    html.Div("Reference", className="section-label"),
                    html.Div(
                        [
                            html.Div(
                                "Mortgage",
                                style={
                                    "fontFamily": "DM Serif Display, serif",
                                    "fontSize": "1.6rem",
                                    "color": C["platinum"],
                                    "lineHeight": "1",
                                },
                            ),
                            html.Div(
                                "Glossary",
                                style={
                                    "fontFamily": "DM Serif Display, serif",
                                    "fontSize": "1.6rem",
                                    "color": C["gold"],
                                },
                            ),
                        ]
                    ),
                    html.Div(
                        "Every input, output, and chart — organised by section.",
                        style={
                            "fontFamily": "Outfit, sans-serif",
                            "fontSize": "0.85rem",
                            "color": C["muted"],
                            "marginTop": "6px",
                        },
                    ),
                    # Legend
                    html.Div(
                        [
                            html.Span(
                                [
                                    html.Span(
                                        "INPUT",
                                        style={
                                            "background": "#3a2e10",
                                            "color": C["gold"],
                                            "border": f"1px solid {C['gold']}44",
                                            "borderRadius": "4px",
                                            "padding": "2px 7px",
                                            "fontFamily": "DM Mono, monospace",
                                            "fontSize": "0.58rem",
                                            "letterSpacing": "1px",
                                        },
                                    ),
                                    html.Span(
                                        " — value you enter",
                                        style={"marginLeft": "6px"},
                                    ),
                                ]
                            ),
                            html.Span(
                                [
                                    html.Span(
                                        "OUTPUT",
                                        style={
                                            "background": "#0f1f3a",
                                            "color": "#60a5fa",
                                            "border": "1px solid #60a5fa44",
                                            "borderRadius": "4px",
                                            "padding": "2px 7px",
                                            "fontFamily": "DM Mono, monospace",
                                            "fontSize": "0.58rem",
                                            "letterSpacing": "1px",
                                        },
                                    ),
                                    html.Span(
                                        " — calculated result",
                                        style={"marginLeft": "6px"},
                                    ),
                                ]
                            ),
                            html.Span(
                                [
                                    html.Span(
                                        "PLOT",
                                        style={
                                            "background": "#1e1530",
                                            "color": "#a78bfa",
                                            "border": "1px solid #a78bfa44",
                                            "borderRadius": "4px",
                                            "padding": "2px 7px",
                                            "fontFamily": "DM Mono, monospace",
                                            "fontSize": "0.58rem",
                                            "letterSpacing": "1px",
                                        },
                                    ),
                                    html.Span(
                                        " — chart or visualisation",
                                        style={"marginLeft": "6px"},
                                    ),
                                ]
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "20px",
                            "marginTop": "14px",
                            "flexWrap": "wrap",
                            "fontFamily": "Outfit, sans-serif",
                            "fontSize": "0.8rem",
                            "color": C["muted"],
                        },
                    ),
                ],
                style={"marginBottom": "28px"},
            ),
            # ── Section 1: Core Mortgage ──────────────────────────────────────
            g_section(
                "bi-house-door",
                "Core Mortgage",
                "The fundamental loan parameters that drive every calculation.",
                [
                    g_term(
                        "Market Price",
                        "The full purchase price of the property in the selected currency. Used to calculate the "
                        "Loan-to-Value (LTV) ratio and as the base for the Exit Strategy sale price.",
                        "input",
                    ),
                    g_term(
                        "Loan Amount",
                        "The amount borrowed from the lender. Must be less than or equal to the Market Price. "
                        "The difference between Market Price and Loan Amount is your deposit.",
                        "input",
                    ),
                    g_term(
                        "Annual Rate",
                        "The base interest rate for the mortgage, expressed as a percentage per year. Divided by 12 "
                        "internally to compute monthly interest on the outstanding balance. If variable rate overrides "
                        "are added, this rate applies only until the first override year.",
                        "input",
                    ),
                    g_term(
                        "Initial Tenure",
                        "The total mortgage term in years. Year 1 covers months 1–12, year 2 covers months 13–24, "
                        "and so on. Longer tenures reduce the monthly EMI but significantly increase total interest paid.",
                        "input",
                    ),
                    g_term(
                        "Scenario Name",
                        "A label for the current calculator state. Used as the scenario title when adding to the "
                        "Comparison tab via the ‘Add to Comparison’ button.",
                        "input",
                    ),
                ],
            ),
            # ── Section 2: Prepayment ─────────────────────────────────────────
            g_section(
                "bi-arrow-down-circle",
                "Prepayment Strategy",
                "Optional extra payments made once per year on top of the regular EMI, applied directly to the principal.",
                [
                    g_term(
                        "Type",
                        "Fixed Amount: a fixed sum is paid at the end of each year regardless of the balance. "
                        "% of Balance: a percentage of the outstanding balance at year-end is paid off. "
                        "Both options keep the EMI unchanged — the reduced balance simply clears the loan earlier.",
                        "input",
                    ),
                    g_term(
                        "Annual Amount",
                        "Active when Type is Fixed Amount. The value deducted from the outstanding balance at the "
                        "end of each year. Has no effect when Type is % of Balance.",
                        "input",
                    ),
                    g_term(
                        "% of Balance",
                        "Active when Type is % of Balance. The percentage of the remaining balance paid off at "
                        "year-end. Has no effect when Type is Fixed Amount.",
                        "input",
                    ),
                    g_term(
                        "Start Yr / Stop Yr",
                        "Years are 1-indexed, not 0-indexed — there is no Year 0. Start Yr 1 means the first "
                        "prepayment is applied at the end of Year 1 (month 12), not at origination. Stop Yr is "
                        "inclusive: a rule with Start Yr 1 and Stop Yr 5 fires at the end of years 1, 2, 3, 4, and 5 "
                        "— five prepayments total. Leave Stop Yr blank for the rule to continue for the rest of the "
                        "loan term.",
                        "input",
                    ),
                ],
            ),
            # ── Section 3: KPI Outputs ────────────────────────────────────────
            g_section(
                "bi-speedometer2",
                "Summary KPIs",
                "The four headline figures shown immediately below the loan inputs.",
                [
                    g_term(
                        "Monthly EMI",
                        "Equated Monthly Instalment — the fixed payment due each month covering both interest and "
                        "principal. Calculated at origination using the standard annuity formula. If a variable rate "
                        "override is added, the EMI recalculates at the start of that rate’s year on the then-remaining "
                        "balance and remaining months. The value shown is always the initial EMI.",
                        "output",
                    ),
                    g_term(
                        "Total Interest",
                        "The cumulative sum of all interest payments across the entire loan schedule, accounting for "
                        "variable rate changes and any prepayments. Prepayments reduce this substantially by shrinking "
                        "the outstanding balance sooner.",
                        "output",
                    ),
                    g_term(
                        "Effective Interest Rate",
                        "Total interest paid expressed as a percentage of the original loan amount. Useful for comparing "
                        "the true cost of different rate and prepayment combinations independent of loan size.",
                        "output",
                    ),
                    g_term(
                        "Payoff Years",
                        "The actual number of years until the loan balance reaches zero. With no prepayments this "
                        "equals the Tenure. With prepayments the EMI stays the same but the balance clears earlier, "
                        "so this figure falls below the full Tenure.",
                        "output",
                    ),
                ],
            ),
            # ── Section 4: Variable Rate Overrides ───────────────────────────
            g_section(
                "bi-graph-up-arrow",
                "Variable Rate Overrides",
                "Model remortgages or rate resets at specific points during the loan.",
                [
                    g_term(
                        "Year",
                        "The year number from which the new rate takes effect. Year 2 means the change kicks in at "
                        "the start of month 13 (after 12 complete months). The new rate persists until a later override supersedes it.",
                        "input",
                    ),
                    g_term(
                        "Rate",
                        "The new annual interest rate (%) applied from the specified year onwards. The EMI is "
                        "recalculated at that point using the remaining balance, preserving the loan's current "
                        "payoff trajectory (including the effect of any prepayments already made) unless a "
                        "New Tenure is also set.",
                        "input",
                    ),
                    g_term(
                        "New Tenure",
                        "Optional. When remortgaging, lenders typically let you choose a new loan term, not just a new "
                        "rate. Set this to the new term length in years to reset the remaining payoff schedule from "
                        "that point — e.g. remortgaging onto a fresh 20-year deal in year 5 resets the clock so the "
                        "loan now runs for 20 more years from year 5. Leave blank to keep the loan on its current "
                        "implied payoff date and just change the rate.",
                        "input",
                    ),
                ],
            ),
            # ── Section 5: Amortisation Charts ───────────────────────────────
            g_section(
                "bi-bar-chart-line",
                "Loan Amortisation Charts",
                "Three charts under the Loan Amortisation tab showing how the balance and payments evolve.",
                [
                    g_term(
                        "Outstanding Balance (gold area)",
                        "The remaining loan balance at each month. Falls slowly at first — when most of each EMI is "
                        "interest — and accelerates toward the end as more of each payment reduces the principal. "
                        "Annual prepayments appear as sudden vertical drops in the curve.",
                        "plot",
                    ),
                    g_term(
                        "Interest vs Principal Bars",
                        "Monthly breakdown of each EMI into interest paid (red) and principal repaid (green). "
                        "The interest bar shrinks and the principal bar grows steadily as the balance falls over time. "
                        "Rate changes cause a visible step in both series at the month the new rate takes effect.",
                        "plot",
                    ),
                    g_term(
                        "Cumulative Interest Chart",
                        "Running total of all interest paid to date, plotted month by month. The curve rises steeply "
                        "early in the loan when interest dominates each EMI, and flattens as the balance — and therefore "
                        "the monthly interest charge — shrinks. Useful for seeing the total cost of credit at any point in time.",
                        "plot",
                    ),
                ],
            ),
            # ── Section 6: EMI & Rates Chart ─────────────────────────────────
            g_section(
                "bi-activity",
                "EMI & Rate Periods",
                "Shows the monthly EMI broken into interest and principal, with rate change periods highlighted.",
                [
                    g_term(
                        "EMI Line (purple)",
                        "The total monthly payment amount across the loan. Flat within each rate period. Steps up "
                        "when the rate rises or down when it falls, because the EMI is recalculated on the remaining "
                        "balance at each rate change.",
                        "plot",
                    ),
                    g_term(
                        "Interest Area (red)",
                        "The portion of each monthly EMI paid to the lender as interest. Starts high and steadily "
                        "declines as the outstanding balance falls over time.",
                        "plot",
                    ),
                    g_term(
                        "Principal Area (green)",
                        "The portion of each monthly EMI that reduces the outstanding balance. Starts low and grows "
                        "as the interest portion shrinks.",
                        "plot",
                    ),
                    g_term(
                        "Rate Period Bands & Labels",
                        "Shaded background regions, each representing one rate period. The applicable annual rate "
                        "is labelled at the top of each band. Dashed vertical lines mark the exact month where each "
                        "rate change takes effect.",
                        "plot",
                    ),
                ],
            ),
            # ── Section 7: Rental Analysis ───────────────────────────────────
            g_section(
                "bi-house-check",
                "Rental Analysis",
                "Models the property as a buy-to-let, calculating monthly cashflow after all costs, tax, and mortgage.",
                [
                    g_term(
                        "Monthly Rent",
                        "The rent charged to tenants at the start of the rental period, per month. "
                        "This is the base figure before any annual rent growth is applied.",
                        "input",
                    ),
                    g_term(
                        "Tax Rate",
                        "Your marginal income tax rate as a percentage. Applied to taxable rental profit. "
                        "The exact calculation depends on the Tax Mode selected.",
                        "input",
                    ),
                    g_term(
                        "Maintenance",
                        "Annual costs expressed as a percentage of gross rent. Intended to cover repairs, letting "
                        "agent fees, insurance, and other recurring property expenses.",
                        "input",
                    ),
                    g_term(
                        "Tax Mode",
                        "Simple: tax applied to rent minus costs minus mortgage interest. "
                        "UK (Section 24): tax applied to rent minus costs only, with a separate 20% credit on "
                        "mortgage interest — reflecting post-2017 UK rules for residential landlords. "
                        "Harsh: tax applied to the full gross rent with no deductions whatsoever.",
                        "input",
                    ),
                    g_term(
                        "Start Year",
                        "The year from which rental income begins. Year 1 means renting from the first month of "
                        "ownership. Year 3 means the first two years are owner-occupied or vacant and cashflow is "
                        "only modelled from year 3 onwards.",
                        "input",
                    ),
                    g_term(
                        "Annual Growth",
                        "Annual percentage increase in rent, compounded year-on-year. In year N the effective "
                        "monthly rent is: Monthly Rent × (1 + growth/100)^(N−1). "
                        "For example, 3% growth on £1,500 gives £1,545 in year 2 and £1,591 in year 3.",
                        "input",
                    ),
                    g_term(
                        "Rental Projection Chart (blue line)",
                        "Monthly net cashflow for each year of the loan: rent after costs and tax, minus the "
                        "monthly EMI for that year. Green shading above zero means the property is cashflow positive "
                        "— rent covers the mortgage and costs. Red shading below zero means it is loss-making.",
                        "plot",
                    ),
                    g_term(
                        "Cumulative Cashflow Chart",
                        "Running total of all net monthly cashflows over the life of the loan. Shows the cumulative "
                        "surplus or deficit built up from the rental income after all costs and mortgage payments. "
                        "Crossing zero means the property has broken even on cashflow.",
                        "plot",
                    ),
                    g_term(
                        "Rent Breakdown Chart",
                        "Annual stacked bar chart decomposing gross rent into its components: mortgage EMI, maintenance "
                        "costs, tax paid, and net profit retained. Gives a clear picture of where each pound of rent goes "
                        "and how the split shifts over time as rent grows and interest costs fall.",
                        "plot",
                    ),
                ],
            ),
            # ── Section 8: Exit Strategy ──────────────────────────────────────
            g_section(
                "bi-door-open",
                "Exit Strategy",
                "Models the financial outcome of selling the property at a chosen point in time.",
                [
                    g_term(
                        "Year of Sale",
                        "The year in which the property is sold. Year 10 means the sale occurs at the end of the "
                        "10th year of ownership. The outstanding mortgage balance at that exact point is deducted "
                        "from the sale price to arrive at proceeds.",
                        "input",
                    ),
                    g_term(
                        "Property Price Growth (Annual)",
                        "Yearly percentage increase in property value from the original Market Price to the sale, "
                        "applied as an annual compound rate.",
                        "input",
                    ),
                    g_term(
                        "Selling Costs",
                        "Flat transaction costs deducted from the gross sale price when calculating proceeds and profit. "
                        "Intended to cover estate agent fees, legal costs, and any other sale expenses.",
                        "input",
                    ),
                    g_term(
                        "Annual Inflation",
                        "The assumed average annual inflation rate, used to discount the future sale price back to "
                        "today’s purchasing power. Higher inflation erodes the real value of future proceeds.",
                        "input",
                    ),
                    g_term(
                        "Sale Proceeds",
                        "Gross sale price minus the outstanding mortgage balance at the year of sale, minus selling costs. "
                        "This is the cash in hand after clearing the mortgage and transaction costs.",
                        "output",
                    ),
                    g_term(
                        "Remaining Loan",
                        "The outstanding mortgage balance at the year of sale, taken directly from the amortisation "
                        "schedule. Zero if the loan has already been fully paid off before the sale year.",
                        "output",
                    ),
                    g_term(
                        "Net Profit",
                        "Nominal property appreciation gain: selling price minus original purchase price minus selling costs. "
                        "Does not account for inflation or financing costs.",
                        "output",
                    ),
                    g_term(
                        "Inflation-Adjusted Value",
                        "The sale price discounted by compound inflation over the holding period: "
                        "Sale Price ÷ (1 + inflation/100)^years. Represents what the sale price is worth "
                        "in today’s money.",
                        "output",
                    ),
                    g_term(
                        "Real Profit (After Inflation)",
                        "Inflation-adjusted appreciation gain: inflation-adjusted sale price minus original purchase price "
                        "minus selling costs. Reflects appreciation in real purchasing power terms.",
                        "output",
                    ),
                    g_term(
                        "Financial Profit",
                        "Actual financial gain after financing costs: nominal appreciation gain minus total mortgage "
                        "interest paid over the holding period.",
                        "output",
                    ),
                    g_term(
                        "Financial Profit (After Inflation)",
                        "Inflation-adjusted actual financial gain after accounting for both inflation and financing costs. "
                        "Represents the estimated real increase in purchasing power generated from the property investment.",
                        "output",
                    ),
                ],
            ),
            # ── Section 9: Scenario Comparison ───────────────────────────────
            g_section(
                "bi-layers",
                "Scenario Comparison",
                "Compare up to 3 mortgage scenarios side by side across all key metrics and charts.",
                [
                    g_term(
                        "Add to Comparison",
                        "Button on the Calculator tab that saves the current calculator state as a named scenario "
                        "and queues it for comparison. Up to 3 scenarios can be queued.",
                        "input",
                    ),
                    g_term(
                        "Add Blank Scenario",
                        "Adds a new empty scenario column directly on the Compare tab with default values, "
                        "which can then be edited manually.",
                        "input",
                    ),
                    g_term(
                        "Remove Last",
                        "Removes the most recently added scenario column from the comparison.",
                        "input",
                    ),
                    g_term(
                        "Scenario Inputs (Price, Loan, Rate, Tenure)",
                        "Core mortgage fields per scenario. Same meaning as the Calculator equivalents. "
                        "Rate is the starting annual rate; use the Variable Rate fields below to apply a rate change.",
                        "input",
                    ),
                    g_term(
                        "Scenario Inputs (Prepayment: Fixed/yr, % Bal, Start/Stop Yr)",
                        "Per-scenario prepayment fields. Fixed/yr sets an annual fixed prepayment amount; "
                        "% Bal sets an annual percentage-of-balance prepayment (only one is active at a time per scenario). "
                        "Start Yr / Stop Yr control which years the prepayment applies to (1-indexed — Start Yr 1 "
                        "is the end of the first year; Stop Yr is inclusive; leave Stop Yr blank for no end).",
                        "input",
                    ),
                    g_term(
                        "Scenario Inputs (Variable Rate: Change Yr, New Rate, New Tenure)",
                        "Per-scenario rate override. Change Yr is the year from which the new rate applies; "
                        "New Rate is the annual interest rate from that year onward. EMI is recalculated automatically "
                        "at the point of change, preserving the loan's current payoff trajectory. New Tenure is optional — "
                        "set it to model remortgaging onto a fresh term (e.g. a new 20-year deal) starting that year, "
                        "which resets the payoff schedule instead of just preserving it. Leave both rate fields blank "
                        "to keep a single fixed rate for the whole tenure.",
                        "input",
                    ),
                    g_term(
                        "Scenario Inputs (Rental: Rent/mo, Tax, Maint, Growth)",
                        "Per-scenario rental fields. Rent/mo is the base monthly rent; Tax is the marginal tax rate; "
                        "Maint is annual maintenance as % of rent; Growth is the annual rent increase rate. "
                        "Tax mode is fixed to UK (Section 24) in comparison mode.",
                        "input",
                    ),
                    g_term(
                        "Scenario Inputs (Exit: Sale Yr, Price Gr, Inflation, Sell Cost)",
                        "Per-scenario exit fields. Sale Yr is the year of sale; Price Gr is annual property price growth; "
                        "Inflation discounts proceeds to today’s money; Sell Cost is flat transaction costs.",
                        "input",
                    ),
                    g_term(
                        "KPI Table",
                        "Side-by-side comparison of all headline metrics: Monthly EMI, Total Interest, Effective Rate, "
                        "Payoff Years, Yr 1 Cashflow/mo, Sale Proceeds, and Net Financial Profit. "
                        "The best value in each row is highlighted with a star and green text.",
                        "output",
                    ),
                    g_term(
                        "Yr 1 Net Cashflow/mo",
                        "The net monthly rental cashflow in the first year of rental: monthly rent after costs and tax, "
                        "minus the monthly EMI. A negative value means the rental income does not cover the mortgage "
                        "and costs in year 1.",
                        "output",
                    ),
                    g_term(
                        "Effective Rate (Comparison)",
                        "Total interest paid as a percentage of the original loan for each scenario. "
                        "Allows direct comparison of the true financing cost across different rate and prepayment strategies.",
                        "output",
                    ),
                    g_term(
                        "Monthly EMI Bar",
                        "Bar chart comparing the initial monthly EMI across scenarios. Lower is better.",
                        "plot",
                    ),
                    g_term(
                        "Total Interest Bar",
                        "Bar chart comparing cumulative interest paid across scenarios. Lower is better.",
                        "plot",
                    ),
                    g_term(
                        "Payoff Years Bar",
                        "Bar chart comparing actual loan duration across scenarios. Lower is better.",
                        "plot",
                    ),
                    g_term(
                        "Yr 1 Cashflow Bar",
                        "Bar chart comparing first-year monthly net rental cashflow. Higher is better.",
                        "plot",
                    ),
                    g_term(
                        "Sale Proceeds Bar",
                        "Bar chart comparing gross sale proceeds at the chosen sale year. Higher is better.",
                        "plot",
                    ),
                    g_term(
                        "Net Financial Profit Bar",
                        "Bar chart comparing net financial profit (appreciation minus interest). Higher is better.",
                        "plot",
                    ),
                    g_term(
                        "Balance Trajectories",
                        "Overlaid line chart showing the outstanding balance curve for all scenarios on a single axis. "
                        "Steeper curves indicate faster principal repayment.",
                        "plot",
                    ),
                    g_term(
                        "EMI Trajectories",
                        "Overlaid line chart showing the monthly instalment (averaged per year) for all scenarios. "
                        "Step changes reflect variable rate overrides or EMI recalculations.",
                        "plot",
                    ),
                ],
            ),
        ],
        className="page-inner",
    )


# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────
app.layout = html.Div(
    [
        sidebar,
        topbar,
        html.Div(
            calculator_layout("£", DEFAULT_CALC),
            id="page-content",
            className="main-content",
        ),
        dcc.Store(id="rates_store", data=[]),
        dcc.Store(id="prepay_rules_store", data=[]),
        dcc.Store(id="active-tab", data="amort"),
        dcc.Store(id="currency-store", data="£"),
        # Persists calculator field values across navigation
        dcc.Store(id="calc-inputs-store", data=DEFAULT_CALC),
        # Persists list of scenario prefill dicts
        dcc.Store(id="scenarios-data-store", data=[]),
        # Whether Rental & Exit Strategy inputs/outputs are shown in Compare tab
        dcc.Store(id="sc-show-rental-exit", data=False),
    ]
)


# ─────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────


@app.callback(
    Output("currency-store", "data"),
    Input("currency-selector", "value"),
)
def update_currency(currency):
    return currency


# ── Save calculator inputs into store whenever they change ────────────────
@app.callback(
    Output("calc-inputs-store", "data"),
    Input("calc-scenario-name", "value"),
    Input("price", "value"),
    Input("buy_costs", "value"),
    Input("loan", "value"),
    Input("rate", "value"),
    Input("tenure", "value"),
    Input("prepay_rules_store", "data"),
    Input("rates_store", "data"),
    Input("rent", "value"),
    Input("tax", "value"),
    Input("maint", "value"),
    Input("rent_year", "value"),
    Input("tax_mode", "value"),
    Input("rent_growth", "value"),
    Input("sell_year", "value"),
    Input("sell_price", "value"),
    Input("selling_costs", "value"),
    Input("inflation", "value"),
    prevent_initial_call=True,
)
def save_calc_inputs(
    scenario_name,
    price,
    buy_costs,
    loan,
    rate,
    tenure,
    prepayment_rules,
    variable_rates,
    rent,
    tax,
    maint,
    rent_year,
    tax_mode,
    rent_growth,
    sell_year,
    sell_price,
    selling_costs,
    inflation,
):
    return {
        "scenario_name": scenario_name or "My Scenario",
        "price": price,
        "buy_costs": buy_costs,
        "loan": loan,
        "rate": rate,
        "tenure": tenure,
        "prepayment_rules": prepayment_rules or [],
        "variable_rates": variable_rates or [],
        "rent": rent,
        "tax": tax,
        "maint": maint,
        "rent_year": rent_year,
        "tax_mode": tax_mode,
        "rent_growth": rent_growth,
        "sell_year": sell_year,
        "sell_price": sell_price,
        "selling_costs": selling_costs,
        "inflation": inflation,
    }


# ── Navigation ────────────────────────────────────────────────────────────
@app.callback(
    Output("page-content", "children"),
    Output("nav-calc", "className"),
    Output("nav-compare", "className"),
    Output("nav-gloss", "className"),
    Input("nav-calc", "n_clicks"),
    Input("nav-compare", "n_clicks"),
    Input("nav-gloss", "n_clicks"),
    Input("currency-store", "data"),
    State("calc-inputs-store", "data"),
    State("scenarios-data-store", "data"),
    State("sc-show-rental-exit", "data"),
)
def navigate(c, cmp, g, currency, calc_state, scenarios_data, show_rental_exit):

    a, i = "nav-item-btn active", "nav-item-btn"

    tid = ctx.triggered_id

    if tid is None or tid == "currency-store":
        return calculator_layout(currency, calc_state), a, i, i

    if tid == "nav-gloss":
        return glossary_layout(), i, i, a

    if tid == "nav-compare":
        return (
            scenario_comparison_layout(
                scenarios_data or [], currency, show_rental_exit or False
            ),
            i,
            a,
            i,
        )

    return calculator_layout(currency, calc_state), a, i, i


# ── Tab switching ─────────────────────────────────────────────────────────
app.clientside_callback(
    """
    function(amort_n, rental_n, emi_n, prepay_n, exit_n) {
        const triggered = window.dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) return window.dash_clientside.no_update;
        const id = triggered[0].prop_id.split('.')[0];
        ['amort','rental','emi','prepay','exit'].forEach(p => {
            const el = document.getElementById('panel-'+p);
            const btn = document.getElementById('tab-'+p);
            if (el) el.style.display = 'none';
            if (btn) btn.className = 'tab-btn';
        });
        let active = id === 'tab-rental' ? 'rental' : id === 'tab-emi' ? 'emi' : id === 'tab-prepay' ? 'prepay' : id === 'tab-exit' ? 'exit' : 'amort';
        const el = document.getElementById('panel-'+active);
        const btn = document.getElementById('tab-'+active);
        if (el) el.style.display = 'block';
        if (btn) btn.className = 'tab-btn active';
        return active;
    }
    """,
    Output("active-tab", "data"),
    Input("tab-amort", "n_clicks"),
    Input("tab-rental", "n_clicks"),
    Input("tab-emi", "n_clicks"),
    Input("tab-prepay", "n_clicks"),
    Input("tab-exit", "n_clicks"),
    prevent_initial_call=True,
)


# ── Variable rates ────────────────────────────────────────────────────────
@app.callback(
    Output("rates_store", "data"),
    Output("rate_table", "children"),
    Output("var_year", "value"),
    Output("var_rate", "value"),
    Output("var_tenure", "value"),
    Input("add_rate", "n_clicks"),
    Input({"type": "delete-rate", "index": ALL}, "n_clicks"),
    State("var_year", "value"),
    State("var_rate", "value"),
    State("var_tenure", "value"),
    State("rates_store", "data"),
    prevent_initial_call=True,
)
def update_rates(add_click, delete_clicks, year, rate, new_tenure, data):
    data = data or []
    triggered = ctx.triggered_id
    if triggered == "add_rate":
        if year is not None and rate is not None:
            entry = {"year": int(year), "rate": float(rate)}
            if new_tenure is not None and new_tenure != "":
                entry["new_tenure_years"] = float(new_tenure)
            data.append(entry)
    elif isinstance(triggered, dict):
        data = [r for i, r in enumerate(data) if i != triggered["index"]]
    data = sorted(data, key=lambda x: x["year"])
    if not data:
        return (
            data,
            html.Div(
                "No overrides added",
                style={
                    "fontFamily": "DM Mono, monospace",
                    "fontSize": "0.7rem",
                    "color": C["muted"],
                    "textAlign": "center",
                    "padding": "12px 0",
                },
            ),
            None,
            None,
            None,
        )
    table = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(f"YR {r['year']}", className="rate-year"),
                            html.Span(f"  {r['rate']}%", className="rate-val"),
                            html.Span(
                                (
                                    f"  \u2192 remortgage, {r['new_tenure_years']:g}yr term"
                                    if r.get("new_tenure_years")
                                    else ""
                                ),
                                className="rate-val",
                                style={"color": C["gold_dim"]},
                            ),
                        ]
                    ),
                    html.Button(
                        html.I(className="bi bi-x"),
                        className="btn-ghost",
                        id={"type": "delete-rate", "index": i},
                    ),
                ],
                className="rate-row",
            )
            for i, r in enumerate(data)
        ]
    )
    return data, table, None, None, None


# ── Prepayment rules ─────────────────────────────────────────────────────
@app.callback(
    Output("prepay_rules_store", "data"),
    Output("prepay_table", "children"),
    Output("prepay_start", "value"),
    Output("prepay_stop", "value"),
    Output("prepay_amount", "value"),
    Output("prepay_pct_input", "value"),
    Input("add_prepay", "n_clicks"),
    Input({"type": "delete-prepay", "index": ALL}, "n_clicks"),
    State("prepay_start", "value"),
    State("prepay_stop", "value"),
    State("prepay_type_input", "value"),
    State("prepay_amount", "value"),
    State("prepay_pct_input", "value"),
    State("prepay_rules_store", "data"),
    State("currency-store", "data"),
    prevent_initial_call=True,
)
def update_prepay_rules(
    add_click, delete_clicks, start, stop, ptype, amount, pct, data, currency
):
    def rule_label(r):
        yr_range = f"YR {r['start_year']}"
        if r.get("stop_year"):
            yr_range += f"\u2013{r['stop_year']}"
        else:
            yr_range += "\u2192\u221e"
        if r["type"] == "percent":
            val = f"{r['pct']}% bal"
        else:
            val = f"{cur}{r['amount']:,.0f}/yr"
        return yr_range, val

    def get_table(data):
        table = html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(f"{rule_label(r)[0]}", className="rate-year"),
                                html.Span(
                                    f"  {rule_label(r)[1]}", className="rate-val"
                                ),
                            ]
                        ),
                        html.Button(
                            html.I(className="bi bi-x"),
                            className="btn-ghost",
                            id={"type": "delete-prepay", "index": i},
                            style={"padding": "2px 6px"},
                        ),
                    ],
                    className="rate-row",
                )
                for i, r in enumerate(data)
            ]
        )
        return table

    data = data or []
    cur = currency or "£"
    if add_click is None and not any(delete_clicks):
        if data:
            table = get_table(data)
            return (
                dash.no_update,
                table,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )
        else:
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )
    triggered = ctx.triggered_id
    if triggered == "add_prepay":
        rule = {
            "start_year": int(start) if start else 1,
            "stop_year": int(stop) if stop else None,
            "type": ptype or "fixed",
            "amount": float(amount or 0),
            "pct": float(pct or 0),
        }
        data = data + [rule]
    elif isinstance(triggered, dict):
        data = [r for i, r in enumerate(data) if i != triggered["index"]]
    if not data:
        return (
            data,
            html.Div(
                "No rules added",
                style={
                    "fontFamily": "DM Mono, monospace",
                    "fontSize": "0.7rem",
                    "color": C["muted"],
                    "textAlign": "center",
                    "padding": "12px 0",
                },
            ),
            None,
            None,
            None,
            None,
        )

    table = get_table(data)
    return data, table, None, None, None, None


# ── Add to comparison from calculator ────────────────────────────────────
@app.callback(
    Output("scenarios-data-store", "data"),
    Output("add-to-comparison-feedback", "children"),
    Input("add-to-comparison-btn", "n_clicks"),
    State("calc-scenario-name", "value"),
    State("calc-inputs-store", "data"),
    State("scenarios-data-store", "data"),
    State("currency-store", "data"),
    prevent_initial_call=True,
)
def add_to_comparison(n_clicks, name, calc_state, scenarios_data, currency):
    if n_clicks is None:
        return dash.no_update, dash.no_update
    scenarios_data = scenarios_data or []
    if len(scenarios_data) >= 3:
        return scenarios_data, "Maximum 3 scenarios reached"
    s = calc_state or DEFAULT_CALC

    new_scenario = {
        "name": name or f"Scenario {SCENARIO_LABELS[len(scenarios_data)]}",
        "price": s.get("price", 600000),
        "buy_costs": s.get("buy_costs", 25000),
        "loan": s.get("loan", 540000),
        "rate": s.get("rate", 5),
        "tenure": s.get("tenure", 25),
        "prepayment_rules": s.get("prepayment_rules") or [],
        "variable_rates": s.get("variable_rates") or [],
        "rent": s.get("rent", 0),
        "tax": s.get("tax", 0),
        "maint": s.get("maint", 0),
        "rent_growth": s.get("rent_growth", 2),
        "sell_year": s.get("sell_year", 10),
        "sell_price": s.get("sell_price", 2),
        "inflation": s.get("inflation", 2),
        "selling_costs": s.get("selling_costs", 5000),
    }
    scenarios_data = scenarios_data + [new_scenario]
    label = new_scenario["name"]
    count = len(scenarios_data)
    return (
        scenarios_data,
        f"✓ '{label}' added ({count}/3) — switch to Compare tab to view",
    )


# ── Add blank / remove scenario on comparison page ───────────────────────
@app.callback(
    Output("page-content", "children", allow_duplicate=True),
    Output("scenarios-data-store", "data", allow_duplicate=True),
    Output("nav-calc", "className", allow_duplicate=True),
    Output("nav-compare", "className", allow_duplicate=True),
    Output("nav-gloss", "className", allow_duplicate=True),
    Output("sc-show-rental-exit", "data", allow_duplicate=True),
    Input("sc-add-btn", "n_clicks"),
    Input("sc-remove-btn", "n_clicks"),
    Input("sc-toggle-rental-exit-btn", "n_clicks"),
    State("scenarios-data-store", "data"),
    State("sc-show-rental-exit", "data"),
    # Capture current field values so we don't lose edits when adding/removing
    State({"type": "sc-name", "index": ALL}, "value"),
    State({"type": "sc-price", "index": ALL}, "value"),
    State({"type": "sc-loan", "index": ALL}, "value"),
    State({"type": "sc-rate", "index": ALL}, "value"),
    State({"type": "sc-tenure", "index": ALL}, "value"),
    State({"type": "sc-rent", "index": ALL}, "value"),
    State({"type": "sc-tax", "index": ALL}, "value"),
    State({"type": "sc-maint", "index": ALL}, "value"),
    State({"type": "sc-rent-growth", "index": ALL}, "value"),
    State({"type": "sc-sell-year", "index": ALL}, "value"),
    State({"type": "sc-sell-price", "index": ALL}, "value"),
    State({"type": "sc-inflation", "index": ALL}, "value"),
    State({"type": "sc-sell-cost", "index": ALL}, "value"),
    State("currency-store", "data"),
    prevent_initial_call=True,
)
def adjust_scenarios(
    add,
    remove,
    toggle_rental_exit,
    stored_data,
    show_rental_exit,
    names,
    prices,
    loans,
    rates,
    tenures,
    rents,
    taxes,
    maints,
    rent_growths,
    sell_years,
    sell_prices,
    inflations,
    sell_costs,
    currency,
):
    # Guard: only fire when a button was actually clicked (not on page mount)
    if add is None and remove is None and toggle_rental_exit is None:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    # Sync any edits made in the fields back to the store first
    n_current = len(stored_data or [])
    synced = []
    for i in range(n_current):
        synced.append(
            {
                "name": (
                    names[i] if i < len(names) else f"Scenario {SCENARIO_LABELS[i]}"
                ),
                "price": prices[i] if i < len(prices) else 600000,
                "loan": loans[i] if i < len(loans) else 540000,
                "rate": rates[i] if i < len(rates) else 5,
                "tenure": tenures[i] if i < len(tenures) else 25,
                "prepayment_rules": (stored_data[i] or {}).get("prepayment_rules", []),
                "variable_rates": (stored_data[i] or {}).get("variable_rates", []),
                "rent": rents[i] if i < len(rents) else 0,
                "tax": taxes[i] if i < len(taxes) else 0,
                "maint": maints[i] if i < len(maints) else 0,
                "rent_growth": rent_growths[i] if i < len(rent_growths) else 2,
                "sell_year": sell_years[i] if i < len(sell_years) else 10,
                "sell_price": sell_prices[i] if i < len(sell_prices) else 2,
                "inflation": inflations[i] if i < len(inflations) else 2,
                "selling_costs": sell_costs[i] if i < len(sell_costs) else 5000,
            }
        )

    tid = ctx.triggered_id
    if tid == "sc-add-btn" and len(synced) < 3:
        synced.append(DEFAULT_CALC.copy())
    elif tid == "sc-remove-btn" and len(synced) > 0:
        synced = synced[:-1]

    new_show_rental_exit = show_rental_exit
    if tid == "sc-toggle-rental-exit-btn":
        new_show_rental_exit = not show_rental_exit

    a, i = "nav-item-btn active", "nav-item-btn"
    return (
        scenario_comparison_layout(synced, currency, new_show_rental_exit),
        synced,
        i,
        a,
        i,
        new_show_rental_exit,
    )


# ── Scenario prepayment rules (multi-rule, add/delete per scenario) ──────
@app.callback(
    Output("scenarios-data-store", "data", allow_duplicate=True),
    Output({"type": "sc-prepay-table", "index": ALL}, "children"),
    Input({"type": "sc-prepay-add", "index": ALL}, "n_clicks"),
    Input({"type": "sc-prepay-delete", "index": ALL}, "n_clicks"),
    State({"type": "sc-prepay-start-input", "index": ALL}, "value"),
    State({"type": "sc-prepay-stop-input", "index": ALL}, "value"),
    State({"type": "sc-prepay-type", "index": ALL}, "value"),
    State({"type": "sc-prepay-amount-input", "index": ALL}, "value"),
    State({"type": "sc-prepay-pct-input", "index": ALL}, "value"),
    State("scenarios-data-store", "data"),
    State("currency-store", "data"),
    prevent_initial_call=True,
)
def update_sc_prepay_rules(
    add_clicks,
    delete_clicks,
    starts,
    stops,
    ptypes,
    amounts,
    pcts,
    stored_data,
    currency,
):
    triggered = ctx.triggered_id
    if not triggered or (not any(add_clicks) and not any(delete_clicks)):
        raise PreventUpdate

    data = [dict(s) for s in (stored_data or [])]

    if triggered["type"] == "sc-prepay-add":
        si = triggered["index"]
        if si < len(data):
            rules = list(data[si].get("prepayment_rules") or [])
            start = starts[si] if si < len(starts) else 1
            stop = stops[si] if si < len(stops) else None
            ptype = ptypes[si] if si < len(ptypes) else "fixed"
            amount = amounts[si] if si < len(amounts) else 0
            pct = pcts[si] if si < len(pcts) else 0
            rules.append(
                {
                    "start_year": int(start) if start else 1,
                    "stop_year": int(stop) if stop else None,
                    "type": ptype or "fixed",
                    "amount": float(amount or 0),
                    "pct": float(pct or 0),
                }
            )
            data[si]["prepayment_rules"] = rules
    elif triggered["type"] == "sc-prepay-delete":
        si, ri = (int(x) for x in triggered["index"].split(":"))
        if si < len(data):
            rules = list(data[si].get("prepayment_rules") or [])
            rules = [r for j, r in enumerate(rules) if j != ri]
            data[si]["prepayment_rules"] = rules

    cur = currency or "£"
    tables = [
        sc_prepay_table(i, data[i].get("prepayment_rules"), cur)
        for i in range(len(data))
    ]
    return data, tables


# ── Scenario variable rate overrides (multi-rule, add/delete per scenario) ─
@app.callback(
    Output("scenarios-data-store", "data", allow_duplicate=True),
    Output({"type": "sc-rate-table", "index": ALL}, "children"),
    Input({"type": "sc-rate-add", "index": ALL}, "n_clicks"),
    Input({"type": "sc-rate-delete", "index": ALL}, "n_clicks"),
    State({"type": "sc-rate-year-input", "index": ALL}, "value"),
    State({"type": "sc-rate-val-input", "index": ALL}, "value"),
    State({"type": "sc-rate-tenure-input", "index": ALL}, "value"),
    State("scenarios-data-store", "data"),
    prevent_initial_call=True,
)
def update_sc_rate_rules(
    add_clicks, delete_clicks, years, vals, new_tenures, stored_data
):
    triggered = ctx.triggered_id
    if not triggered or not any(add_clicks) and not any(delete_clicks):
        raise PreventUpdate

    data = [dict(s) for s in (stored_data or [])]

    if triggered["type"] == "sc-rate-add":
        si = triggered["index"]
        if si < len(data):
            year = years[si] if si < len(years) else None
            val = vals[si] if si < len(vals) else None
            new_tenure = new_tenures[si] if si < len(new_tenures) else None
            if year is not None and val is not None:
                rates = list(data[si].get("variable_rates") or [])
                entry = {"year": int(year), "rate": float(val)}
                if new_tenure is not None and new_tenure != "":
                    entry["new_tenure_years"] = float(new_tenure)
                rates.append(entry)
                rates = sorted(rates, key=lambda r: r["year"])
                data[si]["variable_rates"] = rates
    elif triggered["type"] == "sc-rate-delete":
        si, ri = (int(x) for x in triggered["index"].split(":"))
        if si < len(data):
            rates = list(data[si].get("variable_rates") or [])
            rates = [r for j, r in enumerate(rates) if j != ri]
            data[si]["variable_rates"] = rates

    tables = [sc_rate_table(i, data[i].get("variable_rates")) for i in range(len(data))]
    return data, tables


# ── Main calculator callback ──────────────────────────────────────────────
@app.callback(
    Output("emi", "children"),
    Output("interest", "children"),
    Output("eff_interest_rate", "children"),
    Output("years", "children"),
    Output("balance_chart", "figure"),
    Output("interest_principal_chart", "figure"),
    Output("cumulative_interest_chart", "figure"),
    Output("rental_chart", "figure"),
    Output("cumulative_cashflow_chart", "figure"),
    Output("rent_breakdown_chart", "figure"),
    Output("emi_chart", "figure"),
    Output("prepayment_chart", "figure"),
    Output("rental_summary", "children"),
    Output("selling_output", "children"),
    Input("price", "value"),
    Input("buy_costs", "value"),
    Input("loan", "value"),
    Input("rate", "value"),
    Input("tenure", "value"),
    Input("prepay_rules_store", "data"),
    Input("rates_store", "data"),
    Input("rent", "value"),
    Input("tax", "value"),
    Input("maint", "value"),
    Input("rent_year", "value"),
    Input("tax_mode", "value"),
    Input("sell_year", "value"),
    Input("sell_price", "value"),
    Input("selling_costs", "value"),
    Input("inflation", "value"),
    Input("rent_growth", "value"),
    Input("currency-store", "data"),
)
def update_all(
    price,
    buy_costs,
    loan,
    rate,
    tenure,
    prepayment_rules,
    rates,
    rent,
    tax,
    maint,
    rent_year,
    tax_mode,
    sell_year,
    sell_price,
    selling_costs,
    inflation,
    rent_growth,
    currency,
):
    try:
        calc, result, sell, rental_df = run_calc(
            price,
            buy_costs,
            loan,
            rate,
            tenure,
            prepayment_rules,
            rates,
            rent,
            tax,
            maint,
            rent_year,
            tax_mode,
            sell_year,
            sell_price,
            selling_costs,
            inflation,
            rent_growth,
        )
        df = result.get("schedule", pd.DataFrame())
        if df.empty:
            df = pd.DataFrame(
                {
                    "Month": [0],
                    "Balance": [loan or 0],
                    "Interest Paid": [0],
                    "Principal Paid": [0],
                    "EMI": [0],
                }
            )

        months = df["Month"]
        loan_val = loan or 1
        cur = currency or "£"

        # 1. OUTSTANDING BALANCE
        milestones = []
        for pct, lbl in [
            (0.75, "75% remaining"),
            (0.5, "50% remaining"),
            (0.25, "25% remaining"),
        ]:
            target = loan_val * pct
            sub = df[df["Balance"] <= target]
            if not sub.empty:
                milestones.append((int(sub.iloc[0]["Month"]), target, lbl))

        fig_balance = go.Figure()
        fig_balance.add_trace(
            go.Scatter(
                x=months,
                y=df["Balance"],
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(201,168,76,0.07)",
                line=dict(color=C["gold"], width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig_balance.add_trace(
            go.Scatter(
                x=months,
                y=df["Balance"],
                name="Outstanding Balance",
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(201,168,76,0.12)",
                line=dict(color=C["gold"], width=2.5),
                hovertemplate=f"Month %{{x}}<br><b>Balance: {cur}%{{y:,.0f}}</b><extra></extra>",
            )
        )
        for m, val, lbl in milestones:
            fig_balance.add_vline(x=m, line=dict(color=C["muted"], width=1, dash="dot"))
            fig_balance.add_annotation(
                x=m,
                y=val,
                text=lbl,
                showarrow=True,
                arrowhead=0,
                arrowcolor=C["muted"],
                font=dict(family="DM Mono, monospace", size=9, color=C["muted"]),
                bgcolor="rgba(26,30,40,0.85)",
                bordercolor=C["border"],
                borderwidth=1,
                ax=30,
                ay=-24,
            )
        fig_balance.update_layout(
            **{
                **chart_layout(
                    "Outstanding Balance",
                    y_prefix=cur,
                    subtitle="Remaining loan principal each month",
                ),
                "hovermode": "x unified",
            }
        )

        # 2. INTEREST vs PRINCIPAL
        fig_ip = go.Figure()
        fig_ip.add_trace(
            go.Scatter(
                x=months,
                y=df["Interest Paid"],
                name="Interest",
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(248,113,113,0.2)",
                line=dict(color=C["red"], width=1.5),
                hovertemplate=f"Month %{{x}}<br>Interest: {cur}%{{y:,.0f}}<extra></extra>",
                stackgroup="emi",
            )
        )
        fig_ip.add_trace(
            go.Scatter(
                x=months,
                y=df["Principal Paid"],
                name="Principal",
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(74,222,128,0.15)",
                line=dict(color=C["green"], width=1.5),
                hovertemplate=f"Month %{{x}}<br>Principal: {cur}%{{y:,.0f}}<extra></extra>",
                stackgroup="emi",
            )
        )
        crossover = df[df["Principal Paid"] >= df["Interest Paid"]]
        if not crossover.empty:
            cm = int(crossover.iloc[0]["Month"])
            fig_ip.add_vline(x=cm, line=dict(color=C["gold"], width=1, dash="dot"))
            fig_ip.add_annotation(
                x=cm,
                y=0,
                yref="paper",
                text="Principal > Interest",
                showarrow=False,
                font=dict(family="DM Mono, monospace", size=9, color=C["gold"]),
                bgcolor="rgba(26,30,40,0.85)",
                bordercolor=C["gold"],
                borderwidth=1,
                xanchor="left",
                yanchor="bottom",
                xshift=6,
                yshift=4,
            )
        fig_ip.update_layout(
            **{
                **chart_layout(
                    "Interest vs Principal",
                    y_prefix=cur,
                    subtitle="Composition of each monthly payment",
                ),
                "hovermode": "x unified",
            }
        )

        # 3. CUMULATIVE INTEREST
        cum_interest = df["Interest Paid"].cumsum()
        fig_cum = go.Figure()
        fig_cum.add_trace(
            go.Scatter(
                x=months,
                y=cum_interest,
                name="Cumulative Interest",
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(167,139,250,0.1)",
                line=dict(color=C["purple"], width=2.5),
                hovertemplate=f"Month %{{x}}<br>Total Interest: {cur}%{{y:,.0f}}<extra></extra>",
            )
        )
        fig_cum.add_annotation(
            x=months.iloc[-1],
            y=cum_interest.iloc[-1],
            text=f"Total: {cur}{cum_interest.iloc[-1]:,.0f}",
            showarrow=True,
            arrowhead=0,
            arrowcolor=C["purple"],
            font=dict(family="DM Mono, monospace", size=10, color=C["purple"]),
            bgcolor="rgba(26,30,40,0.9)",
            bordercolor=C["purple"],
            borderwidth=1,
            ax=-50,
            ay=-20,
        )
        fig_cum.update_layout(
            **{
                **chart_layout(
                    "Cumulative Interest Paid",
                    y_prefix=cur,
                    subtitle="Total interest cost building over time",
                ),
                "hovermode": "x unified",
            }
        )

        # 4. RENTAL NET CASHFLOW
        fig_rental = go.Figure()
        layout_rental = {
            **chart_layout(
                "Monthly Net Cashflow", y_prefix=cur, subtitle="After EMI, costs & tax"
            ),
            "hovermode": "x unified",
        }
        if rental_df is not None and not rental_df.empty:
            years = rental_df["Year"]
            cf = rental_df["Net Cashflow"]
            fig_rental.add_trace(
                go.Bar(
                    x=years,
                    y=cf.clip(lower=0),
                    name="Positive",
                    marker=dict(color=C["green"], opacity=0.7, line=dict(width=0)),
                    hovertemplate=f"Year %{{x}}<br>+{cur}%{{y:,.0f}}/mo<extra></extra>",
                )
            )
            fig_rental.add_trace(
                go.Bar(
                    x=years,
                    y=cf.clip(upper=0),
                    name="Negative",
                    marker=dict(color=C["red"], opacity=0.7, line=dict(width=0)),
                    hovertemplate=f"Year %{{x}}<br>{cur}%{{y:,.0f}}/mo<extra></extra>",
                )
            )
            fig_rental.add_trace(
                go.Scatter(
                    x=years,
                    y=cf,
                    name="Net Cashflow",
                    mode="lines+markers",
                    line=dict(color=C["blue"], width=2.5),
                    marker=dict(size=5, color=C["blue"]),
                    hovertemplate=f"Year %{{x}}<br><b>{cur}%{{y:,.0f}}/mo</b><extra></extra>",
                )
            )
            fig_rental.add_hline(y=0, line=dict(color=C["muted"], width=1, dash="dot"))
            layout_rental["barmode"] = "relative"
        fig_rental.update_layout(**layout_rental)

        # 5. CUMULATIVE CASHFLOW
        fig_cumcf = go.Figure()
        layout_cumcf = {
            **chart_layout(
                "Cumulative Net Cashflow",
                y_prefix=cur,
                subtitle="Running total — crossing zero = breakeven",
            ),
            "hovermode": "x unified",
        }
        if rental_df is not None and not rental_df.empty:
            cum_cf = rental_df["Net Cashflow"].cumsum() * 12
            years = rental_df["Year"]
            fig_cumcf.add_trace(
                go.Scatter(
                    x=years,
                    y=cum_cf.clip(lower=0),
                    fill="tozeroy",
                    fillcolor="rgba(74,222,128,0.12)",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig_cumcf.add_trace(
                go.Scatter(
                    x=years,
                    y=cum_cf.clip(upper=0),
                    fill="tozeroy",
                    fillcolor="rgba(248,113,113,0.12)",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig_cumcf.add_trace(
                go.Scatter(
                    x=years,
                    y=cum_cf,
                    name="Cumulative Cashflow",
                    mode="lines",
                    line=dict(color=C["teal"], width=2.5),
                    hovertemplate=f"Year %{{x}}<br>Cumulative: {cur}%{{y:,.0f}}<extra></extra>",
                )
            )
            fig_cumcf.add_hline(y=0, line=dict(color=C["muted"], width=1, dash="dot"))
            breakeven = rental_df[cum_cf >= 0]
            if not breakeven.empty:
                by = int(breakeven.iloc[0]["Year"])
                fig_cumcf.add_annotation(
                    x=by,
                    y=0,
                    text=f"Breakeven Yr {by}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=C["teal"],
                    font=dict(family="DM Mono, monospace", size=9, color=C["teal"]),
                    bgcolor="rgba(26,30,40,0.85)",
                    bordercolor=C["teal"],
                    borderwidth=1,
                    ax=30,
                    ay=-28,
                )
        fig_cumcf.update_layout(**layout_cumcf)

        # 6. RENT BREAKDOWN
        fig_breakdown = go.Figure()
        layout_bd = {
            **chart_layout(
                "Annual Rent Breakdown",
                y_prefix=cur,
                subtitle="Where the gross rent goes each year",
            ),
            "hovermode": "x unified",
        }
        if rental_df is not None and not rental_df.empty and rent and rent > 0:
            years = rental_df["Year"].tolist()
            gross = [
                rent * ((1 + (rent_growth or 0) / 100) ** (y - 1)) * 12 for y in years
            ]
            maint_vals = [g * (maint or 0) / 100 for g in gross]
            emi_vals = [
                (
                    float(df[df["Year"] == y]["EMI"].mean() * 12)
                    if not df[df["Year"] == y].empty
                    else 0
                )
                for y in years
            ]
            net_vals = [cf * 12 for cf in rental_df["Net Cashflow"].tolist()]
            tax_vals = [
                max(g - m - e - n, 0)
                for g, m, e, n in zip(gross, maint_vals, emi_vals, net_vals)
            ]
            fig_breakdown.add_trace(
                go.Bar(
                    name="Maintenance",
                    x=years,
                    y=maint_vals,
                    marker=dict(color=C["orange"], opacity=0.85),
                )
            )
            fig_breakdown.add_trace(
                go.Bar(
                    name="Tax",
                    x=years,
                    y=tax_vals,
                    marker=dict(color=C["red"], opacity=0.75),
                )
            )
            fig_breakdown.add_trace(
                go.Bar(
                    name="EMI",
                    x=years,
                    y=emi_vals,
                    marker=dict(color=C["purple"], opacity=0.75),
                )
            )
            fig_breakdown.add_trace(
                go.Bar(
                    name="Net Profit",
                    x=years,
                    y=[max(n, 0) for n in net_vals],
                    marker=dict(color=C["green"], opacity=0.85),
                )
            )
            layout_bd["barmode"] = "stack"
        fig_breakdown.update_layout(**layout_bd)

        # 7. EMI & RATES
        fig_emi = go.Figure()
        emi_df, segments = calc.get_emi_chart_data()
        for idx_s, (s, e, seg_rate) in enumerate(segments):
            fig_emi.add_vrect(
                x0=s,
                x1=e,
                fillcolor=BAND_COLORS[idx_s % len(BAND_COLORS)],
                line_width=0,
                layer="below",
            )
            fig_emi.add_annotation(
                x=(s + e) / 2,
                y=1,
                yref="paper",
                text=f"<b>{seg_rate:.2f}%</b>",
                showarrow=False,
                font=dict(family="DM Mono, monospace", size=10, color=C["gold"]),
                yanchor="bottom",
                xanchor="center",
                bgcolor="rgba(26,30,40,0.7)",
                borderpad=3,
            )
        for s, _, _ in segments[1:]:
            fig_emi.add_vline(x=s, line=dict(color=C["gold"], width=1.5, dash="dash"))
        fig_emi.add_trace(
            go.Scatter(
                x=emi_df["Month"],
                y=emi_df["Interest Paid"],
                name="Interest",
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(248,113,113,0.18)",
                line=dict(color=C["red"], width=1),
                hovertemplate=f"Month %{{x}}<br>Interest: {cur}%{{y:,.0f}}<extra></extra>",
            )
        )
        fig_emi.add_trace(
            go.Scatter(
                x=emi_df["Month"],
                y=emi_df["Principal Paid"],
                name="Principal",
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(74,222,128,0.14)",
                line=dict(color=C["green"], width=1),
                hovertemplate=f"Month %{{x}}<br>Principal: {cur}%{{y:,.0f}}<extra></extra>",
            )
        )
        fig_emi.add_trace(
            go.Scatter(
                x=emi_df["Month"],
                y=emi_df["EMI"],
                name="EMI",
                mode="lines",
                line=dict(color=C["purple"], width=3),
                hovertemplate=f"Month %{{x}}<br><b>EMI: {cur}%{{y:,.0f}}</b><extra></extra>",
            )
        )
        fig_emi.update_layout(
            **{
                **chart_layout(
                    "EMI & Rate Periods",
                    y_prefix=cur,
                    subtitle="Monthly payment split with rate change bands",
                ),
                "hovermode": "x unified",
            }
        )

        # 8. PREPAYMENTS
        fig_prepay = go.Figure()
        prepay_by_year = (
            df[df["Prepayment"] > 0].groupby("Year")["Prepayment"].sum().reset_index()
        )
        layout_prepay = {
            **chart_layout(
                "Prepayments by Year",
                y_prefix=cur,
                subtitle="Extra principal paid down at each year-end, on top of the regular EMI",
            ),
            "hovermode": "x unified",
        }
        if not prepay_by_year.empty:
            fig_prepay.add_trace(
                go.Bar(
                    x=prepay_by_year["Year"],
                    y=prepay_by_year["Prepayment"],
                    name="Prepayment",
                    marker=dict(color=C["teal"], opacity=0.85),
                    text=[f"{cur}{v:,.0f}" for v in prepay_by_year["Prepayment"]],
                    textposition="outside",
                    textfont=dict(
                        family="DM Mono, monospace", size=10, color=C["platinum"]
                    ),
                    hovertemplate=f"Year %{{x}}<br><b>{cur}%{{y:,.0f}}</b><extra></extra>",
                )
            )
            cum_prepay = prepay_by_year["Prepayment"].cumsum()
            fig_prepay.add_trace(
                go.Scatter(
                    x=prepay_by_year["Year"],
                    y=cum_prepay,
                    name="Cumulative Prepaid",
                    mode="lines+markers",
                    yaxis="y2",
                    line=dict(color=C["gold"], width=2.5),
                    marker=dict(size=5, color=C["gold"]),
                    hovertemplate=f"Year %{{x}}<br>Cumulative: {cur}%{{y:,.0f}}<extra></extra>",
                )
            )
            layout_prepay["yaxis2"] = dict(
                overlaying="y",
                side="right",
                showgrid=False,
                tickprefix=cur,
                tickformat=",.0f",
                tickfont=dict(family="DM Mono, monospace", size=10, color=C["gold"]),
            )
        fig_prepay.update_layout(**layout_prepay)
        if prepay_by_year.empty:
            fig_prepay.add_annotation(
                text="No prepayments configured for this scenario",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(family="DM Mono, monospace", size=12, color=C["muted"]),
            )

        # Selling cards
        def sell_card(label, value, positive=False, large=False):
            col = (
                C["green"]
                if positive and value >= 0
                else (C["red"] if positive else C["platinum"])
            )
            return html.Div(
                [
                    html.Div(
                        label,
                        style={
                            "fontFamily": "DM Mono, monospace",
                            "fontSize": "0.58rem",
                            "color": C["muted"],
                            "letterSpacing": "2px",
                            "textTransform": "uppercase",
                        },
                    ),
                    html.Div(
                        f"{cur}{value:,.0f}",
                        style={
                            "fontFamily": "DM Serif Display, serif",
                            "fontSize": "1.45rem" if large else "1.2rem",
                            "color": col,
                            "marginTop": "4px",
                        },
                    ),
                ],
                style={
                    "background": C["panel"],
                    "border": f"1px solid {C['border']}",
                    "borderRadius": "10px",
                    "padding": "18px 20px",
                    "flex": "1",
                },
            )

        sell_ui = html.Div(
            [
                html.Div(
                    [
                        sell_card("Buy Price", price or 0, large=True),
                        sell_card("Sale Price", sell.get("sale_price", 0), large=True),
                        sell_card(
                            "Inflation-Adjusted Value",
                            sell.get("inflation_adj_sale_price", 0),
                            large=True,
                        ),
                    ],
                    style={"display": "flex", "gap": "12px", "marginBottom": "12px"},
                ),
                html.Div(
                    [
                        sell_card(
                            "Remaining Loan",
                            sell.get("remaining_balance", 0),
                            large=True,
                        ),
                        sell_card(
                            "Interest Paid", sell.get("interest_paid", 0), large=True
                        ),
                        sell_card("Sale Costs", selling_costs or 0, large=True),
                        sell_card("Sale Proceeds", sell.get("proceeds", 0), large=True),
                    ],
                    style={"display": "flex", "gap": "12px", "marginBottom": "12px"},
                ),
                html.Div(
                    [
                        sell_card(
                            "Net Appreciation Profit",
                            sell.get("gain", 0),
                            positive=True,
                            large=True,
                        ),
                        sell_card(
                            "Real Appreciation Profit (Infl. Adj.)",
                            sell.get("real_gain", 0),
                            positive=True,
                            large=True,
                        ),
                    ],
                    style={"display": "flex", "gap": "12px", "marginBottom": "12px"},
                ),
                html.Div(
                    [
                        sell_card(
                            "Net Financial Profit",
                            sell.get("fin_gain", 0),
                            positive=True,
                            large=True,
                        ),
                        sell_card(
                            "Real Financial Profit (Infl. Adj.)",
                            sell.get("fin_real_gain", 0),
                            positive=True,
                            large=True,
                        ),
                    ],
                    style={"display": "flex", "gap": "12px"},
                ),
            ]
        )

        return (
            f"{cur}{result.get('emi', 0):,.0f}",
            f"{cur}{result.get('total_interest', 0):,.0f}",
            f"{result.get('total_interest', 0) / loan_val:.2%}",
            f"{result.get('payoff_years', 0):.1f} yrs",
            fig_balance,
            fig_ip,
            fig_cum,
            fig_rental,
            fig_cumcf,
            fig_breakdown,
            fig_emi,
            fig_prepay,
            "",
            sell_ui,
        )
    except Exception:
        import traceback

        traceback.print_exc()
        empty = go.Figure()
        empty.update_layout(**chart_layout(""))
        return (
            "-",
            "-",
            "-",
            "-",
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            "",
            "",
        )


# ── Scenario comparison runner ────────────────────────────────────────────
@app.callback(
    Output("sc-results", "children"),
    Input("sc-run-btn", "n_clicks"),
    State({"type": "sc-name", "index": ALL}, "value"),
    State({"type": "sc-price", "index": ALL}, "value"),
    State({"type": "sc-buy-costs", "index": ALL}, "value"),
    State({"type": "sc-loan", "index": ALL}, "value"),
    State({"type": "sc-rate", "index": ALL}, "value"),
    State({"type": "sc-tenure", "index": ALL}, "value"),
    State({"type": "sc-rent", "index": ALL}, "value"),
    State({"type": "sc-tax", "index": ALL}, "value"),
    State({"type": "sc-maint", "index": ALL}, "value"),
    State({"type": "sc-rent-growth", "index": ALL}, "value"),
    State({"type": "sc-sell-year", "index": ALL}, "value"),
    State({"type": "sc-sell-price", "index": ALL}, "value"),
    State({"type": "sc-inflation", "index": ALL}, "value"),
    State({"type": "sc-sell-cost", "index": ALL}, "value"),
    State("scenarios-data-store", "data"),
    State("currency-store", "data"),
    State("sc-show-rental-exit", "data"),
    prevent_initial_call=True,
)
def run_scenario_comparison(
    _,
    names,
    prices,
    buy_costs,
    loans,
    rates,
    tenures,
    rents,
    taxes,
    maints,
    rent_growths,
    sell_years,
    sell_prices,
    inflations,
    sell_costs,
    stored_data,
    currency,
    show_rental_exit,
):
    if _ is None:
        return dash.no_update
    cur = currency or "£"
    n = len(names)
    if n == 0:
        return html.Div(
            "Add at least one scenario to compare.",
            style={"color": C["muted"], "fontFamily": "DM Mono, monospace"},
        )

    scenarios = []
    for i in range(n):
        try:
            sc_store = (
                stored_data[i] if stored_data and i < len(stored_data) else {}
            ) or {}
            prepay_rules = sc_store.get("prepayment_rules") or []
            var_rates = sc_store.get("variable_rates") or []
            calc, result, sell, rental_df = run_calc(
                price=prices[i] or 600000,
                buy_costs=buy_costs or 25000,
                loan=loans[i] or 540000,
                rate=rates[i] or 5,
                tenure=tenures[i] or 25,
                prepayment_rules=prepay_rules,
                rates=var_rates,
                rent=rents[i] or 0,
                tax=taxes[i] or 0,
                maint=maints[i] or 0,
                rent_year=1,
                tax_mode="uk",
                sell_year=sell_years[i] or 10,
                sell_price=sell_prices[i] or 2,
                selling_costs=sell_costs[i] or 5000,
                inflation=inflations[i] or 2,
                rent_growth=rent_growths[i] or 2,
            )
            yr1_cf = 0
            if rental_df is not None and not rental_df.empty:
                yr1_cf = rental_df.iloc[0]["Net Cashflow"]
            scenarios.append(
                {
                    "name": names[i] or f"Scenario {SCENARIO_LABELS[i]}",
                    "color": SCENARIO_COLORS[i],
                    "emi": result["emi"],
                    "total_interest": result["total_interest"],
                    "payoff_years": result["payoff_years"],
                    "eff_rate": result["total_interest"] / (loans[i] or 1),
                    "yr1_cashflow": yr1_cf,
                    "proceeds": sell.get("proceeds", 0),
                    "fin_gain": sell.get("fin_gain", 0),
                    "schedule": result["schedule"],
                }
            )
        except Exception as e:
            print(f"Scenario {i} error:", e)

    if not scenarios:
        return html.Div(
            "Could not compute any scenarios.",
            style={"color": C["red"], "fontFamily": "DM Mono, monospace"},
        )

    kpi_rows = [
        ("Monthly EMI", [f"{cur}{s['emi']:,.0f}" for s in scenarios], True),
        (
            "Total Interest",
            [f"{cur}{s['total_interest']:,.0f}" for s in scenarios],
            True,
        ),
        ("Effective Rate", [f"{s['eff_rate']:.2%}" for s in scenarios], True),
        ("Payoff Years", [f"{s['payoff_years']:.1f} yrs" for s in scenarios], True),
    ]
    if show_rental_exit:
        kpi_rows += [
            (
                "Yr 1 Cashflow/mo",
                [f"{cur}{s['yr1_cashflow']:,.0f}" for s in scenarios],
                False,
            ),
            (
                "Sale Proceeds",
                [f"{cur}{s['proceeds']:,.0f}" for s in scenarios],
                False,
            ),
            (
                "Net Financial Profit",
                [f"{cur}{s['fin_gain']:,.0f}" for s in scenarios],
                False,
            ),
        ]

    header_row = html.Tr(
        [
            html.Th(
                "Metric",
                style={
                    "fontFamily": "DM Mono, monospace",
                    "fontSize": "0.65rem",
                    "color": C["muted"],
                    "padding": "12px 16px",
                    "textTransform": "uppercase",
                    "letterSpacing": "1px",
                    "borderBottom": f"2px solid {C['border2']}",
                },
            ),
            *[
                html.Th(
                    s["name"],
                    style={
                        "fontFamily": "DM Mono, monospace",
                        "fontSize": "0.65rem",
                        "color": s["color"],
                        "padding": "12px 16px",
                        "textTransform": "uppercase",
                        "letterSpacing": "1px",
                        "borderBottom": f"2px solid {s['color']}55",
                        "textAlign": "right",
                    },
                )
                for s in scenarios
            ],
        ]
    )

    table_rows = []
    for label, values, lower_is_better in kpi_rows:
        try:
            nums = [
                float(
                    v.replace(cur, "")
                    .replace(",", "")
                    .replace(" yrs", "")
                    .replace("%", "")
                )
                for v in values
            ]
            best_idx = nums.index(min(nums) if lower_is_better else max(nums))
        except Exception:
            best_idx = -1
        cells = [
            html.Td(
                label,
                style={
                    "fontFamily": "Outfit, sans-serif",
                    "fontSize": "0.82rem",
                    "color": C["muted"],
                    "padding": "10px 16px",
                    "borderBottom": f"1px solid {C['border']}",
                },
            )
        ]
        for j, (v, s) in enumerate(zip(values, scenarios)):
            is_best = j == best_idx
            cells.append(
                html.Td(
                    html.Div(
                        [
                            html.Span(
                                "★ " if is_best else "",
                                style={"color": C["gold"], "fontSize": "0.6rem"},
                            ),
                            html.Span(v),
                        ]
                    ),
                    style={
                        "fontFamily": "DM Mono, monospace",
                        "fontSize": "0.8rem",
                        "color": C["green"] if is_best else C["platinum"],
                        "padding": "10px 16px",
                        "textAlign": "right",
                        "borderBottom": f"1px solid {C['border']}",
                        "background": f"{s['color']}08" if is_best else "transparent",
                    },
                )
            )
        table_rows.append(html.Tr(cells))

    kpi_table = html.Div(
        [
            html.Div(
                "Key Metrics",
                style={
                    "fontFamily": "DM Serif Display, serif",
                    "fontSize": "1.15rem",
                    "color": C["platinum"],
                    "marginBottom": "12px",
                },
            ),
            html.Div(
                html.Table(
                    [html.Thead(header_row), html.Tbody(table_rows)],
                    style={"width": "100%", "borderCollapse": "collapse"},
                ),
                style={
                    "background": C["panel"],
                    "border": f"1px solid {C['border2']}",
                    "borderRadius": "12px",
                    "overflow": "hidden",
                },
            ),
        ],
        style={"marginBottom": "28px"},
    )

    def sc_bar(title, values, subtitle="", y_prefix=None, suffix_fmt=None):
        yp = y_prefix if y_prefix is not None else cur
        n = len(scenarios)
        # One trace per scenario so each gets its own colour, but we place
        # them all on the same dummy x-category ("") and use barmode="group"
        # so Plotly handles side-by-side spacing with no overlap.
        fig = go.Figure()
        for s, v in zip(scenarios, values):
            display = suffix_fmt.format(v) if suffix_fmt else f"{cur}{v:,.0f}"
            fig.add_trace(
                go.Bar(
                    name=s["name"],
                    x=[""],
                    y=[abs(v)],
                    marker=dict(
                        color=s["color"],
                        opacity=0.85,
                        line=dict(color=s["color"], width=1),
                    ),
                    text=[display],
                    textposition="outside",
                    textfont=dict(
                        family="DM Mono, monospace", size=13, color=C["platinum"]
                    ),
                    hovertemplate=f"<b>{s['name']}</b><br>{display}<extra></extra>",
                )
            )
        layout = chart_layout(title, y_prefix=yp, subtitle=subtitle)
        layout["showlegend"] = True
        layout["legend"] = dict(
            orientation="h",
            y=-0.18,
            x=0.5,
            xanchor="center",
            font=dict(family="DM Mono, monospace", size=10, color=C["muted"]),
            bgcolor="rgba(0,0,0,0)",
        )
        layout["barmode"] = "group"
        layout["bargap"] = 0.3
        layout["bargroupgap"] = 0.08
        layout["margin"] = dict(l=44, r=16, t=60, b=48)
        layout["xaxis"] = dict(
            showticklabels=False, showgrid=False, linecolor=C["border"]
        )
        fig.update_layout(**layout)
        fig.update_traces(cliponaxis=False)
        return fig

    bar_emi = sc_bar("Monthly EMI", [s["emi"] for s in scenarios], "Lower is better")
    bar_interest = sc_bar(
        "Total Interest", [s["total_interest"] for s in scenarios], "Lower is better"
    )
    bar_years = sc_bar(
        "Payoff Years",
        [s["payoff_years"] for s in scenarios],
        "Lower is better",
        y_prefix="",
        suffix_fmt="{:.1f} yrs",
    )
    bar_years.update_layout(
        yaxis=dict(
            gridcolor="rgba(37,42,56,0.6)",
            linecolor=C["border"],
            tickfont=dict(family="DM Mono, monospace", size=10, color=C["muted"]),
            zeroline=False,
            ticksuffix=" yrs",
            tickformat=",.1f",
        )
    )

    def gchart(fig, height="220px"):
        return dcc.Graph(
            figure=fig,
            config={"displayModeBar": False},
            style={"height": height},
            responsive=True,
        )

    def chart_section(title, fig, height="380px"):
        return html.Div(
            [
                html.Div(
                    title,
                    style={
                        "fontFamily": "DM Serif Display, serif",
                        "fontSize": "1.15rem",
                        "color": C["platinum"],
                        "marginBottom": "12px",
                    },
                ),
                html.Div(
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": height},
                        responsive=True,
                    ),
                    style={
                        "background": C["panel"],
                        "border": f"1px solid {C['border2']}",
                        "borderRadius": "12px",
                        "padding": "12px",
                    },
                ),
            ],
            style={"marginBottom": "24px"},
        )

    bar_grid = html.Div(
        [
            html.Div(
                [
                    html.Div(gchart(bar_emi), className="chart-cell"),
                    html.Div(gchart(bar_interest), className="chart-cell"),
                    html.Div(gchart(bar_years), className="chart-cell"),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                    "gap": "12px",
                    "width": "100%",
                },
            ),
        ]
    )

    fig_bal = go.Figure()
    for s in scenarios:
        sch = s["schedule"]
        r, g, b = (
            int(s["color"][1:3], 16),
            int(s["color"][3:5], 16),
            int(s["color"][5:7], 16),
        )
        fig_bal.add_trace(
            go.Scatter(
                x=sch["Month"],
                y=sch["Balance"],
                mode="lines",
                name=s["name"],
                line=dict(color=s["color"], width=2.5),
                fill="tozeroy",
                fillcolor=f"rgba({r},{g},{b},0.04)",
                hovertemplate=f"<b>{s['name']}</b><br>Month %{{x}}<br>Balance: {cur}%{{y:,.0f}}<extra></extra>",
            )
        )
    fig_bal.update_layout(
        **{
            **chart_layout(
                "Balance Trajectories — All Scenarios",
                y_prefix=cur,
                subtitle="Overlaid payoff curves",
            ),
            "hovermode": "x unified",
        }
    )

    fig_emi = go.Figure()
    for s in scenarios:
        sch = s["schedule"]
        emi_by_year = sch.groupby("Year")["EMI"].mean().reset_index()
        fig_emi.add_trace(
            go.Scatter(
                x=emi_by_year["Year"],
                y=emi_by_year["EMI"],
                mode="lines+markers",
                name=s["name"],
                line=dict(color=s["color"], width=2.5, shape="hv"),
                marker=dict(size=5, color=s["color"]),
                hovertemplate=f"<b>{s['name']}</b><br>Year %{{x}}<br>EMI: {cur}%{{y:,.0f}}<extra></extra>",
            )
        )
    fig_emi.update_layout(
        **{
            **chart_layout(
                "EMI Trajectories — All Scenarios",
                y_prefix=cur,
                subtitle="Monthly instalment by year, reflecting rate changes",
            ),
            "hovermode": "x unified",
        }
    )

    core_sections = [
        kpi_table,
        bar_grid,
        chart_section("Balance Trajectories", fig_bal),
        chart_section("EMI Trajectories", fig_emi),
    ]

    if show_rental_exit:
        bar_cf = sc_bar(
            "Yr 1 Net Cashflow/mo",
            [s["yr1_cashflow"] for s in scenarios],
            "Higher is better",
        )
        bar_proceeds = sc_bar(
            "Sale Proceeds", [s["proceeds"] for s in scenarios], "Higher is better"
        )
        bar_fin = sc_bar(
            "Net Financial Profit",
            [s["fin_gain"] for s in scenarios],
            "Higher is better",
        )
        rental_exit_section = html.Div(
            [
                html.Div(
                    [
                        html.I(
                            className="bi bi-house-door",
                            style={"marginRight": "8px", "color": C["gold"]},
                        ),
                        "Rental & Exit Strategy",
                    ],
                    style={
                        "fontFamily": "DM Serif Display, serif",
                        "fontSize": "1.15rem",
                        "color": C["platinum"],
                        "marginBottom": "16px",
                        "paddingBottom": "10px",
                        "borderBottom": f"1px solid {C['border2']}",
                    },
                ),
                html.Div(
                    [
                        html.Div(gchart(bar_cf), className="chart-cell"),
                        html.Div(gchart(bar_proceeds), className="chart-cell"),
                        html.Div(gchart(bar_fin), className="chart-cell"),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                        "gap": "12px",
                        "width": "100%",
                    },
                ),
            ],
            style={
                "background": C["panel"],
                "border": f"1px solid {C['border2']}",
                "borderRadius": "12px",
                "padding": "18px",
                "marginTop": "24px",
                "marginBottom": "24px",
            },
        )
        core_sections.append(rental_exit_section)

    return html.Div(core_sections)


if __name__ == "__main__":
    app.run(debug=True)
