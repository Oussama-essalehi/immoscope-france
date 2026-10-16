"""Export the aggregates used by the React web dashboard (``web/public/data/``).

Medians cannot be re-aggregated in the browser, so every filter combination
offered by the web app (department x property type x year, city x type x year,
...) is pre-computed here from the clean Parquet file. Values therefore match
the Python, SQL and Power BI results exactly.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from src.clean import PROCESSED_FILE
from src.income import read_income
from src.settings import PROJECT_ROOT, load_config, project_path, setup_logging

logger = logging.getLogger("export_web")

WEB_DATA_DIR = PROJECT_ROOT / "web" / "public" / "data"
ALL = "all"
MIN_SALES_COMMUNE = 30


def expand(df: pd.DataFrame, dims: Iterable[str]) -> pd.DataFrame:
    """Duplicate rows so that each dimension also gets an ``all`` member."""
    out = df
    for dim in dims:
        out = pd.concat([out, out.assign(**{dim: ALL})], ignore_index=True)
    return out


def stats(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Sales count and medians for each group."""
    return (
        df.groupby(keys, observed=True)
        .agg(
            n=("prix_m2", "size"),
            p=("prix_m2", "median"),
            v=("valeur_fonciere", "median"),
            s=("surface_reelle_bati", "median"),
        )
        .reset_index()
    )


def key(*parts: object) -> str:
    return "|".join(str(p) for p in parts)


def compact(row: pd.Series, fields: str = "npvs") -> dict:
    """Rounded record: n (count), p (median EUR/m2), v (median price), s (median m2)."""
    out = {"n": int(row["n"])}
    if "p" in fields:
        out["p"] = round(float(row["p"]), 2)
    if "v" in fields:
        out["v"] = round(float(row["v"]))
    if "s" in fields:
        out["s"] = round(float(row["s"]), 1)
    return out


def base_frame(sales: pd.DataFrame) -> pd.DataFrame:
    frame = sales[
        ["code_departement", "type_local", "annee", "annee_mois", "prix_m2", "valeur_fonciere",
         "surface_reelle_bati", "code_commune", "nom_commune", "ville_principale", "trimestre"]
    ].copy()
    frame["annee"] = frame["annee"].astype(str)
    frame["code_departement"] = frame["code_departement"].astype(str)
    frame["type_local"] = frame["type_local"].astype(str)
    frame["annee_trimestre"] = frame["annee"] + "-T" + frame["trimestre"].astype(str)
    return frame


def build_meta(sales: pd.DataFrame, cfg: dict) -> dict:
    years = sorted(int(y) for y in sales["annee"].unique())
    cities = (
        sales.dropna(subset=["ville_principale"])
        .groupby("ville_principale")["code_departement"].first()
    )
    return {
        "source": "DVF géolocalisées (Etalab / DGFiP), ventes d'un seul logement après nettoyage",
        "years": years,
        "lastYear": years[-1],
        "totalSales": int(len(sales)),
        "communes": int(sales["code_commune"].nunique()),
        "departments": [{"code": c, "label": cfg["departments_labels"][c]} for c in cfg["scope"]["departments"]],
        "types": ["Appartement", "Maison"],
        "cities": [
            {"name": name, "dept": str(dept), "metropole": name in cfg["metropoles"]}
            for name, dept in sorted(cities.items(), key=lambda kv: (kv[1], kv[0]))
        ],
        "metropoles": cfg["metropoles"],
        "minSalesCommune": MIN_SALES_COMMUNE,
        "budgets": {"min": 100_000, "max": 500_000, "step": 10_000, "default": 250_000},
    }


