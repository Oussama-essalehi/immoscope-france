"""Unit tests for the DVF cleaning rules, on small synthetic mutations."""

from __future__ import annotations

import pandas as pd
import pytest

from src.clean import (
    CleaningReport,
    add_derived_columns,
    add_price_per_m2,
    aggregate_mutations,
    apply_hard_bounds,
    assign_band,
    clean,
    drop_missing_values,
    filter_price_outliers,
    filter_residential_mutations,
    filter_sales,
)

DWELLINGS = ["Maison", "Appartement"]
ANNEXES = ["Dépendance"]


def row(id_mutation: str, valeur: float, type_local: str | None, **kwargs) -> dict:
    """Build one raw DVF row with sensible defaults."""
    base = {
        "id_mutation": id_mutation,
        "date_mutation": pd.Timestamp("2023-05-10"),
        "nature_mutation": "Vente",
        "valeur_fonciere": valeur,
        "code_commune": "31555",
        "nom_commune": "Toulouse",
        "code_departement": "31",
        "id_parcelle": f"P-{id_mutation}",
        "lot1_numero": None,
        "type_local": type_local,
        "surface_reelle_bati": None,
        "nombre_pieces_principales": None,
        "code_nature_culture": None,
        "surface_terrain": None,
        "longitude": 1.44,
        "latitude": 43.60,
    }
    base.update(kwargs)
    return base


@pytest.fixture
def raw() -> pd.DataFrame:
    """Five mutations covering the multi-lot cases met in the real files."""
    return pd.DataFrame(
        [
            # M1: one apartment + cellar + parking, price repeated on 3 rows
            row("M1", 300_000, "Appartement", lot1_numero="12", surface_reelle_bati=60, nombre_pieces_principales=3),
            row("M1", 300_000, "Dépendance", lot1_numero="45"),
            row("M1", 300_000, "Dépendance", lot1_numero="46"),
            # M2: one house repeated on two land-use lines (sols + jardin) of its parcel
            row("M2", 400_000, "Maison", surface_reelle_bati=100, nombre_pieces_principales=5, code_nature_culture="S", surface_terrain=300),
            row("M2", 400_000, "Maison", surface_reelle_bati=100, nombre_pieces_principales=5, code_nature_culture="J", surface_terrain=500),
            row("M2", 400_000, "Dépendance", code_nature_culture="S", surface_terrain=300),
            # M3: two apartments sold together -> no reliable price per m²
            row("M3", 500_000, "Appartement", lot1_numero="1", surface_reelle_bati=40, nombre_pieces_principales=2),
            row("M3", 500_000, "Appartement", lot1_numero="2", surface_reelle_bati=50, nombre_pieces_principales=2),
            # M4: apartment + shop -> excluded
            row("M4", 350_000, "Appartement", lot1_numero="3", surface_reelle_bati=70, nombre_pieces_principales=3),
            row("M4", 350_000, "Local industriel. commercial ou assimilé", lot1_numero="4", surface_reelle_bati=30),
            # M5: not a standard sale
            row("M5", 250_000, "Appartement", nature_mutation="Echange", surface_reelle_bati=50, nombre_pieces_principales=2),
            # M6: land only
            row("M6", 80_000, None, code_nature_culture="T", surface_terrain=1000),
        ]
    )


