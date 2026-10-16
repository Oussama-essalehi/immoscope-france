# Dictionnaire des données

## 1. Fichier nettoyé — `data/processed/ventes_clean.parquet`

Une ligne par vente d'un seul logement (534 309 lignes).

| Colonne | Type | Description |
|---|---|---|
| `id_mutation` | texte | Identifiant DVF de la mutation (non stable entre publications) |
| `date_mutation` | date | Date de signature de l'acte |
| `valeur_fonciere` | décimal | Prix total de la vente en € (pris une seule fois par mutation) |
| `code_commune` | texte (5) | Code INSEE de la commune (arrondissement pour Lyon : 69381 à 69389) |
| `nom_commune` | texte | Libellé de la commune |
| `code_departement` | texte | Code du département |
| `type_local` | texte | `Maison` ou `Appartement` |
| `surface_reelle_bati` | décimal | Surface réelle bâtie du logement (m²) |
| `nombre_pieces_principales` | entier | Nombre de pièces principales |
| `longitude`, `latitude` | décimal | Coordonnées WGS-84 de la parcelle du logement (1,5 % manquantes) |
| `surface_terrain` | décimal | Surface de terrain de la mutation (m², somme des natures de culture distinctes) |
| `prix_m2` | décimal | `valeur_fonciere / surface_reelle_bati` |
| `annee`, `mois`, `trimestre` | entier | Calendrier de la date de mutation |
| `annee_mois` | texte | `AAAA-MM` |
| `ville_principale` | texte | Libellé de la ville suivie (vide pour les autres communes) |
| `est_metropole` | booléen | Vrai pour Toulouse, Bordeaux, Montpellier, Nantes, Lyon |
| `tranche_prix`, `tranche_surface`, `tranche_pieces` | texte | Tranches définies dans `config.yaml` (`Non renseigné` si absent) |

## 2. Schéma en étoile — PostgreSQL (`dvf`) et `data/gold/*.csv`

Format des CSV : UTF-8, séparateur virgule, point décimal, dates ISO `AAAA-MM-JJ`, en-tête.

### `fact_ventes` (534 309 lignes)

| Colonne | Type SQL | Description |
|---|---|---|
| `id_mutation` | `TEXT` PK | Identifiant de la vente |
| `date_key` | `INTEGER` FK | → `dim_date.date_key` (AAAAMMJJ) |
| `commune_key` | `INTEGER` FK | → `dim_commune.commune_key` |
| `type_local_key` | `SMALLINT` FK | → `dim_type_local.type_local_key` |
| `profil_key` | `INTEGER` FK | → `dim_profil_bien.profil_key` |
| `valeur_fonciere` | `DOUBLE PRECISION` | Prix de vente (€) |
| `surface` | `DOUBLE PRECISION` | Surface réelle bâtie (m²) |
| `prix_m2` | `DOUBLE PRECISION` | Prix au m² (€) |
| `nb_pieces` | `SMALLINT` | Nombre de pièces principales |
| `surface_terrain` | `DOUBLE PRECISION` | Surface de terrain (m²) |
| `latitude`, `longitude` | `DOUBLE PRECISION` | Coordonnées de la parcelle |

### `dim_date` (1 826 lignes, du 01/01/2021 au 31/12/2025)

| Colonne | Description |
|---|---|
| `date_key` | Clé AAAAMMJJ |
| `date` | Date (colonne de la table de dates marquée dans Power BI) |
| `annee`, `semestre`, `trimestre`, `mois` | Calendrier |
| `mois_nom` | Nom du mois en français (trié par `mois`) |
| `annee_mois`, `annee_trimestre` | Libellés `2025-03`, `2025-T1` |
| `debut_mois` | Premier jour du mois |
| `jour_semaine` | 1 = lundi … 7 = dimanche |

### `dim_commune` (1 939 lignes)