def build_overview(frame: pd.DataFrame) -> dict:
    """Monthly and yearly series by department x type (with ``all`` members)."""
    data = expand(frame, ["code_departement", "type_local"])
    monthly = stats(data, ["code_departement", "type_local", "annee_mois"])
    yearly = stats(expand(data, ["annee"]), ["code_departement", "type_local", "annee"])
    out: dict = {"monthly": {}, "yearly": {}}
    for (dept, typ), grp in monthly.groupby(["code_departement", "type_local"]):
        out["monthly"][key(dept, typ)] = [
            {"m": r["annee_mois"], **compact(r, "np")} for _, r in grp.sort_values("annee_mois").iterrows()
        ]
    for (dept, typ), grp in yearly.groupby(["code_departement", "type_local"]):
        out["yearly"][key(dept, typ)] = {r["annee"]: compact(r) for _, r in grp.iterrows()}
    return out


def build_communes(frame: pd.DataFrame, sales: pd.DataFrame) -> dict:
    """Commune list with coordinates, and stats per type x year (>= 30 sales only)."""
    geo = (
        sales.groupby("code_commune")
        .agg(nom=("nom_commune", lambda s: s.mode().iloc[0]), dept=("code_departement", "first"),
             lat=("latitude", "median"), lon=("longitude", "median"))
        .dropna(subset=["lat", "lon"])
        .reset_index()
        .sort_values("code_commune")
        .reset_index(drop=True)
    )
    index = {code: i for i, code in enumerate(geo["code_commune"])}
    data = expand(frame[frame["code_commune"].isin(index)], ["type_local", "annee"])
    grouped = stats(data, ["type_local", "annee", "code_commune"])
    grouped = grouped[grouped["n"] >= MIN_SALES_COMMUNE]
    out = {
        "list": [
            [r.code_commune, r.nom, str(r.dept), round(r.lat, 4), round(r.lon, 4)]
            for r in geo.itertuples()
        ],
        "stats": {},
    }
    for (typ, year), grp in grouped.groupby(["type_local", "annee"]):
        out["stats"][key(typ, year)] = [
            [index[r.code_commune], int(r.n), round(float(r.p), 2)] for r in grp.itertuples()
        ]
    return out


def build_cities(frame: pd.DataFrame, cfg: dict) -> dict:
    """Yearly and quarterly stats per main city x type, plus household income."""
    data = expand(frame[frame["ville_principale"].notna()], ["type_local"])
    yearly = stats(expand(data, ["annee"]), ["ville_principale", "type_local", "annee"])
    quarterly = stats(data, ["ville_principale", "type_local", "annee_trimestre"])
    out: dict = {"yearly": {}, "quarterly": {}, "income": {}}
    for (city, typ), grp in yearly.groupby(["ville_principale", "type_local"]):
        out["yearly"][key(city, typ)] = {r["annee"]: compact(r) for _, r in grp.iterrows()}
    for (city, typ), grp in quarterly.groupby(["ville_principale", "type_local"]):
        out["quarterly"][key(city, typ)] = [
            {"q": r["annee_trimestre"], **compact(r, "np")} for _, r in grp.sort_values("annee_trimestre").iterrows()
        ]
    income = read_income()
    if not income.empty:
        rev = income.set_index("code_geo")["revenu_menage_median"]
        for code, city in cfg["main_cities"].items():
            city_code = "69123" if code.startswith("6938") else code
            if city_code in rev.index and city not in out["income"]:
                out["income"][city] = int(rev[city_code])
    return out


def write_json(name: str, payload: dict, target_dir: Path) -> Path:
    target = target_dir / f"{name}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    logger.info("Wrote %-14s %7.1f kB", target.name, target.stat().st_size / 1e3)
    return target


def run(target_dir: Path = WEB_DATA_DIR) -> list[Path]:
    cfg = load_config()
    sales = pd.read_parquet(project_path("processed") / PROCESSED_FILE)
    frame = base_frame(sales)
    target_dir.mkdir(parents=True, exist_ok=True)
    return [
        write_json("meta", build_meta(sales, cfg), target_dir),
        write_json("overview", build_overview(frame), target_dir),
        write_json("communes", build_communes(frame, sales), target_dir),
        write_json("cities", build_cities(frame, cfg), target_dir),
    ]


if __name__ == "__main__":
    setup_logging()
    run()
