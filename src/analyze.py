"""Statistical analysis of the clean DVF sales: tables, tests and figures.

Outputs
-------
* ``reports/tables/*.csv``: one table per business question;
* ``reports/tables/summary.json``: headline numbers quoted in ``findings.md``;
* ``reports/figures/*.png``: static Plotly charts used in the README.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import mannwhitneyu

from src.clean import PROCESSED_FILE
from src.income import read_income
from src.settings import load_config, project_path, setup_logging

logger = logging.getLogger("analyze")

ALL_TYPES = "Ensemble"

# --------------------------------------------------------------------------- #
# Chart style (validated categorical order, recessive chrome, one axis per chart)
# --------------------------------------------------------------------------- #
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQ_LIGHT, SEQ_MID, SEQ_DARK = "#9ec5f4", "#2a78d6", "#104281"
UP, DOWN = "#e34948", "#2a78d6"  # diverging poles: rise / fall
FONT = "Segoe UI, system-ui, -apple-system, Helvetica, Arial, sans-serif"


def city_colors(metropoles: Sequence[str]) -> dict[str, str]:
    """Fixed colour per metropolis (colour follows the entity, never its rank)."""
    return {city: CATEGORICAL[i] for i, city in enumerate(metropoles)}


def base_layout(fig: go.Figure, title: str, subtitle: str = "", height: int = 520) -> go.Figure:
    """Apply the shared look: white surface, hairline grid, left-aligned titles."""
    full_title = f"<b>{title}</b>"
    if subtitle:
        full_title += f"<br><span style='font-size:13px;color:{INK_2}'>{subtitle}</span>"
    fig.update_layout(
        title={"text": full_title, "x": 0.01, "xanchor": "left", "font": {"size": 19, "color": INK}},
        font={"family": FONT, "size": 13, "color": INK_2},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        height=height,
        width=1000,
        margin={"l": 70, "r": 40, "t": 125, "b": 95},
        legend={"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0, "title": None},
        separators=", ",
        hoverlabel={"font": {"family": FONT}},
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, ticks="outside", zeroline=False)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=False, linecolor=AXIS)
    return fig


def add_source(fig: go.Figure, note: str = "") -> None:
    """Footnote with the data source."""
    text = "Source : DVF géolocalisées (Etalab / DGFiP), ventes d'un seul logement, après nettoyage."
    if note:
        text += " " + note
    fig.add_annotation(
        text=text, xref="paper", yref="paper", x=0, y=0, yshift=-80, showarrow=False,
        xanchor="left", yanchor="top", font={"size": 11, "color": MUTED},
    )


def save_figure(fig: go.Figure, name: str) -> Path:
    """Write a PNG (needs Chrome/Chromium for kaleido); never fail the pipeline on it."""
    target = project_path("figures") / f"{name}.png"
    if "BROWSER_PATH" not in os.environ:
        for candidate in ("chromium", "chromium-browser", "google-chrome", "/opt/pw-browsers/chromium"):
            found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
            if found:
                os.environ["BROWSER_PATH"] = found
                break
    try:
        fig.write_image(target, scale=2)
        logger.info("Figure saved: %s", target.name)
    except Exception as exc:  # noqa: BLE001 - kaleido raises various errors without Chrome
        logger.warning("Could not export %s (%s). Install Chrome or run `plotly_get_chrome`.", name, exc)
    return target


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def with_all_types(df: pd.DataFrame) -> pd.DataFrame:
    """Duplicate the sales with ``type_local = 'Ensemble'`` to get all-type aggregates."""
    return pd.concat([df, df.assign(type_local=ALL_TYPES)], ignore_index=True)


def median_by(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Sales count and medians (price per m², price, surface) for each group."""
    return (
        df.groupby(keys, observed=True)
        .agg(
            nb_ventes=("prix_m2", "size"),
            prix_m2_median=("prix_m2", "median"),
            prix_median=("valeur_fonciere", "median"),
            surface_mediane=("surface_reelle_bati", "median"),
        )
        .reset_index()
    )