| Colonne | Description |
|---|---|
| `commune_key` | Clé de substitution |
| `code_commune`, `nom_commune` | Code INSEE et libellé |
| `code_departement`, `nom_departement`, `departement` | Ex. `69`, `Rhône`, `69 - Rhône` |
| `ville_principale` | Ville suivie (Lyon regroupe ses 9 arrondissements) ou vide |
| `est_ville_principale`, `est_metropole` | Indicateurs booléens |
| `latitude`, `longitude` | Médiane des coordonnées des ventes de la commune (pour la carte) |
| `niveau_vie_median` | INSEE Filosofi 2021, niveau de vie médian (€ / an / unité de consommation) |
| `revenu_menage_median` | Estimation du revenu disponible médian d'un ménage (€ / an) |
| `revenu_menage_ville` | Même indicateur au niveau de la ville principale (Lyon : commune 69123) |

### `dim_type_local` (2 lignes)

`type_local_key` (1 = Appartement, 2 = Maison), `type_local`.

### `dim_profil_bien` (238 lignes)

| Colonne | Description |
|---|---|
| `profil_key` | Clé de substitution |
| `tranche_prix`, `tranche_prix_ordre` | `< 100 k€` … `≥ 750 k€` |
| `tranche_surface`, `tranche_surface_ordre` | `< 30 m²` … `≥ 150 m²` |
| `tranche_pieces`, `tranche_pieces_ordre` | `1 pièce` … `5 pièces et +`, `Non renseigné` (ordre 99) |

## 3. Vues SQL (`sql/02_views.sql`)

| Vue | Grain | Contenu |
|---|---|---|
| `v_ventes` | vente | Faits joints aux dimensions |
| `v_prix_departement_annee` | département × type × année | Volume, médianes (ligne « Ensemble » par `GROUPING SETS`) |
| `v_prix_commune_annee` | commune × type × année | Volume, médianes du prix au m² et de la surface |
| `v_evolution_annuelle_ville` | ville × type × année | Médianes, volume, variations sur un an (`LAG`) |
| `v_tendance_mensuelle_ville` | ville × mois | Volume, médiane, médiane glissante 3 mois (`LATERAL`), moyenne mobile, volume 12 mois glissants |
| `v_classement_villes` | ville | Prix première / dernière année, évolutions, rangs (`RANK`) |

## 4. Tables d'analyse (`reports/tables/`)

| Fichier | Contenu |
|---|---|
| `cleaning_report.csv`, `cleaning_exclusions.csv` | Comptages de chaque règle de nettoyage |
| `prix_departement.csv`, `prix_commune.csv` | Q1 — médianes par département / commune, type, année |
| `evolution_annuelle_ville.csv`, `tendance_mensuelle_ville.csv` | Q2 — tendances annuelles et mensuelles |
| `effet_hausse_taux.csv` | Q3 — volume vs prix, 2021 → 2023 → 2025 |
| `classement_villes.csv` | Q4 — rangs hausse / baisse / prix |
| `accessibilite_budget.csv` | Q5 — m² achetables pour 150 / 250 / 350 k€ |
| `accessibilite_revenu.csv` | Q6 — années de revenu (INSEE) |
| `tests_mann_whitney.csv` | Tests 2021 vs 2025 avec tailles d'effet et interprétation |
| `crosscheck_sql_python.csv` | Contrôle croisé des médianes SQL et Python |
| `summary.json` | Chiffres clés repris dans les constats |

## 5. Données du tableau de bord web (`web/public/data/`)

Agrégats produits par `src/export_web.py` (`python run.py export-web`). Les médianes ne
s'additionnent pas : chaque combinaison de filtres proposée par le site est calculée à
l'avance. Abréviations : `n` = ventes, `p` = prix médian au m², `v` = prix médian, `s` =
surface médiane ; `all` = toutes les valeurs du filtre.

| Fichier | Clés | Contenu |
|---|---|---|
| `meta.json` | – | Années, départements, villes suivies, bornes du simulateur |
| `overview.json` | `departement\|type` → mois ou année | Séries mensuelles et annuelles (vue d'ensemble) |
| `communes.json` | `type\|annee` → commune | Communes (code, nom, département, coordonnées) et statistiques des communes ayant au moins 30 ventes |
| `cities.json` | `ville\|type` → année ou trimestre | Statistiques des 15 villes suivies et revenu médian estimé des ménages |
