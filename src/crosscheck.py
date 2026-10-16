"""Cross-check: medians computed in PostgreSQL must equal the pandas medians.

Compares the median price per m² of a few (city, year) pairs computed by the
SQL view ``v_evolution_annuelle_ville`` and by pandas on the Parquet file, and
writes the result to ``reports/tables/crosscheck_sql_python.csv``.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from src.clean import PROCESSED_FILE
from src.load_postgres import get_engine
from src.settings import load_config, project_path, setup_logging

logger = logging.getLogger("crosscheck")

CHECKS = [("Lyon", 2021), ("Lyon", 2025), ("Bordeaux", 2021), ("Bordeaux", 2025)]
TOLERANCE_EUR = 0.01


def run() -> pd.DataFrame:
    """Return the comparison table; raise if any difference exceeds the tolerance."""
    schema = load_config()["database"]["schema"]
    sales = pd.read_parquet(project_path("processed") / PROCESSED_FILE)
    rows = []
    with get_engine().connect() as conn:
        for city, year in CHECKS:
            for typ in ("Ensemble", "Appartement", "Maison"):
                sql = text(
                    f"SELECT prix_m2_median, nb_ventes FROM {schema}.v_evolution_annuelle_ville "
                    "WHERE ville_principale = :city AND annee = :year AND type_local = :typ"
                )
                sql_median, sql_count = conn.execute(sql, {"city": city, "year": year, "typ": typ}).one()
                mask = (sales["ville_principale"] == city) & (sales["annee"] == year)
                if typ != "Ensemble":
                    mask &= sales["type_local"] == typ
                py = sales.loc[mask, "prix_m2"]
                rows.append(
                    {
                        "ville": city,
                        "annee": year,
                        "type_local": typ,
                        "nb_ventes_sql": int(sql_count),
                        "nb_ventes_python": int(py.size),
                        "prix_m2_median_sql": round(float(sql_median), 4),
                        "prix_m2_median_python": round(float(py.median()), 4),
                    }
                )
    result = pd.DataFrame(rows)
    result["ecart_eur"] = (result["prix_m2_median_sql"] - result["prix_m2_median_python"]).abs()
    result["ok"] = (result["ecart_eur"] <= TOLERANCE_EUR) & (
        result["nb_ventes_sql"] == result["nb_ventes_python"]
    )
    result.to_csv(project_path("tables") / "crosscheck_sql_python.csv", index=False)
    logger.info("SQL vs Python cross-check:\n%s", result.to_string(index=False))
    if not result["ok"].all():
        raise AssertionError("SQL and Python medians differ: see crosscheck_sql_python.csv")
    logger.info("Cross-check passed: %d comparisons identical", len(result))
    return result


if __name__ == "__main__":
    setup_logging()
    run()
