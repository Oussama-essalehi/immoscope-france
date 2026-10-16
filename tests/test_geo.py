"""Unit tests for the geography helpers (regions, arrondissements, main cities)."""

from __future__ import annotations

import pandas as pd

from src.geo import add_region, assign_cities, city_code, departments, select_main_cities

ARR = {"751": "75056", "6938": "69123", "132": "13055"}

CFG = {
    "scope": {
        "regions": {
            "11": {"name": "Île-de-France", "departments": {"75": "Paris", "92": "Hauts-de-Seine"}},
            "84": {"name": "Auvergne-Rhône-Alpes", "departments": {"69": "Rhône"}},
        }
    },
    "main_cities": {"top_n": 2, "highlight_n": 1, "arrondissements": ARR, "labels": {"75056": "Paris", "69123": "Lyon"}},
}


def sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code_commune": ["75101", "75120", "69381", "69266", "92012", "92012", "92012"],
            "nom_commune": ["Paris 1er Arrondissement", "Paris 20e Arrondissement", "Lyon 1er Arrondissement",
                            "Villeurbanne", "Boulogne-Billancourt", "Boulogne-Billancourt", "Boulogne-Billancourt"],
            "code_departement": ["75", "75", "69", "69", "92", "92", "92"],
        }
    )


def test_departments_and_regions() -> None:
    assert departments(CFG) == ["75", "92", "69"]
    out = add_region(sales(), CFG)
    assert out.loc[0, "region"] == "Île-de-France"
    assert out.loc[2, "code_region"] == "84"


def test_arrondissements_map_to_the_whole_city() -> None:
    assert city_code("75112", ARR) == "75056"
    assert city_code("69389", ARR) == "69123"
    assert city_code("13208", ARR) == "13055"
    assert city_code("13001", ARR) == "13001"  # Aix-en-Provence is not a Marseille arrondissement
    assert city_code("31555", ARR) == "31555"


def test_main_cities_ranked_by_population() -> None:
    income = pd.DataFrame({"code_geo": ["75056", "69123", "69266", "92012"], "population": [2.1e6, 5.2e5, 1.5e5, 1.2e5]})
    cities = select_main_cities(sales(), CFG, income)
    assert cities["ville"].tolist() == ["Paris", "Lyon"]
    assert cities["est_metropole"].tolist() == [True, False]
    assert cities.loc[0, "nb_ventes"] == 2  # both Paris arrondissements counted


def test_main_cities_fall_back_to_sales_count() -> None:
    cities = select_main_cities(sales(), CFG, pd.DataFrame())
    assert cities.loc[0, "ville"] == "Boulogne-Billancourt"  # 3 sales


def test_assign_cities() -> None:
    income = pd.DataFrame({"code_geo": ["75056", "69123"], "population": [2.1e6, 5.2e5]})
    cities = select_main_cities(sales(), CFG, income)
    out = assign_cities(sales(), cities, CFG)
    assert out["ville_principale"].tolist()[:3] == ["Paris", "Paris", "Lyon"]
    assert pd.isna(out.loc[3, "ville_principale"])  # Villeurbanne is not in the top 2
    assert out.loc[0, "code_ville"] == "75056"
    assert bool(out.loc[0, "est_metropole"]) and not bool(out.loc[2, "est_metropole"])
    assert pd.isna(out.loc[4, "ville_principale"])