def price_by_area(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Q1 — median price per m² by department, commune and property type."""
    data = with_all_types(df)
    dept = median_by(data, ["code_departement", "type_local", "annee"])
    commune = median_by(data, ["code_commune", "nom_commune", "code_departement", "type_local", "annee"])
    return {"prix_departement": dept, "prix_commune": commune}


def city_yearly(df: pd.DataFrame) -> pd.DataFrame:
    """Q2 — yearly medians and volumes per main city, with year-over-year changes."""
    data = with_all_types(df[df["ville_principale"].notna()])
    out = median_by(data, ["ville_principale", "type_local", "annee"]).sort_values(
        ["ville_principale", "type_local", "annee"]
    )
    grouped = out.groupby(["ville_principale", "type_local"])
    out["evol_prix_m2_pct"] = grouped["prix_m2_median"].pct_change() * 100
    out["evol_volume_pct"] = grouped["nb_ventes"].pct_change() * 100
    return out.reset_index(drop=True)


def city_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Q2 — monthly volume, median price per m² and rolling 3-month median per city.

    The rolling median is computed on the raw sales of the last 3 months (same
    definition as the SQL view ``v_tendance_mensuelle_ville``).
    """
    data = df[df["ville_principale"].notna()].copy()
    data["debut_mois"] = data["date_mutation"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        data.groupby(["ville_principale", "debut_mois"])
        .agg(nb_ventes=("prix_m2", "size"), prix_m2_median=("prix_m2", "median"))
        .reset_index()
    )
    rolling = []
    for city, sub in data.groupby("ville_principale"):
        months = monthly.loc[monthly["ville_principale"] == city, "debut_mois"]
        for month in months:
            window = sub[(sub["debut_mois"] > month - pd.DateOffset(months=3)) & (sub["debut_mois"] <= month)]
            rolling.append((city, month, window["prix_m2"].median()))
    roll = pd.DataFrame(rolling, columns=["ville_principale", "debut_mois", "prix_m2_median_3m"])
    return monthly.merge(roll, on=["ville_principale", "debut_mois"])


def rate_rise_effect(yearly: pd.DataFrame, before: int, after: int, last: int) -> pd.DataFrame:
    """Q3 — change in volume vs change in price, before / after the rate rise."""
    data = yearly[yearly["type_local"] == ALL_TYPES].set_index(["ville_principale", "annee"])
    rows = []
    for city in data.index.get_level_values(0).unique():
        b, a, l = data.loc[(city, before)], data.loc[(city, after)], data.loc[(city, last)]
        rows.append(
            {
                "ville_principale": city,
                f"ventes_{before}": int(b["nb_ventes"]),
                f"ventes_{after}": int(a["nb_ventes"]),
                f"ventes_{last}": int(l["nb_ventes"]),
                f"prix_m2_{before}": b["prix_m2_median"],
                f"prix_m2_{after}": a["prix_m2_median"],
                f"prix_m2_{last}": l["prix_m2_median"],
                "evol_volume_hausse_taux_pct": (a["nb_ventes"] / b["nb_ventes"] - 1) * 100,
                "evol_prix_hausse_taux_pct": (a["prix_m2_median"] / b["prix_m2_median"] - 1) * 100,
                "evol_volume_total_pct": (l["nb_ventes"] / b["nb_ventes"] - 1) * 100,
                "evol_prix_total_pct": (l["prix_m2_median"] / b["prix_m2_median"] - 1) * 100,
            }
        )
    return pd.DataFrame(rows).sort_values("evol_volume_hausse_taux_pct").reset_index(drop=True)


def city_ranking(effect: pd.DataFrame, last: int) -> pd.DataFrame:
    """Q4 — rank cities by price change (rise / fall) and by price level."""
    out = effect[["ville_principale", "evol_prix_total_pct", "evol_volume_total_pct", f"prix_m2_{last}"]].copy()
    out["rang_plus_forte_hausse"] = out["evol_prix_total_pct"].rank(ascending=False, method="min").astype(int)
    out["rang_plus_forte_baisse"] = out["evol_prix_total_pct"].rank(ascending=True, method="min").astype(int)
    out["rang_moins_cher"] = out[f"prix_m2_{last}"].rank(ascending=True, method="min").astype(int)
    return out.sort_values("rang_plus_forte_hausse").reset_index(drop=True)


def affordability(yearly: pd.DataFrame, budgets: Sequence[int], last: int) -> pd.DataFrame:
    """Q5 — m² buyable for each budget at the city median price per m² (last year)."""
    latest = yearly[yearly["annee"] == last]
    rows = [
        {
            "ville_principale": r.ville_principale,
            "type_local": r.type_local,
            "prix_m2_median": r.prix_m2_median,
            "surface_mediane": r.surface_mediane,
            "budget": budget,
            "m2_achetables": budget / r.prix_m2_median,
        }
        for r in latest.itertuples()
        for budget in budgets
    ]
    return pd.DataFrame(rows)


def income_ratio(yearly: pd.DataFrame, cfg: dict, last: int) -> pd.DataFrame:
    """Q6 — years of median household income needed to buy the median dwelling."""
    income = read_income()
    if income.empty:
        return pd.DataFrame()
    city_codes: dict[str, str] = {}
    for code, city in cfg["main_cities"].items():
        city_codes.setdefault(city, "69123" if code.startswith("6938") else code)
    rev = income.set_index("code_geo")["revenu_menage_median"]
    latest = yearly[(yearly["annee"] == last) & (yearly["type_local"] == ALL_TYPES)].copy()
    latest["revenu_menage_median"] = latest["ville_principale"].map(city_codes).map(rev)
    latest["annees_de_revenu"] = latest["prix_median"] / latest["revenu_menage_median"]
    return latest[
        ["ville_principale", "prix_median", "revenu_menage_median", "annees_de_revenu"]
    ].sort_values("annees_de_revenu").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Statistical test
# --------------------------------------------------------------------------- #
def effect_label(r: float) -> str:
    """Conventional magnitude of a rank-biserial correlation."""
    size = abs(r)
    if size < 0.1:
        return "négligeable"
    if size < 0.3:
        return "faible"
    if size < 0.5:
        return "moyen"
    return "fort"


def mann_whitney(
    first: np.ndarray, last: np.ndarray, alpha: float, n_tests: int = 1
) -> dict[str, float | str | bool]:
    """Two-sided Mann-Whitney U test of ``last`` vs ``first`` with effect sizes.

    * ``prob_superiorite``: probability that a random sale of the last year has
      a higher price per m² than a random sale of the first year (ties = 1/2);
    * ``r_rang_bisériel = 2 * prob - 1`` in [-1, 1] (> 0: prices went up).
    Significance uses a Bonferroni-corrected threshold ``alpha / n_tests``.
    """
    result = mannwhitneyu(last, first, alternative="two-sided")
    prob = result.statistic / (len(first) * len(last))
    r = 2 * prob - 1
    significant = bool(result.pvalue < alpha / n_tests)
    return {
        "u_stat": float(result.statistic),
        "p_value": float(result.pvalue),
        "significatif": significant,
        "prob_superiorite": float(prob),
        "r_rang_biseriel": float(r),
        "taille_effet": effect_label(r),
    }


def interpret(city: str, row: dict, first_year: int, last_year: int) -> str:
    """Plain-language interpretation of one test result."""
    direction = "plus élevés" if row["r_rang_biseriel"] > 0 else "plus bas"
    chance = row["prob_superiorite"] * 100
    if not row["significatif"]:
        return (
            f"{city} : pas de différence statistiquement significative entre {first_year} et "
            f"{last_year} (p = {row['p_value']:.3f})."
        )
    return (
        f"{city} : prix au m² {direction} en {last_year} qu'en {first_year} (p < 0,001 ; effet "
        f"{row['taille_effet']}). Une vente {last_year} prise au hasard a {chance:.0f} % de chances "
        f"d'être plus chère au m² qu'une vente {first_year}."
        if row["p_value"] < 0.001
        else f"{city} : prix au m² {direction} en {last_year} qu'en {first_year} (p = "
        f"{row['p_value']:.3f} ; effet {row['taille_effet']}). Une vente {last_year} prise au hasard "
        f"a {chance:.0f} % de chances d'être plus chère au m² qu'une vente {first_year}."
    )


def price_tests(df: pd.DataFrame, first_year: int, last_year: int, alpha: float, min_n: int) -> pd.DataFrame:
    """Mann-Whitney U per main city and property type, first vs last full year."""
    data = with_all_types(df[df["ville_principale"].notna()])
    groups = [
        (city, typ, sub)
        for (city, typ), sub in data.groupby(["ville_principale", "type_local"])
        if (sub["annee"] == first_year).sum() >= min_n and (sub["annee"] == last_year).sum() >= min_n
    ]
    n_tests = len(groups)
    rows = []
    for city, typ, sub in groups:
        first = sub.loc[sub["annee"] == first_year, "prix_m2"].to_numpy()
        last = sub.loc[sub["annee"] == last_year, "prix_m2"].to_numpy()
        res = mann_whitney(first, last, alpha, n_tests)
        rows.append(
            {
                "ville_principale": city,
                "type_local": typ,
                f"n_{first_year}": len(first),
                f"n_{last_year}": len(last),
                f"mediane_{first_year}": float(np.median(first)),
                f"mediane_{last_year}": float(np.median(last)),
                "evol_mediane_pct": (np.median(last) / np.median(first) - 1) * 100,
                "evol_volume_pct": (len(last) / len(first) - 1) * 100,
                **res,
                "interpretation": interpret(
                    city if typ == ALL_TYPES else f"{city} ({typ.lower()}s)", res, first_year, last_year
                ),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def fig_distribution(df: pd.DataFrame, metropoles: Sequence[str], last: int) -> go.Figure:
    """Box plots of price per m² by metropolis and type (last year)."""
    data = df[(df["ville_principale"].isin(metropoles)) & (df["annee"] == last)]
    order = data.groupby("ville_principale")["prix_m2"].median().sort_values().index.tolist()
    fig = go.Figure()
    for typ, color in (("Appartement", CATEGORICAL[0]), ("Maison", CATEGORICAL[1])):
        sub = data[data["type_local"] == typ]
        fig.add_trace(
            go.Box(
                x=sub["ville_principale"], y=sub["prix_m2"], name=typ, marker_color=color,
                boxpoints=False, line={"width": 1.5}, fillcolor=color, opacity=0.85,
            )
        )
    fig.update_layout(boxmode="group", boxgap=0.35, boxgroupgap=0.12)
    fig.update_xaxes(categoryorder="array", categoryarray=order, title=None)
    fig.update_yaxes(title="Prix au m² (€)", tickformat=",.0f", rangemode="tozero")
    base_layout(fig, f"Distribution des prix au m² dans les 5 métropoles ({last})",
                "Boîtes : 1er quartile, médiane, 3e quartile ; moustaches : 1,5 x l'écart interquartile")
    add_source(fig)
    return fig


def dodge_labels(values: Sequence[float], min_gap: float) -> list[float]:
    """Spread end-of-line label positions so that they are at least ``min_gap`` apart."""
    order = np.argsort(values)
    placed = np.asarray(values, dtype=float)[order].copy()
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + min_gap)
    out = np.empty_like(placed)
    out[order] = placed
    return out.tolist()


def fig_monthly_price(monthly: pd.DataFrame, metropoles: Sequence[str]) -> go.Figure:
    """Rolling 3-month median price per m², one line per metropolis."""
    colors = city_colors(metropoles)
    fig = go.Figure()
    ends = []
    for city in metropoles:
        sub = monthly[monthly["ville_principale"] == city].sort_values("debut_mois")
        fig.add_trace(
            go.Scatter(
                x=sub["debut_mois"], y=sub["prix_m2_median_3m"], name=city, mode="lines",
                line={"color": colors[city], "width": 2},
            )
        )
        ends.append((city, sub.iloc[-1]["debut_mois"], sub.iloc[-1]["prix_m2_median_3m"]))
    span = monthly["prix_m2_median_3m"].max() - monthly["prix_m2_median_3m"].min()
    label_y = dodge_labels([e[2] for e in ends], min_gap=span * 0.05)
    for (city, x, _), y in zip(ends, label_y):
        fig.add_annotation(
            x=x, y=y, text=f" {city}", showarrow=False, xanchor="left",
            font={"size": 12, "color": INK_2},
        )
    fig.update_yaxes(title="Prix médian au m² (€), glissant 3 mois", tickformat=",.0f")
    fig.update_xaxes(dtick="M6", tickformat="%m/%Y", range=[monthly["debut_mois"].min(), monthly["debut_mois"].max() + pd.DateOffset(months=5)])
    base_layout(fig, "Prix médian au m² : pic en 2022, repli ensuite à Lyon, Bordeaux et Nantes",
                "Médiane glissante sur 3 mois, maisons et appartements")
    add_source(fig)
    return fig


def fig_monthly_volume(monthly: pd.DataFrame, metropoles: Sequence[str], base_year: int) -> go.Figure:
    """Monthly sales indexed to the base-year monthly average (= 100), one axis."""
    colors = city_colors(metropoles)
    fig = go.Figure()
    for city in metropoles:
        sub = monthly[monthly["ville_principale"] == city].sort_values("debut_mois").copy()
        base = sub.loc[sub["debut_mois"].dt.year == base_year, "nb_ventes"].mean()
        sub["indice"] = (sub["nb_ventes"].rolling(3, min_periods=1).mean() / base) * 100
        fig.add_trace(
            go.Scatter(x=sub["debut_mois"], y=sub["indice"], name=city, mode="lines",
                       line={"color": colors[city], "width": 2})
        )
    fig.add_hline(y=100, line={"color": AXIS, "width": 1, "dash": "dot"})
    fig.update_yaxes(title=f"Indice volume (moyenne mensuelle {base_year} = 100)")
    fig.update_xaxes(dtick="M6", tickformat="%m/%Y")
    base_layout(fig, "Volume de ventes : décrochage de 2023-2024, reprise partielle en 2025",
                f"Ventes mensuelles lissées sur 3 mois, indice base 100 = moyenne {base_year}")
    add_source(fig)
    return fig


def fig_rate_effect(effect: pd.DataFrame, before: int, after: int, metropoles: Sequence[str]) -> go.Figure:
    """Scatter: change in volume (x) vs change in price (y), one point per city."""
    is_metro = effect["ville_principale"].isin(metropoles)
    fig = go.Figure()
    for flag, name, color in ((True, "Métropole", SEQ_DARK), (False, "Autre ville suivie", SEQ_LIGHT)):
        sub = effect[is_metro == flag]
        fig.add_trace(
            go.Scatter(
                x=sub["evol_volume_hausse_taux_pct"], y=sub["evol_prix_hausse_taux_pct"],
                mode="markers+text", name=name, text=sub["ville_principale"], textposition="top center",
                textfont={"size": 11, "color": INK_2},
                marker={"size": 11, "color": color, "line": {"color": SURFACE, "width": 2}},
            )
        )
    fig.add_hline(y=0, line={"color": AXIS, "width": 1})
    fig.update_xaxes(title=f"Variation du nombre de ventes {before} → {after} (%)", ticksuffix=" %",
                     showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title=f"Variation du prix médian au m² {before} → {after} (%)", ticksuffix=" %")
    base_layout(fig, "Hausse des taux : les volumes ont plongé, les prix ont peu bougé",
                f"Chaque point est une ville ; {before} = taux bas, {after} = taux au plus haut", height=560)
    add_source(fig)
    return fig


def fig_price_change(ranking: pd.DataFrame, first: int, last: int) -> go.Figure:
    """Bar chart of the price change first → last year, diverging colours."""
    data = ranking.sort_values("evol_prix_total_pct")
    colors = [UP if v > 0 else DOWN for v in data["evol_prix_total_pct"]]
    fig = go.Figure(
        go.Bar(
            x=data["evol_prix_total_pct"], y=data["ville_principale"], orientation="h",
            marker={"color": colors, "line": {"color": SURFACE, "width": 2}},
            text=[f"{v:+.1f} %".replace(".", ",") for v in data["evol_prix_total_pct"]],
            textposition="outside", textfont={"color": INK_2}, showlegend=False,
        )
    )
    fig.add_vline(x=0, line={"color": AXIS, "width": 1})
    fig.update_xaxes(title=f"Variation du prix médian au m² {first} → {last} (%)", ticksuffix=" %",
                     showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title=None, showgrid=False)
    rng = data["evol_prix_total_pct"].abs().max() * 1.25
    fig.update_xaxes(range=[-rng, rng])
    base_layout(fig, f"Évolution des prix {first} → {last} : les grandes métropoles reculent",
                "Rouge : hausse ; bleu : baisse. Maisons et appartements confondus", height=600)
    add_source(fig)
    return fig


def fig_affordability(afford: pd.DataFrame, budgets: Sequence[int], last: int) -> go.Figure:
    """Small multiples: m² of apartment buyable per budget, cities sorted."""
    data = afford[afford["type_local"] == "Appartement"]
    order = (
        data[data["budget"] == budgets[0]].sort_values("m2_achetables")["ville_principale"].tolist()
    )
    fig = make_subplots(
        rows=1, cols=len(budgets), shared_yaxes=True, horizontal_spacing=0.03,
        subplot_titles=[f"Budget {b // 1000} k€" for b in budgets],
    )
    for i, budget in enumerate(budgets, start=1):
        sub = data[data["budget"] == budget].set_index("ville_principale").loc[order]
        fig.add_trace(
            go.Bar(
                x=sub["m2_achetables"], y=sub.index, orientation="h", marker_color=SEQ_MID,
                text=[f"{v:.0f}" for v in sub["m2_achetables"]], textposition="outside",
                textfont={"size": 11, "color": INK_2}, showlegend=False,
            ),
            row=1, col=i,
        )
        fig.update_xaxes(range=[0, data["m2_achetables"].max() * 1.2], showgrid=False,
                         showticklabels=False, ticks="", row=1, col=i)
    base_layout(fig, f"Combien de m² d'appartement pour mon budget ? ({last})",
                "Budget divisé par le prix médian au m² des appartements de la ville", height=620)
    fig.update_xaxes(ticks="", showticklabels=False)
    fig.update_annotations(font={"size": 13, "color": INK})
    add_source(fig, "Hors frais de notaire.")
    return fig


def fig_tests(tests: pd.DataFrame, first: int, last: int) -> go.Figure:
    """Dumbbell chart: median price per m² first vs last year, significance flagged."""
    data = tests[tests["type_local"] == ALL_TYPES].sort_values(f"mediane_{last}")
    fig = go.Figure()
    for r in data.itertuples():
        fig.add_trace(
            go.Scatter(
                x=[getattr(r, f"mediane_{first}"), getattr(r, f"mediane_{last}")],
                y=[r.ville_principale] * 2, mode="lines", line={"color": AXIS, "width": 2},
                showlegend=False, hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Scatter(x=data[f"mediane_{first}"], y=data["ville_principale"], mode="markers",
                   name=str(first), marker={"size": 11, "color": SEQ_LIGHT, "line": {"color": SURFACE, "width": 2}})
    )
    fig.add_trace(
        go.Scatter(x=data[f"mediane_{last}"], y=data["ville_principale"], mode="markers",
                   name=str(last), marker={"size": 11, "color": SEQ_DARK, "line": {"color": SURFACE, "width": 2}})
    )
    labels = [
        ("significatif, effet " + t) if s else "non significatif"
        for s, t in zip(data["significatif"], data["taille_effet"])
    ]
    xmax = data[[f"mediane_{first}", f"mediane_{last}"]].max(axis=1)
    for y, x, lab in zip(data["ville_principale"], xmax, labels):
        fig.add_annotation(x=x, y=y, text=f"  {lab}", showarrow=False, xanchor="left",
                           font={"size": 11, "color": MUTED})
    fig.update_xaxes(title="Prix médian au m² (€)", tickformat=",.0f", showgrid=True, gridcolor=GRID,
                     range=[data[f"mediane_{first}"].min() * 0.85, xmax.max() * 1.32])
    fig.update_yaxes(showgrid=False)
    base_layout(fig, f"Test de Mann-Whitney : prix au m² {first} vs {last}",
                "Seuil de Bonferroni sur l'ensemble des tests ; taille d'effet = corrélation rang-bisérielle",
                height=600)
    add_source(fig)
    return fig


def fig_income(ratio: pd.DataFrame, last: int) -> go.Figure:
    """Years of median household income to buy the median dwelling, per city."""
    data = ratio.sort_values("annees_de_revenu")
    fig = go.Figure(
        go.Bar(
            x=data["annees_de_revenu"], y=data["ville_principale"], orientation="h",
            marker={"color": SEQ_MID, "line": {"color": SURFACE, "width": 2}},
            text=[f"{v:.1f} ans".replace(".", ",") for v in data["annees_de_revenu"]],
            textposition="outside", textfont={"color": INK_2}, showlegend=False,
        )
    )
    fig.update_xaxes(title="Années de revenu disponible médian d'un ménage", showgrid=True, gridcolor=GRID,
                     range=[0, data["annees_de_revenu"].max() * 1.18])
    fig.update_yaxes(showgrid=False, autorange="reversed")
    base_layout(fig, f"Effort d'achat : prix médian d'un logement ({last}) / revenu médian du ménage",
                "Revenu : INSEE Filosofi 2021 (niveau de vie médian x unités de consommation par ménage)",
                height=600)
    add_source(fig)
    return fig


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run() -> dict:
    """Compute every table, test and figure; return the summary dictionary."""
    cfg = load_config()
    acfg = cfg["analysis"]
    metropoles = cfg["metropoles"]
    df = pd.read_parquet(project_path("processed") / PROCESSED_FILE)
    # Only complete years are compared: every month must be present
    months = df.groupby("annee")["mois"].nunique()
    full_years = months[months == 12].index
    first, last = int(full_years.min()), int(full_years.max())
    before, after = acfg["rate_rise"]["before_year"], acfg["rate_rise"]["after_year"]
    tables_dir = project_path("tables")

    areas = price_by_area(df)
    yearly = city_yearly(df)
    monthly = city_monthly(df)
    effect = rate_rise_effect(yearly, before, after, last)
    ranking = city_ranking(effect, last)
    afford = affordability(yearly, acfg["budgets"], last)
    ratio = income_ratio(yearly, cfg, last)
    tests = price_tests(df, first, last, acfg["alpha"], acfg["min_sales_for_test"])

    outputs = {
        **areas,
        "evolution_annuelle_ville": yearly,
        "tendance_mensuelle_ville": monthly,
        "effet_hausse_taux": effect,
        "classement_villes": ranking,
        "accessibilite_budget": afford,
        "accessibilite_revenu": ratio,
        "tests_mann_whitney": tests,
    }
    for name, table in outputs.items():
        table.to_csv(tables_dir / f"{name}.csv", index=False, float_format="%.4f")
        logger.info("Table saved: %s.csv (%d rows)", name, len(table))

    save_figure(fig_distribution(df, metropoles, last), "01_distribution_prix_m2")
    save_figure(fig_monthly_price(monthly, metropoles), "02_tendance_prix_m2")
    save_figure(fig_monthly_volume(monthly, metropoles, first), "03_volume_ventes")
    save_figure(fig_rate_effect(effect, before, after, metropoles), "04_effet_hausse_taux")
    save_figure(fig_price_change(ranking, first, last), "05_classement_evolution_prix")
    save_figure(fig_affordability(afford, acfg["budgets"], last), "06_simulateur_budget")
    save_figure(fig_tests(tests, first, last), "07_test_mann_whitney")
    if not ratio.empty:
        save_figure(fig_income(ratio, last), "08_annees_de_revenu")

    summary = build_summary(df, areas, yearly, effect, ranking, afford, ratio, tests, first, last, before, after)
    (tables_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Summary saved: summary.json")
    return summary


def build_summary(
    df: pd.DataFrame,
    areas: dict[str, pd.DataFrame],
    yearly: pd.DataFrame,
    effect: pd.DataFrame,
    ranking: pd.DataFrame,
    afford: pd.DataFrame,
    ratio: pd.DataFrame,
    tests: pd.DataFrame,
    first: int,
    last: int,
    before: int,
    after: int,
) -> dict:
    """Headline numbers (rounded) quoted in the findings and the README."""
    vol = df.groupby("annee").size()
    med = df.groupby("annee")["prix_m2"].median()
    ens = tests[tests["type_local"] == ALL_TYPES]
    return {
        "periode": [first, last],
        "nb_ventes_total": int(len(df)),
        "nb_communes": int(df["code_commune"].nunique()),
        "ventes_par_annee": {int(k): int(v) for k, v in vol.items()},
        "prix_m2_median_par_annee": {int(k): round(float(v)) for k, v in med.items()},
        "evol_volume_perimetre_pct": {
            f"{before}_{after}": round(float((vol[after] / vol[before] - 1) * 100), 1),
            f"{first}_{last}": round(float((vol[last] / vol[first] - 1) * 100), 1),
        },
        "evol_prix_perimetre_pct": {
            f"{before}_{after}": round(float((med[after] / med[before] - 1) * 100), 1),
            f"{first}_{last}": round(float((med[last] / med[first] - 1) * 100), 1),
        },
        "effet_hausse_taux": effect.round(1).to_dict(orient="records"),
        "classement": ranking.round(1).to_dict(orient="records"),
        "tests_significatifs": int(ens["significatif"].sum()),
        "tests_total": int(len(ens)),
        "accessibilite_appartement": afford[afford["type_local"] == "Appartement"]
        .round(1).to_dict(orient="records"),
        "annees_de_revenu": ratio.round(1).to_dict(orient="records"),
        "prix_departement_derniere_annee": areas["prix_departement"]
        .query("annee == @last").round(0).to_dict(orient="records"),
    }


if __name__ == "__main__":
    setup_logging()
    run()
