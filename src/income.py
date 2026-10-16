"""Optional enrichment: median income per commune from INSEE Filosofi 2021.

The communal base gives, for each commune (``COM``) and each Paris/Lyon/Marseille
arrondissement (``ARM``), the median standard of living per consumption unit
(``MED_SL``), the number of households (``NUM_HH``), of consumption units
(``NUM_CU``) and of people (``NUM_PER``, used as population to rank cities). The median disposable income of a household is approximated by
``MED_SL * NUM_CU / NUM_HH`` (median per unit x average units per household).
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import pandas as pd

from src.settings import load_config, project_path

logger = logging.getLogger("income")

INCOME_ARCHIVE = "filosofi_communes.zip"
MEASURES = {"MED_SL": "niveau_vie_median", "NUM_HH": "nb_menages", "NUM_CU": "nb_uc", "NUM_PER": "population"}


def archive_path() -> Path:
    """Local path of the downloaded Filosofi archive."""
    return project_path("raw") / INCOME_ARCHIVE


def read_income(path: Path | None = None) -> pd.DataFrame:
    """Return one row per commune / arrondissement code with income indicators.

    Columns: ``code_geo``, ``niveau_vie_median``, ``nb_menages``, ``nb_uc``,
    ``revenu_menage_median`` (estimated median household income, EUR / year).
    Returns an empty frame when the archive is missing or the enrichment is
    disabled, so the pipeline still runs without it.
    """
    cfg = load_config().get("income", {})
    path = path or archive_path()
    columns = ["code_geo", *MEASURES.values(), "revenu_menage_median"]
    if not cfg.get("enabled", False) or not path.exists():
        logger.warning("Filosofi income data not available: enrichment skipped")
        return pd.DataFrame(columns=columns)

    with zipfile.ZipFile(path) as archive:
        data_name = next(n for n in archive.namelist() if n.endswith("_data.csv"))
        with archive.open(data_name) as handle:
            raw = pd.read_csv(
                handle,
                sep=";",
                dtype={"GEO": "string", "GEO_OBJECT": "string", "FILOSOFI_MEASURE": "string"},
                usecols=["GEO", "GEO_OBJECT", "FILOSOFI_MEASURE", "OBS_VALUE"],
            )

    raw = raw[raw["GEO_OBJECT"].isin(["COM", "ARM"]) & raw["FILOSOFI_MEASURE"].isin(MEASURES)]
    wide = (
        raw.pivot_table(index="GEO", columns="FILOSOFI_MEASURE", values="OBS_VALUE", aggfunc="first")
        .rename(columns=MEASURES)
        .rename_axis(index="code_geo", columns=None)
        .reset_index()
    )
    wide["revenu_menage_median"] = (
        wide["niveau_vie_median"] * wide["nb_uc"] / wide["nb_menages"]
    ).round(0)
    return wide[columns]
