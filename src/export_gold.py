"""Export the PostgreSQL star schema to CSV files read by Power BI (``data/gold/``).

Format: UTF-8, comma separator, ``.`` as decimal separator, ISO dates
(YYYY-MM-DD), header row. Power BI reads these files, not the database, so the
report opens without PostgreSQL.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.load_postgres import get_engine
from src.settings import load_config, project_path, setup_logging

logger = logging.getLogger("export")

TABLES: dict[str, str] = {
    "dim_date": "date_key",
    "dim_commune": "commune_key",
    "dim_type_local": "type_local_key",
    "dim_profil_bien": "profil_key",
    "fact_ventes": "date_key, id_mutation",
}
# Decimal places kept in the CSV (keeps the files small; prix_m2 keeps 4 decimals
# so that medians match PostgreSQL to the cent).
ROUNDING = {
    "valeur_fonciere": 2,
    "surface": 2,
    "prix_m2": 4,
    "surface_terrain": 2,
    "latitude": 6,
    "longitude": 6,
    "niveau_vie_median": 0,
    "revenu_menage_median": 0,
    "revenu_menage_ville": 0,
}
GIT_SIZE_LIMIT_MB = 50


def compact_numbers(values: pd.Series) -> pd.Series:
    """Write floats without a useless trailing ``.0`` (430000.0 -> 430000)."""
    text = values.map(lambda v: "" if pd.isna(v) else f"{v:.10g}")
    return text.astype("string")


def export_table(table: str, order_by: str, schema: str, target_dir: Path) -> Path:
    """Dump one table to ``<target_dir>/<table>.csv``."""
    with get_engine().connect() as conn:
        frame = pd.read_sql(f"SELECT * FROM {schema}.{table} ORDER BY {order_by}", conn)
    frame = frame.round({k: v for k, v in ROUNDING.items() if k in frame.columns})
    for col in frame.columns:
        if pd.api.types.is_float_dtype(frame[col]):
            frame[col] = compact_numbers(frame[col])
    target = target_dir / f"{table}.csv"
    frame.to_csv(target, index=False, encoding="utf-8", lineterminator="\n", date_format="%Y-%m-%d")
    size_mb = target.stat().st_size / 1e6
    logger.info("Exported %-15s %10s rows  %6.1f MB", table, f"{len(frame):,}", size_mb)
    if size_mb > GIT_SIZE_LIMIT_MB:
        logger.warning("%s is larger than %d MB: keep it out of git", target.name, GIT_SIZE_LIMIT_MB)
    return target


def run() -> list[Path]:
    schema = load_config()["database"]["schema"]
    target_dir = project_path("gold")
    return [export_table(t, order, schema, target_dir) for t, order in TABLES.items()]


if __name__ == "__main__":
    setup_logging()
    run()
