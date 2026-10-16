"""Clean the raw DVF files into one row per residential sale with a reliable price per m².

Pipeline (each step is logged with row / mutation counts in a cleaning report):

1. keep ``nature_mutation == "Vente"``;
2. keep mutations that contain at least one ``Maison`` or ``Appartement``;
3. aggregate to one row per ``id_mutation`` (the sale price is repeated on every
   row of a mutation and is never summed) and keep only mutations with exactly
   one distinct dwelling, outbuildings (``Dépendance``) and bare land allowed;
4. drop missing or zero price / built surface;
5. compute ``prix_m2``;
6. remove outliers (hard bounds, then 1st-99th percentile per department x type);
7. add derived columns (calendar, region, main city, bands);
8. write a Parquet file to ``data/processed/``.

The files are processed one department at a time (all years together) so that
memory stays bounded at national scale; the outlier percentiles are computed per
department and property type, so the result is the same as a single pass.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.geo import add_region, assign_cities, departments, select_main_cities
from src.income import read_income
from src.settings import load_config, project_path, setup_logging

logger = logging.getLogger("clean")

PROCESSED_FILE = "ventes_clean.parquet"
REPORT_FILE = "cleaning_report.csv"
EXCLUSIONS_FILE = "cleaning_exclusions.csv"
CITIES_FILE = "villes_suivies.csv"

RAW_DTYPES: dict[str, str] = {
    "id_mutation": "string",
    "date_mutation": "string",
    "nature_mutation": "string",
    "valeur_fonciere": "float64",
    "code_commune": "string",
    "nom_commune": "string",
    "code_departement": "string",
    "id_parcelle": "string",
    "lot1_numero": "string",
    "type_local": "string",
    "surface_reelle_bati": "float64",
    "nombre_pieces_principales": "float64",
    "code_nature_culture": "string",
    "surface_terrain": "float64",
    "longitude": "float64",
    "latitude": "float64",
}

# A dwelling can appear on several rows of the same mutation: DVF repeats the
# local once per land-use line (``nature_culture``) of its parcel. These columns
# identify one physical dwelling inside a mutation.
DWELLING_KEY = [
    "id_mutation",
    "id_parcelle",
    "lot1_numero",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
]
# One land-use line of a parcel (used to sum the land surface without duplicates).
LAND_KEY = ["id_mutation", "id_parcelle", "code_nature_culture", "surface_terrain"]


@dataclass
class StepStat:
    """Row and mutation counts before / after one cleaning step."""

    step: str
    description: str
    rows_before: int
    rows_after: int
    mutations_before: int
    mutations_after: int

    @property
    def rows_removed(self) -> int:
        return self.rows_before - self.rows_after


@dataclass
class CleaningReport:
    """Collects one :class:`StepStat` per step plus detailed exclusion reasons."""

    steps: list[StepStat] = field(default_factory=list)
    exclusions: dict[str, int] = field(default_factory=dict)

    def add(
        self, step: str, description: str, before: pd.DataFrame, after: pd.DataFrame
    ) -> None:
        stat = StepStat(
            step=step,
            description=description,
            rows_before=len(before),
            rows_after=len(after),
            mutations_before=before["id_mutation"].nunique(),
            mutations_after=after["id_mutation"].nunique(),
        )
        self.steps.append(stat)
        logger.debug(
            "%-28s rows %10s -> %10s | mutations %9s -> %9s",
            step,
            f"{stat.rows_before:,}",
            f"{stat.rows_after:,}",
            f"{stat.mutations_before:,}",
            f"{stat.mutations_after:,}",
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(s) for s in self.steps])

    def merge(self, other: "CleaningReport") -> None:
        """Add the counts of another report (e.g. another department) to this one."""
        if not self.steps:
            self.steps = [StepStat(**asdict(s)) for s in other.steps]
        else:
            for mine, theirs in zip(self.steps, other.steps):
                if mine.step != theirs.step:
                    raise ValueError(f"Cannot merge step {theirs.step} into {mine.step}")
                mine.rows_before += theirs.rows_before
                mine.rows_after += theirs.rows_after
                mine.mutations_before += theirs.mutations_before
                mine.mutations_after += theirs.mutations_after
        for reason, count in other.exclusions.items():
            self.exclusions[reason] = self.exclusions.get(reason, 0) + count


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_raw(paths: Iterable[Path]) -> pd.DataFrame:
    """Read the raw gzip CSV files, keeping only the columns used downstream."""
    frames = [
        pd.read_csv(path, usecols=list(RAW_DTYPES), dtype=RAW_DTYPES, low_memory=False)
        for path in paths
    ]
    if not frames:
        raise FileNotFoundError("No raw DVF file found: run the download step first.")
    df = pd.concat(frames, ignore_index=True)
    df["date_mutation"] = pd.to_datetime(df["date_mutation"], format="%Y-%m-%d")
    return df


# --------------------------------------------------------------------------- #
# Cleaning rules (pure functions, unit-tested)
# --------------------------------------------------------------------------- #
def filter_sales(df: pd.DataFrame, nature: str = "Vente") -> pd.DataFrame:
    """Rule 1 — keep standard sales only (excludes VEFA, exchanges, auctions...)."""
    return df[df["nature_mutation"] == nature].copy()


def filter_residential_mutations(
    df: pd.DataFrame, dwelling_types: Sequence[str]
) -> pd.DataFrame:
    """Rule 2 — keep every row of the mutations that include at least one dwelling."""
    has_dwelling = df["type_local"].isin(dwelling_types)
    ids = df.loc[has_dwelling, "id_mutation"].unique()
    return df[df["id_mutation"].isin(ids)].copy()


def aggregate_mutations(
    df: pd.DataFrame,
    dwelling_types: Sequence[str],
    allowed_annex_types: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rule 3 — collapse each mutation to one row and keep single-dwelling sales.

    ``valeur_fonciere`` is the total price of the mutation, repeated on each of
    its rows, so it is taken once per mutation and never summed. The land surface
    is summed over distinct (parcel, land-use) lines.

    Returns the one-row-per-mutation frame and the number of mutations excluded
    per reason.
    """
    dwellings = df[df["type_local"].isin(dwelling_types)].drop_duplicates(
        DWELLING_KEY
    )
    n_dwellings = dwellings.groupby("id_mutation").size()

    known_types = set(dwelling_types) | set(allowed_annex_types)
    other_locals = df["type_local"].notna() & ~df["type_local"].isin(known_types)
    mutations_with_other = set(df.loc[other_locals, "id_mutation"])

    multi = set(n_dwellings[n_dwellings > 1].index)
    other_only = mutations_with_other - multi
    exclusions = {
        "plusieurs_logements": len(multi),
        "local_commercial_ou_industriel": len(other_only),
    }
    keep_ids = set(n_dwellings.index) - multi - other_only

    single = dwellings[dwellings["id_mutation"].isin(keep_ids)]
    land = (
        df[df["id_mutation"].isin(keep_ids)]
        .dropna(subset=["surface_terrain"])
        .drop_duplicates(LAND_KEY)
        .groupby("id_mutation")["surface_terrain"]
        .sum()
    )
    out = single[
        [
            "id_mutation",
            "date_mutation",
            "valeur_fonciere",
            "code_commune",
            "nom_commune",
            "code_departement",
            "type_local",
            "surface_reelle_bati",
            "nombre_pieces_principales",
            "longitude",
            "latitude",
        ]
    ].set_index("id_mutation")
    out["surface_terrain"] = land.reindex(out.index).fillna(0.0)
    return out.reset_index(), exclusions


