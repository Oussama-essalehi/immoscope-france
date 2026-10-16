"""Export the aggregates used by the React web dashboard (``web/public/data/``).

Medians cannot be re-aggregated in the browser, so every filter combination
offered by the web app is pre-computed here from the clean Parquet file, and
values match the Python, SQL and Power BI results exactly.

Files
-----
* ``meta.json``: years, regions with their departments, tracked cities;
* ``overview.json``: monthly and yearly series per zone x property type, where a
  zone is ``all``, a region (``R11``) or a department (``75``);
* ``departements.json``: one map point per department (national map view);
* ``communes_R<code>.json``: communes of one region (loaded on demand by the map);
* ``communes_top.json``: most / least expensive communes of the whole scope;
* ``cities.json``: yearly and quarterly stats of the tracked cities, income.
"""

from __future__ import annotations

import json
import logging
from itertools import product
from pathlib import Path

import pandas as pd

from src.clean import CITIES_FILE, PROCESSED_FILE
from src.geo import department_table
from src.income import read_income
from src.settings import PROJECT_ROOT, load_config, project_path, setup_logging

logger = logging.getLogger("export_web")

WEB_DATA_DIR = PROJECT_ROOT / "web" / "public" / "data"
ALL = "all"
MIN_SALES_COMMUNE = 30
TOP_COMMUNES = 10


def key(*parts: object) -> str:
    return "|".join(str(p) for p in parts)


