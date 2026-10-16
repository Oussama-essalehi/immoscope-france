"""Geography helpers: regions and departments in scope, main cities.

* The scope is a list of regions, each with its departments (``config.yaml``).
* Paris, Lyon and Marseille are split into arrondissements in DVF (75101...,
  69381..., 13201...): they are grouped under the whole commune (75056, 69123,
  13055) to compare cities.
* The main cities are the ``top_n`` most populated communes of the scope
  (INSEE Filosofi population), or the communes with the most sales when the
  income file is not available.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("geo")


def departments(cfg: dict) -> list[str]:
    """Department codes in scope, in configuration order."""
    return [d for region in cfg["scope"]["regions"].values() for d in region["departments"]]


def department_table(cfg: dict) -> pd.DataFrame:
    """One row per department: code, label, region code and region name."""
    rows = [
        {"code_departement": dep, "nom_departement": label, "code_region": reg, "region": region["name"]}
        for reg, region in cfg["scope"]["regions"].items()
        for dep, label in region["departments"].items()
    ]
    return pd.DataFrame(rows)


def city_code(code_commune: str, arrondissements: dict[str, str]) -> str:
    """Code of the whole city: arrondissement codes map to their commune."""
    for prefix, whole in arrondissements.items():
        if code_commune.startswith(prefix):
            return whole
    return code_commune


def add_region(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add ``code_region`` and ``region`` from the department code."""
    lookup = department_table(cfg).set_index("code_departement")
    out = df.copy()
    out["code_region"] = out["code_departement"].map(lookup["code_region"]).astype("string")
    out["region"] = out["code_departement"].map(lookup["region"]).astype("string")
    return out


def select_main_cities(sales: pd.DataFrame, cfg: dict, income: pd.DataFrame) -> pd.DataFrame:
    """Rank the cities of the scope and keep the ``top_n`` largest.

    Returns one row per city: ``rang``, ``code_ville``, ``ville``, ``population``
    (``None`` without income data), ``nb_ventes``, ``code_departement``,
    ``est_metropole`` (the ``highlight_n`` largest).
    """
    settings = cfg["main_cities"]
    arr = settings["arrondissements"]
    codes = sales["code_commune"].astype(str)
    frame = pd.DataFrame(
        {
            "code_ville": codes.map(lambda c: city_code(c, arr)),
            "nom_commune": sales["nom_commune"].astype(str),
            "code_departement": sales["code_departement"].astype(str),
        }
    )
    grouped = frame.groupby("code_ville").agg(
        ville=("nom_commune", lambda s: s.mode().iloc[0]),
        nb_ventes=("nom_commune", "size"),
        code_departement=("code_departement", "first"),
    )
    labels = settings.get("labels", {})
    grouped["ville"] = [labels.get(code, name) for code, name in zip(grouped.index, grouped["ville"])]

    if "population" in income.columns and not income.empty:
        population = income.set_index("code_geo")["population"]
        grouped["population"] = grouped.index.map(population)
        ranked = grouped.dropna(subset=["population"]).sort_values("population", ascending=False)
        logger.info("Main cities ranked by INSEE population")
    else:
        grouped["population"] = None
        ranked = grouped.sort_values("nb_ventes", ascending=False)
        logger.warning("No population data: main cities ranked by number of sales")

    top = ranked.head(int(settings["top_n"])).reset_index()
    top.insert(0, "rang", range(1, len(top) + 1))
    top["est_metropole"] = top["rang"] <= int(settings["highlight_n"])
    return top[["rang", "code_ville", "ville", "population", "nb_ventes", "code_departement", "est_metropole"]]


def assign_cities(sales: pd.DataFrame, cities: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add ``code_ville``, ``ville_principale`` and ``est_metropole`` to the sales."""
    arr = cfg["main_cities"]["arrondissements"]
    out = sales.copy()
    whole = out["code_commune"].astype(str).map(lambda c: city_code(c, arr))
    tracked = cities.set_index("code_ville")
    in_scope = whole.isin(tracked.index)
    out["code_ville"] = whole.where(in_scope).astype("string")
    out["ville_principale"] = out["code_ville"].map(tracked["ville"]).astype("string")
    out["est_metropole"] = out["code_ville"].map(tracked["est_metropole"]).fillna(False).astype(bool)
    return out
