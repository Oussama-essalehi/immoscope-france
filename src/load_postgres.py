"""Build the star schema from the clean Parquet file and load it into PostgreSQL.

Steps: run ``sql/01_schema.sql`` (recreates the ``dvf`` schema), build the
dimension and fact frames with pandas, bulk-load them with ``COPY``, then run
``sql/02_views.sql``.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from src.clean import PROCESSED_FILE
from src.geo import department_table
from src.income import read_income
from src.settings import PROJECT_ROOT, DatabaseSettings, load_config, project_path, setup_logging

logger = logging.getLogger("load")

SQL_DIR = PROJECT_ROOT / "sql"
MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
TYPE_LOCAL_KEYS = {"Appartement": 1, "Maison": 2}


# --------------------------------------------------------------------------- #
# Star schema construction (pandas)
# --------------------------------------------------------------------------- #
def build_dim_date(first_year: int, last_year: int) -> pd.DataFrame:
    """Daily calendar covering complete years ``first_year`` .. ``last_year``."""
    dates = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31", freq="D")
    return pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "date": dates.date,
            "annee": dates.year,
            "semestre": (dates.month > 6).astype(int) + 1,
            "trimestre": dates.quarter,
            "mois": dates.month,
            "mois_nom": [MONTHS_FR[m - 1] for m in dates.month],
            "annee_mois": dates.strftime("%Y-%m"),
            "annee_trimestre": [f"{y}-T{q}" for y, q in zip(dates.year, dates.quarter)],
            "debut_mois": dates.to_period("M").to_timestamp().date,
            "jour_semaine": dates.dayofweek + 1,
        }
    )


def build_dim_commune(sales: pd.DataFrame, cfg: dict, income: pd.DataFrame) -> pd.DataFrame:
    """One row per commune present in the clean sales, enriched with region and income."""
    names = (
        sales.groupby(["code_commune", "nom_commune"]).size().rename("n").reset_index()
        .sort_values(["code_commune", "n"], ascending=[True, False])
        .drop_duplicates("code_commune")
        .set_index("code_commune")["nom_commune"]
    )
    geo = sales.groupby("code_commune").agg(
        code_departement=("code_departement", "first"),
        code_ville=("code_ville", "first"),
        ville_principale=("ville_principale", "first"),
        est_metropole=("est_metropole", "first"),
        latitude=("latitude", "median"),
        longitude=("longitude", "median"),
    )
    dim = geo.join(names).reset_index().sort_values("code_commune").reset_index(drop=True)
    dim.insert(0, "commune_key", dim.index + 1)

    deps = department_table(cfg).set_index("code_departement")
    dim["nom_departement"] = dim["code_departement"].map(deps["nom_departement"])
    dim["departement"] = dim["code_departement"] + " - " + dim["nom_departement"]
    dim["code_region"] = dim["code_departement"].map(deps["code_region"])
    dim["region"] = dim["code_departement"].map(deps["region"])
    dim["est_ville_principale"] = dim["ville_principale"].notna()
    dim["est_metropole"] = dim["est_metropole"].fillna(False).astype(bool)

    inc = income.set_index("code_geo")
    dim["niveau_vie_median"] = dim["code_commune"].map(inc["niveau_vie_median"])
    dim["revenu_menage_median"] = dim["code_commune"].map(inc["revenu_menage_median"])
    # City-level income: the whole city for Paris / Lyon / Marseille arrondissements
    dim["revenu_menage_ville"] = dim["code_ville"].map(inc["revenu_menage_median"])
    return dim[
        [
            "commune_key", "code_commune", "nom_commune", "code_departement",
            "nom_departement", "departement", "code_region", "region", "code_ville",
            "ville_principale", "est_ville_principale", "est_metropole", "latitude",
            "longitude", "niveau_vie_median", "revenu_menage_median", "revenu_menage_ville",
        ]
    ]


def build_dim_type_local() -> pd.DataFrame:
    return pd.DataFrame(
        {"type_local_key": list(TYPE_LOCAL_KEYS.values()), "type_local": list(TYPE_LOCAL_KEYS)}
    )


BAND_COLUMNS = {"tranche_prix": "price", "tranche_surface": "surface", "tranche_pieces": "rooms"}
UNKNOWN_BAND_ORDER = 99


def build_dim_profil(sales: pd.DataFrame, bands: dict) -> pd.DataFrame:
    """Junk dimension: one row per observed (price, surface, rooms) band combination."""
    dim = (
        sales[list(BAND_COLUMNS)].drop_duplicates().astype(str).reset_index(drop=True)
    )
    for column, key in BAND_COLUMNS.items():
        order = {label: i + 1 for i, label in enumerate(bands[key]["labels"])}
        dim[f"{column}_ordre"] = dim[column].map(order).fillna(UNKNOWN_BAND_ORDER).astype(int)
    dim = dim.sort_values([f"{c}_ordre" for c in BAND_COLUMNS]).reset_index(drop=True)
    dim.insert(0, "profil_key", dim.index + 1)
    return dim[
        [
            "profil_key", "tranche_prix", "tranche_prix_ordre", "tranche_surface",
            "tranche_surface_ordre", "tranche_pieces", "tranche_pieces_ordre",
        ]
    ]


def build_fact(sales: pd.DataFrame, dim_commune: pd.DataFrame, dim_profil: pd.DataFrame) -> pd.DataFrame:
    """Fact table at the grain of one single-dwelling sale."""
    commune_keys = dim_commune.set_index("code_commune")["commune_key"]
    profil_keys = (
        sales[list(BAND_COLUMNS)].astype(str)
        .merge(dim_profil[["profil_key", *BAND_COLUMNS]], on=list(BAND_COLUMNS), how="left")
        ["profil_key"].to_numpy()
    )
    fact = pd.DataFrame(
        {
            "id_mutation": sales["id_mutation"],
            "date_key": sales["date_mutation"].dt.strftime("%Y%m%d").astype(int),
            "commune_key": sales["code_commune"].map(commune_keys).astype(int),
            "type_local_key": sales["type_local"].map(TYPE_LOCAL_KEYS).astype(int),
            "profil_key": profil_keys.astype(int),
            "valeur_fonciere": sales["valeur_fonciere"],
            "surface": sales["surface_reelle_bati"],
            "prix_m2": sales["prix_m2"],
            "nb_pieces": sales["nombre_pieces_principales"].astype("Int16"),
            "surface_terrain": sales["surface_terrain"],
            "latitude": sales["latitude"],
            "longitude": sales["longitude"],
        }
    )
    return fact


def build_star_schema(sales: pd.DataFrame, cfg: dict) -> dict[str, pd.DataFrame]:
    """Return the five tables of the star schema, in load order."""
    dim_commune = build_dim_commune(sales, cfg, read_income())
    dim_profil = build_dim_profil(sales, cfg["bands"])
    return {
        "dim_date": build_dim_date(int(sales["annee"].min()), int(sales["annee"].max())),
        "dim_commune": dim_commune,
        "dim_type_local": build_dim_type_local(),
        "dim_profil_bien": dim_profil,
        "fact_ventes": build_fact(sales, dim_commune, dim_profil),
    }


# --------------------------------------------------------------------------- #
# PostgreSQL helpers
# --------------------------------------------------------------------------- #
def get_engine(retries: int = 30, delay: float = 2.0) -> Engine:
    """Create an engine and wait until the database accepts connections."""
    settings = DatabaseSettings.from_config()
    engine = create_engine(settings.url, future=True)
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as exc:  # noqa: BLE001 - any connection error means "not ready yet"
            if attempt == retries:
                raise RuntimeError(
                    f"PostgreSQL unreachable at {settings.host}:{settings.port} "
                    "(start it with `docker compose up -d --wait`)"
                ) from exc
            logger.info("Waiting for PostgreSQL (%d/%d)...", attempt, retries)
            time.sleep(delay)
    raise AssertionError("unreachable")


def run_sql_file(engine: Engine, path: Path) -> None:
    """Execute a SQL script (several statements) in one transaction."""
    logger.info("Running %s", path.name)
    with engine.begin() as conn:
        conn.exec_driver_sql(path.read_text(encoding="utf-8"))


def copy_frame(engine: Engine, frame: pd.DataFrame, table: str, schema: str, chunk_rows: int = 250_000) -> None:
    """Bulk-load a DataFrame with PostgreSQL ``COPY ... FROM STDIN`` (CSV), by chunks."""
    columns = ", ".join(f'"{c}"' for c in frame.columns)
    sql = f"COPY {schema}.{table} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            with cur.copy(sql) as copy:
                for start in range(0, len(frame), chunk_rows):
                    buffer = io.StringIO()
                    frame.iloc[start : start + chunk_rows].to_csv(buffer, index=False, header=False, na_rep="\\N")
                    copy.write(buffer.getvalue())
        raw.commit()
    finally:
        raw.close()
    logger.info("Loaded %-15s %10s rows", table, f"{len(frame):,}")


def run() -> None:
    """Recreate the schema, load the star schema and create the analytical views."""
    cfg = load_config()
    schema = cfg["database"]["schema"]
    sales = pd.read_parquet(project_path("processed") / PROCESSED_FILE)
    tables = build_star_schema(sales, cfg)

    engine = get_engine()
    run_sql_file(engine, SQL_DIR / "01_schema.sql")
    for name, frame in tables.items():
        copy_frame(engine, frame, name, schema)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"ANALYZE {schema}.fact_ventes")
    run_sql_file(engine, SQL_DIR / "02_views.sql")
    logger.info("PostgreSQL star schema ready")


if __name__ == "__main__":
    setup_logging()
    run()