def stats(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Sales count and medians (price/m², price, surface) for each group."""
    grouped = df.groupby(keys, observed=True) if keys else df.assign(_all=0).groupby("_all")
    out = grouped.agg(
        n=("prix_m2", "size"),
        p=("prix_m2", "median"),
        v=("valeur_fonciere", "median"),
        s=("surface_reelle_bati", "median"),
    ).reset_index()
    return out.drop(columns="_all", errors="ignore")


def stats_with_all(df: pd.DataFrame, keys: list[str], optional: list[str]) -> pd.DataFrame:
    """Like :func:`stats`, also for every subset of ``optional`` keys set to ``all``.

    Avoids duplicating millions of rows: each subset is one more group-by.
    """
    frames = []
    for mask in product([True, False], repeat=len(optional)):
        kept = [k for k, keep in zip(optional, mask) if keep]
        part = stats(df, keys + kept)
        for k, keep in zip(optional, mask):
            if not keep:
                part[k] = ALL
        frames.append(part)
    return pd.concat(frames, ignore_index=True)


def compact(row, fields: str = "npvs") -> dict:
    """Rounded record: n (count), p (median EUR/m2), v (median price), s (median m2)."""
    out = {"n": int(row.n)}
    if "p" in fields:
        out["p"] = round(float(row.p), 2)
    if "v" in fields:
        out["v"] = round(float(row.v))
    if "s" in fields:
        out["s"] = round(float(row.s), 1)
    return out


def base_frame(sales: pd.DataFrame) -> pd.DataFrame:
    frame = sales[
        ["code_region", "code_departement", "type_local", "annee", "annee_mois", "trimestre", "prix_m2",
         "valeur_fonciere", "surface_reelle_bati", "code_commune", "ville_principale"]
    ].copy()
    for col in ("code_region", "code_departement", "type_local", "code_commune"):
        frame[col] = frame[col].astype(str)
    frame["annee"] = frame["annee"].astype(str)
    frame["annee_trimestre"] = frame["annee"] + "-T" + frame["trimestre"].astype(str)
    frame["region_zone"] = "R" + frame["code_region"]
    return frame


def build_meta(sales: pd.DataFrame, cfg: dict, cities: pd.DataFrame) -> dict:
    years = sorted(int(y) for y in sales["annee"].unique())
    deps = department_table(cfg)
    present = set(sales["code_departement"].astype(str))
    city_region = sales.dropna(subset=["ville_principale"]).groupby("ville_principale")["code_region"].first()
    return {
        "source": "DVF géolocalisées (Etalab / DGFiP), ventes d'un seul logement après nettoyage",
        "years": years,
        "lastYear": years[-1],
        "totalSales": int(len(sales)),
        "communes": int(sales["code_commune"].nunique()),
        "regions": [
            {
                "code": reg,
                "name": region["name"],
                "departments": [
                    {"code": d, "label": label} for d, label in region["departments"].items() if d in present
                ],
            }
            for reg, region in cfg["scope"]["regions"].items()
        ],
        "departmentCount": int(deps["code_departement"].isin(present).sum()),
        "types": ["Appartement", "Maison"],
        "cities": [
            {
                "name": r.ville,
                "dept": str(r.code_departement).zfill(2),
                "region": str(city_region.get(r.ville, "")),
                "rank": int(r.rang),
                "metropole": bool(r.est_metropole),
            }
            for r in cities.itertuples()
        ],
        "minSalesCommune": MIN_SALES_COMMUNE,
        "budgets": {"min": 100_000, "max": 500_000, "step": 10_000, "default": 250_000},
    }


def build_overview(frame: pd.DataFrame) -> dict:
    """Monthly and yearly series per zone (all, region, department) x type."""
    out: dict = {"monthly": {}, "yearly": {}}
    for zone_col in (None, "region_zone", "code_departement"):
        keys = [zone_col] if zone_col else []
        monthly = stats_with_all(frame, keys + ["annee_mois"], ["type_local"])
        yearly = stats_with_all(frame, keys, ["type_local", "annee"])
        if not zone_col:
            monthly["zone"], yearly["zone"] = ALL, ALL
        else:
            monthly["zone"], yearly["zone"] = monthly[zone_col], yearly[zone_col]
        for (zone, typ), grp in monthly.groupby(["zone", "type_local"]):
            out["monthly"][key(zone, typ)] = [
                {"m": r.annee_mois, **compact(r, "np")} for r in grp.sort_values("annee_mois").itertuples()
            ]
        for (zone, typ), grp in yearly.groupby(["zone", "type_local"]):
            out["yearly"][key(zone, typ)] = {r.annee: compact(r) for r in grp.itertuples()}
    return out


def geo_points(sales: pd.DataFrame, level: str) -> pd.DataFrame:
    """Map coordinates (median of the sale coordinates) and name per commune or department."""
    names = "nom_commune" if level == "code_commune" else "code_departement"
    return (
        sales.groupby(level)
        .agg(nom=(names, lambda s: s.mode().iloc[0]), dept=("code_departement", "first"),
             region=("code_region", "first"), lat=("latitude", "median"), lon=("longitude", "median"))
        .dropna(subset=["lat", "lon"])
        .reset_index()
        .sort_values(level)
        .reset_index(drop=True)
    )


def points_payload(points: pd.DataFrame, level: str, frame: pd.DataFrame, min_sales: int) -> dict:
    """Point list and stats per type x year: ``[index, n, p]`` rows."""
    index = {code: i for i, code in enumerate(points[level].astype(str))}
    subset = frame[frame[level].isin(index)]
    grouped = stats_with_all(subset, [level], ["type_local", "annee"])
    grouped = grouped[grouped["n"] >= min_sales]
    payload = {
        "list": [[str(r[level]), r["nom"], str(r["dept"]), round(r["lat"], 4), round(r["lon"], 4)] for _, r in points.iterrows()],
        "stats": {},
    }
    for (typ, year), grp in grouped.groupby(["type_local", "annee"]):
        payload["stats"][key(typ, year)] = [[index[str(r[level])], int(r["n"]), round(float(r["p"]), 2)] for _, r in grp.iterrows()]
    return payload


def build_departments(sales: pd.DataFrame, frame: pd.DataFrame, cfg: dict) -> dict:
    points = geo_points(sales, "code_departement")
    labels = department_table(cfg).set_index("code_departement")["nom_departement"]
    points["nom"] = points["code_departement"].map(labels)
    return points_payload(points, "code_departement", frame, 1)


def build_region_communes(sales: pd.DataFrame, frame: pd.DataFrame, region: str) -> dict:
    points = geo_points(sales[sales["code_region"] == region], "code_commune")
    return points_payload(points, "code_commune", frame[frame["code_region"] == region], MIN_SALES_COMMUNE)


def build_top_communes(sales: pd.DataFrame, frame: pd.DataFrame) -> dict:
    """Most / least expensive communes of the whole scope per type x year (>= 30 sales)."""
    names = sales.groupby("code_commune")["nom_commune"].agg(lambda s: s.mode().iloc[0])
    depts = sales.groupby("code_commune")["code_departement"].first()
    grouped = stats_with_all(frame, ["code_commune"], ["type_local", "annee"])
    grouped = grouped[grouped["n"] >= MIN_SALES_COMMUNE]
    out: dict = {}
    for (typ, year), grp in grouped.groupby(["type_local", "annee"]):
        ordered = grp.sort_values("p", ascending=False)
        rows = lambda part: [  # noqa: E731
            [r.code_commune, names[r.code_commune], str(depts[r.code_commune]), int(r.n), round(float(r.p), 2)]
            for r in part.itertuples()
        ]
        out[key(typ, year)] = {"top": rows(ordered.head(TOP_COMMUNES)), "bottom": rows(ordered.tail(TOP_COMMUNES).iloc[::-1])}
    return out


def build_cities(frame: pd.DataFrame, sales: pd.DataFrame) -> dict:
    """Yearly and quarterly stats per tracked city x type, plus household income."""
    data = frame[frame["ville_principale"].notna()]
    yearly = stats_with_all(data, ["ville_principale"], ["type_local", "annee"])
    quarterly = stats_with_all(data, ["ville_principale", "annee_trimestre"], ["type_local"])
    out: dict = {"yearly": {}, "quarterly": {}, "income": {}}
    for (city, typ), grp in yearly.groupby(["ville_principale", "type_local"]):
        out["yearly"][key(city, typ)] = {r.annee: compact(r) for r in grp.itertuples()}
    for (city, typ), grp in quarterly.groupby(["ville_principale", "type_local"]):
        out["quarterly"][key(city, typ)] = [
            {"q": r.annee_trimestre, **compact(r, "np")} for r in grp.sort_values("annee_trimestre").itertuples()
        ]
    income = read_income()
    if not income.empty:
        revenue = income.set_index("code_geo")["revenu_menage_median"]
        codes = sales.dropna(subset=["ville_principale"]).groupby("ville_principale")["code_ville"].first()
        for city, code in codes.items():
            if code in revenue.index and pd.notna(revenue[code]):
                out["income"][city] = int(revenue[code])
    return out


def write_json(name: str, payload: dict, target_dir: Path) -> Path:
    target = target_dir / f"{name}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    logger.info("Wrote %-20s %7.1f kB", target.name, target.stat().st_size / 1e3)
    return target


def run(target_dir: Path = WEB_DATA_DIR) -> list[Path]:
    cfg = load_config()
    sales = pd.read_parquet(project_path("processed") / PROCESSED_FILE)
    sales["code_region"] = sales["code_region"].astype(str)
    cities = pd.read_csv(project_path("tables") / CITIES_FILE, dtype={"code_ville": str, "code_departement": str})
    frame = base_frame(sales)
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob("communes*.json"):
        old.unlink()  # files of a previous scope
    paths = [
        write_json("meta", build_meta(sales, cfg, cities), target_dir),
        write_json("overview", build_overview(frame), target_dir),
        write_json("departements", build_departments(sales, frame, cfg), target_dir),
        write_json("communes_top", build_top_communes(sales, frame), target_dir),
        write_json("cities", build_cities(frame, sales), target_dir),
    ]
    for region in sorted(sales["code_region"].unique()):
        paths.append(write_json(f"communes_R{region}", build_region_communes(sales, frame, region), target_dir))
    return paths


if __name__ == "__main__":
    setup_logging()
    run()