def drop_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 4 — drop sales with a missing or zero price or built surface."""
    valid = (
        df["valeur_fonciere"].fillna(0).gt(0)
        & df["surface_reelle_bati"].fillna(0).gt(0)
    )
    return df[valid].copy()


def add_price_per_m2(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 5 — ``prix_m2 = valeur_fonciere / surface_reelle_bati``."""
    out = df.copy()
    out["prix_m2"] = out["valeur_fonciere"] / out["surface_reelle_bati"]
    return out


def apply_hard_bounds(
    df: pd.DataFrame,
    min_surface: float,
    max_surface: float,
    min_price: float,
    max_price: float,
) -> pd.DataFrame:
    """Rule 6a — remove implausible surfaces and prices (bounds inclusive)."""
    keep = df["surface_reelle_bati"].between(min_surface, max_surface) & df[
        "valeur_fonciere"
    ].between(min_price, max_price)
    return df[keep].copy()


def filter_price_outliers(
    df: pd.DataFrame,
    quantiles: tuple[float, float] = (0.01, 0.99),
    groupby: Sequence[str] = ("code_departement", "type_local"),
) -> pd.DataFrame:
    """Rule 6b — keep ``prix_m2`` within the given quantiles of its group."""
    grouped = df.groupby(list(groupby))["prix_m2"]
    low = grouped.transform("quantile", quantiles[0])
    high = grouped.transform("quantile", quantiles[1])
    return df[df["prix_m2"].between(low, high)].copy()


def assign_band(values: pd.Series, edges: Sequence[float], labels: Sequence[str]) -> pd.Series:
    """Map numeric values to labels; ``edges`` are inclusive lower bounds.

    Values below the first edge (or missing) are labelled "Non renseigné".
    """
    if len(edges) != len(labels):
        raise ValueError("edges and labels must have the same length")
    idx = np.searchsorted(np.asarray(edges, dtype=float), values.to_numpy(dtype=float), side="right") - 1
    labelled = np.where(idx >= 0, np.asarray(labels, dtype=object)[idx.clip(min=0)], "Non renseigné")
    labelled = np.where(values.isna().to_numpy(), "Non renseigné", labelled)
    return pd.Series(labelled, index=values.index, dtype="string")