def aggregate(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    sales = filter_residential_mutations(filter_sales(raw), DWELLINGS)
    return aggregate_mutations(sales, DWELLINGS, ANNEXES)


# --------------------------------------------------------------------------- #
# Rules 1-2
# --------------------------------------------------------------------------- #
def test_filter_sales_keeps_only_vente(raw: pd.DataFrame) -> None:
    out = filter_sales(raw)
    assert set(out["nature_mutation"]) == {"Vente"}
    assert "M5" not in set(out["id_mutation"])


def test_residential_filter_keeps_all_rows_of_dwelling_mutations(raw: pd.DataFrame) -> None:
    out = filter_residential_mutations(filter_sales(raw), DWELLINGS)
    assert "M6" not in set(out["id_mutation"])
    # the cellar and parking rows of M1 are kept for the aggregation step
    assert (out["id_mutation"] == "M1").sum() == 3


# --------------------------------------------------------------------------- #
# Rule 3 — multi-lot deduplication
# --------------------------------------------------------------------------- #
def test_one_row_per_mutation(raw: pd.DataFrame) -> None:
    out, _ = aggregate(raw)
    assert out["id_mutation"].is_unique
    assert set(out["id_mutation"]) == {"M1", "M2"}


def test_price_is_not_duplicated_across_lots(raw: pd.DataFrame) -> None:
    out, _ = aggregate(raw)
    prices = out.set_index("id_mutation")["valeur_fonciere"]
    # M1 has 3 rows and M2 has 3 rows: the price must stay the sale price
    assert prices["M1"] == 300_000
    assert prices["M2"] == 400_000


def test_dwelling_repeated_per_land_use_counts_once(raw: pd.DataFrame) -> None:
    out, exclusions = aggregate(raw)
    m2 = out.set_index("id_mutation").loc["M2"]
    assert m2["surface_reelle_bati"] == 100
    # land = 300 (sols) + 500 (jardin), the duplicated 300 m² line counted once
    assert m2["surface_terrain"] == 800
    assert exclusions["plusieurs_logements"] == 1  # only M3


def test_multi_dwelling_and_commercial_mutations_are_excluded(raw: pd.DataFrame) -> None:
    out, exclusions = aggregate(raw)
    assert "M3" not in set(out["id_mutation"])
    assert "M4" not in set(out["id_mutation"])
    assert exclusions == {"plusieurs_logements": 1, "local_commercial_ou_industriel": 1}


def test_house_and_apartment_in_same_mutation_is_multi_dwelling() -> None:
    raw = pd.DataFrame(
        [
            row("X", 500_000, "Maison", surface_reelle_bati=90, nombre_pieces_principales=4),
            row("X", 500_000, "Appartement", lot1_numero="1", surface_reelle_bati=40, nombre_pieces_principales=2),
        ]
    )
    out, exclusions = aggregate(raw)
    assert out.empty
    assert exclusions["plusieurs_logements"] == 1


# --------------------------------------------------------------------------- #
# Rules 4-5
# --------------------------------------------------------------------------- #
def test_drop_missing_or_zero_values() -> None:
    df = pd.DataFrame(
        {
            "valeur_fonciere": [100_000, 0, None, 150_000, 120_000],
            "surface_reelle_bati": [50, 40, 40, 0, None],
        }
    )
    assert len(drop_missing_values(df)) == 1


def test_price_per_m2_computation() -> None:
    df = pd.DataFrame({"valeur_fonciere": [300_000.0, 99_000.0], "surface_reelle_bati": [60.0, 33.0]})
    out = add_price_per_m2(df)
    assert out["prix_m2"].tolist() == pytest.approx([5_000.0, 3_000.0])


# --------------------------------------------------------------------------- #
# Rule 6 — outliers
# --------------------------------------------------------------------------- #
def test_hard_bounds() -> None:
    df = pd.DataFrame(
        {
            "valeur_fonciere": [5_000, 200_000, 200_000, 200_000],
            "surface_reelle_bati": [50, 8, 9, 1_500],
        }
    )
    out = apply_hard_bounds(df, min_surface=9, max_surface=1_000, min_price=10_000, max_price=20_000_000)
    assert out["surface_reelle_bati"].tolist() == [9]


def test_percentile_outliers_are_filtered_per_group() -> None:
    normal = list(range(3_000, 3_100))  # 100 plausible values
    df = pd.DataFrame(
        {
            "code_departement": ["31"] * 102 + ["69"] * 102,
            "type_local": ["Appartement"] * 204,
            "prix_m2": [10.0] + normal + [90_000.0] + [10.0] + [v + 2_000 for v in normal] + [90_000.0],
        }
    )
    out = filter_price_outliers(df, (0.01, 0.99), ["code_departement", "type_local"])
    assert out["prix_m2"].min() > 10
    assert out["prix_m2"].max() < 90_000
    # each group keeps its own range: 69 values are not cut by the 31 bounds
    assert out.loc[out["code_departement"] == "69", "prix_m2"].max() >= 5_000


# --------------------------------------------------------------------------- #
# Rule 7 — derived columns
# --------------------------------------------------------------------------- #
def test_assign_band_uses_inclusive_lower_bounds() -> None:
    values = pd.Series([0, 1, 2.5, 7, None])
    out = assign_band(values, edges=[1, 2, 5], labels=["1", "2-4", "5+"])
    assert out.tolist() == ["Non renseigné", "1", "2-4", "5+", "Non renseigné"]


def test_derived_columns() -> None:
    df = pd.DataFrame(
        {
            "date_mutation": pd.to_datetime(["2022-11-30"]),
            "code_commune": ["69383"],
            "valeur_fonciere": [250_000.0],
            "surface_reelle_bati": [55.0],
            "nombre_pieces_principales": [3.0],
        }
    )
    bands = {
        "price": {"edges": [0, 200_000], "labels": ["< 200 k€", "≥ 200 k€"]},
        "surface": {"edges": [0, 50], "labels": ["< 50", "≥ 50"]},
        "rooms": {"edges": [1, 3], "labels": ["1-2", "3+"]},
    }
    out = add_derived_columns(df, bands).iloc[0]
    assert (out["annee"], out["mois"], out["trimestre"], out["annee_mois"]) == (2022, 11, 4, "2022-11")
    assert (out["tranche_prix"], out["tranche_surface"], out["tranche_pieces"]) == ("≥ 200 k€", "≥ 50", "3+")


def test_reports_of_two_departments_are_summed(raw: pd.DataFrame) -> None:
    cfg = end_to_end_config()
    _, first = clean(raw, cfg)
    _, second = clean(raw.assign(id_mutation=raw["id_mutation"] + "-bis"), cfg)
    total = CleaningReport()
    total.merge(first)
    total.merge(second)
    assert total.steps[0].rows_before == 2 * len(raw)
    assert total.steps[-1].rows_after == 4
    assert total.exclusions["plusieurs_logements"] == 2


# --------------------------------------------------------------------------- #
# End to end on the synthetic frame
# --------------------------------------------------------------------------- #
def end_to_end_config() -> dict:
    return {
        "cleaning": {
            "nature_mutation": "Vente",
            "dwelling_types": DWELLINGS,
            "allowed_annex_types": ANNEXES,
            "min_surface_m2": 9,
            "max_surface_m2": 1_000,
            "min_price_eur": 10_000,
            "max_price_eur": 20_000_000,
            "outlier_quantiles": [0.0, 1.0],
            "outlier_groupby": ["code_departement", "type_local"],
        },
        "bands": {
            "price": {"edges": [0], "labels": ["tous"]},
            "surface": {"edges": [0], "labels": ["tous"]},
            "rooms": {"edges": [1], "labels": ["tous"]},
        },
    }


def test_clean_end_to_end(raw: pd.DataFrame) -> None:
    out, report = clean(raw, end_to_end_config())
    assert sorted(out["id_mutation"]) == ["M1", "M2"]
    assert out.set_index("id_mutation")["prix_m2"].to_dict() == pytest.approx({"M1": 5_000.0, "M2": 4_000.0})
    assert [s.step for s in report.steps][0] == "1_vente"
    assert report.steps[-1].rows_after == 2
