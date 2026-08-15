"""Shared visual design tokens + Plotly styling.

Dark theme only — a deliberate single-look choice (see .streamlit/config.toml),
not an auto light/dark flip. Values are the dark column of the dataviz skill's
reference palette (references/palette.md): one accent hue for all charts here,
since every chart in this dashboard is a single-series magnitude chart (filing
counts, mention counts) rather than a multi-series comparison — sequential/
single-hue is the correct treatment per the skill's chart-type table, not a
per-bar rainbow.
"""
SURFACE = "#1a1a19"
INK_PRIMARY = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"
AXIS = "#383835"
ACCENT = "#3987e5"  # categorical slot 1 (blue), dark column

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def style_fig(fig, title: str = None, y_title: str = None):
    """Apply consistent dark styling to a Plotly figure: chart surface, hairline
    recessive gridlines, themed hover, no default legend (single-series charts
    don't need one — see marks-and-anatomy.md)."""
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY, size=13),
        title=dict(text=title, font=dict(color=INK_PRIMARY, size=16)) if title else None,
        margin=dict(l=10, r=10, t=48 if title else 16, b=10),
        showlegend=False,
        hoverlabel=dict(bgcolor=SURFACE, font_color=INK_PRIMARY, bordercolor=AXIS),
        bargap=0.35,
    )
    fig.update_xaxes(gridcolor=GRIDLINE, linecolor=AXIS, zeroline=False, showgrid=False)
    fig.update_yaxes(
        gridcolor=GRIDLINE, linecolor=AXIS, zeroline=False, title=y_title,
        title_font=dict(color=INK_MUTED, size=12),
    )
    return fig