def add_derived_columns(df: pd.DataFrame, bands: dict) -> pd.DataFrame:
    """Rule 7 — calendar fields and price / surface / room bands.

    The region and the main city are added once every department is cleaned
    (see :func:`run`), because ranking the cities needs the whole scope.
    """
    out = df.copy()
    dates = out["date_mutation"]
    out["annee"] = dates.dt.year.astype("int16")
    out["mois"] = dates.dt.month.astype("int8")
    out["trimestre"] = dates.dt.quarter.astype("int8")
    out["annee_mois"] = dates.dt.strftime("%Y-%m").astype("string")
    out["tranche_prix"] = assign_band(out["valeur_fonciere"], **bands["price"])
    out["tranche_surface"] = assign_band(out["surface_reelle_bati"], **bands["surface"])
    out["tranche_pieces"] = assign_band(out["nombre_pieces_principales"], **bands["rooms"])
    return out


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def clean(raw: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, CleaningReport]:
    """Apply every cleaning rule to a raw DVF frame and return the clean sales."""
    rules = cfg["cleaning"]
    report = CleaningReport()

    sales = filter_sales(raw, rules["nature_mutation"])
    report.add("1_vente", "nature_mutation = 'Vente'", raw, sales)

    residential = filter_residential_mutations(sales, rules["dwelling_types"])
    report.add("2_logement", "Mutation contenant une Maison ou un Appartement", sales, residential)

    mutations, exclusions = aggregate_mutations(
        residential, rules["dwelling_types"], rules["allowed_annex_types"]
    )
    report.exclusions.update(exclusions)
    report.add("3_un_logement", "1 ligne par mutation, un seul logement", residential, mutations)

    complete = drop_missing_values(mutations)
    report.add("4_valeurs_manquantes", "Prix et surface renseignés et > 0", mutations, complete)

    priced = add_price_per_m2(complete)

    bounded = apply_hard_bounds(
        priced,
        rules["min_surface_m2"],
        rules["max_surface_m2"],
        rules["min_price_eur"],
        rules["max_price_eur"],
    )
    report.add("6a_bornes", "Bornes dures surface et prix", priced, bounded)

    filtered = filter_price_outliers(
        bounded, tuple(rules["outlier_quantiles"]), rules["outlier_groupby"]
    )
    report.add("6b_percentiles", "prix_m2 entre P1 et P99 (dép. x type)", bounded, filtered)

    enriched = add_derived_columns(filtered, cfg["bands"])
    return enriched, report


def run() -> Path:
    """Clean every raw file, department by department, then add region and cities."""
    cfg = load_config()
    raw_dir = project_path("raw")
    report = CleaningReport()
    frames: list[pd.DataFrame] = []
    for department in departments(cfg):
        paths = sorted(raw_dir.glob(f"dvf_*_{department}.csv.gz"))
        if not paths:
            logger.warning("No raw file for department %s: skipped", department)
            continue
        clean_dep, report_dep = clean(load_raw(paths), cfg)
        report.merge(report_dep)
        frames.append(clean_dep)
        logger.info("Department %-3s %9s raw rows -> %8s sales", department,
                    f"{report_dep.steps[0].rows_before:,}", f"{len(clean_dep):,}")

    clean_df = pd.concat(frames, ignore_index=True)
    clean_df = add_region(clean_df, cfg)
    cities = select_main_cities(clean_df, cfg, read_income())
    clean_df = assign_cities(clean_df, cities, cfg)
    clean_df = clean_df.sort_values(["date_mutation", "id_mutation"]).reset_index(drop=True)

    for stat in report.steps:
        logger.info("%-22s rows %11s -> %11s | mutations %10s -> %10s", stat.step,
                    f"{stat.rows_before:,}", f"{stat.rows_after:,}",
                    f"{stat.mutations_before:,}", f"{stat.mutations_after:,}")
    for reason, count in report.exclusions.items():
        logger.info("    excluded mutations (%s): %s", reason, f"{count:,}")

    target = project_path("processed") / PROCESSED_FILE
    clean_df.to_parquet(target, index=False)
    logger.info("Wrote %s (%s sales, %d main cities)", target, f"{len(clean_df):,}", len(cities))

    tables = project_path("tables")
    report.to_frame().to_csv(tables / REPORT_FILE, index=False)
    pd.Series(report.exclusions, name="mutations").rename_axis("motif").to_csv(
        tables / EXCLUSIONS_FILE
    )
    cities.to_csv(tables / CITIES_FILE, index=False)
    return target


if __name__ == "__main__":
    setup_logging()
    run()
