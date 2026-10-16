# Dictionnaire des données

## 1. Fichier nettoyé — `data/processed/ventes_clean.parquet`

Une ligne par vente d'un seul logement (3 831 945 lignes, 27 329 communes, 77 départements).

| Colonne | Type | Description |
|---|---|---|
| `id_mutation` | texte | Identifiant DVF de la mutation (non stable entre publications) |
| `date_mutation` | date | Date de signature de l'acte |
| `valeur_fonciere` | décimal | Prix total de la vente en € (pris une seule fois par mutation) |
| `code_commune` | texte (5) | Code INSEE de la commune (arrondissement pour Paris 75101-75120, Lyon 69381-69389, Marseille 13201-13216) |
| `nom_commune` | texte | Libellé de la commune |
| `code_departement` | texte | Code du département |
| `type_local` | texte | `Maison` ou `Appartement` |
| `surface_reelle_bati` | décimal | Surface réelle bâtie du logement (m²) |
| `nombre_pieces_principales` | entier | Nombre de pièces principales |
| `longitude`, `latitude` | décimal | Coordonnées WGS-84 de la parcelle du logement (1,2 % manquantes) |
| `surface_terrain` | décimal | Surface de terrain de la mutation (m², somme des natures de culture distinctes) |
| `prix_m2` | décimal | `valeur_fonciere / surface_reelle_bati` |
| `annee`, `mois`, `trimestre` | entier | Calendrier de la date de mutation |
| `annee_mois` | texte | `AAAA-MM` |
| `tranche_prix`, `tranche_surface`, `tranche_pieces` | texte | Tranches définies dans `config.yaml` (`Non renseigné` si absent) |
| `code_region`, `region` | texte | Code INSEE et nom de la région (table de `config.yaml`, section `scope.regions`) |
| `code_ville` | texte (5) | Code INSEE de la ville, arrondissements regroupés (Paris 75056, Lyon 69123, Marseille 13055), sinon `code_commune` |
| `ville_principale` | texte | Libellé de la ville suivie (une des 30 plus grandes villes ; vide pour les autres communes) |
| `est_metropole` | booléen | Vrai pour les 5 plus grandes villes (Paris, Marseille, Lyon, Toulouse, Nice), mises en avant dans les graphiques |

## 2. Schéma en étoile — PostgreSQL (`dvf`) et `data/gold/*.csv`

Format des CSV : UTF-8, séparateur virgule, point décimal, dates ISO `AAAA-MM-JJ`, en-tête.
Les CSV ne sont pas versionnés (`fact_ventes.csv` pèse environ 290 Mo) : `python run.py export`
les régénère depuis PostgreSQL.

### `fact_ventes` (3 831 945 lignes)

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

### `dim_commune` (27 329 lignes)

| Colonne | Description |
|---|---|
| `commune_key` | Clé de substitution |
| `code_commune`, `nom_commune` | Code INSEE et libellé |
| `code_departement`, `nom_departement`, `departement` | Ex. `69`, `Rhône`, `69 - Rhône` |
| `code_region`, `region` | Ex. `84`, `Auvergne-Rhône-Alpes` |
| `code_ville` | Code INSEE de la ville (arrondissements de Paris, Lyon et Marseille regroupés) |
| `ville_principale` | Ville suivie (Paris, Lyon et Marseille regroupent leurs arrondissements) ou vide |
| `est_ville_principale`, `est_metropole` | Indicateurs booléens |
| `latitude`, `longitude` | Médiane des coordonnées des ventes de la commune (pour la carte) |
| `niveau_vie_median` | INSEE Filosofi 2021, niveau de vie médian (€ / an / unité de consommation) |
| `revenu_menage_median` | Estimation du revenu disponible médian d'un ménage (€ / an) |
| `revenu_menage_ville` | Même indicateur au niveau de la ville (`code_ville`), utilisé pour les 30 villes suivies |

### `dim_type_local` (2 lignes)

`type_local_key` (1 = Appartement, 2 = Maison), `type_local`.

### `dim_profil_bien` (277 lignes)

| Colonne | Description |
|---|---|
| `profil_key` | Clé de substitution |
| `tranche_prix`, `tranche_prix_ordre` | `< 100 k€` … `≥ 750 k€` |
| `tranche_surface`, `tranche_surface_ordre` | `< 30 m²` … `≥ 150 m²` |
| `tranche_pieces`, `tranche_pieces_ordre` | `1 pièce` … `5 pièces et +`, `Non renseigné` (ordre 99) |

## 3. Vues SQL (`sql/02_views.sql`)

| Vue | Grain | Contenu |
|---|---|---|
| `v_ventes` | vente | Faits joints aux dimensions (dont région et département) |
| `v_prix_region_annee` | région × type × année | Volume, médianes (ligne « Ensemble » par `GROUPING SETS`) |
| `v_prix_departement_annee` | département × type × année | Volume, médianes (ligne « Ensemble » par `GROUPING SETS`) |
| `v_prix_commune_annee` | commune × type × année | Volume, médianes du prix au m² et de la surface |
| `v_evolution_annuelle_ville` | ville × type × année | Médianes, volume, variations sur un an (`LAG`) |
| `v_tendance_mensuelle_ville` | ville × mois | Volume, médiane, médiane glissante 3 mois (`LATERAL`), moyenne mobile, volume 12 mois glissants |
| `v_classement_villes` | ville | Prix première / dernière année, évolutions, rangs (`RANK`) |

## 4. Tables d'analyse (`reports/tables/`)

| Fichier | Contenu |
|---|---|
| `cleaning_report.csv`, `cleaning_exclusions.csv` | Comptages de chaque règle de nettoyage |
| `prix_region.csv`, `prix_departement.csv`, `prix_commune.csv` | Q1 — médianes par région / département / commune (≥ 10 ventes), type, année (`all` = toutes années) |
| `villes_suivies.csv` | Les 30 villes suivies : rang, code INSEE, population (INSEE Filosofi 2021), ventes, département, indicateur des 5 plus grandes |
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
| `meta.json` | – | Années, régions et leurs départements, 30 villes suivies (rang, région), bornes du simulateur |
| `overview.json` | `zone\|type` → mois ou année | Séries mensuelles et annuelles ; zone = `all`, `R<code région>` ou code département |
| `departements.json` | `type\|annee` → département | Départements (code, nom, coordonnées) et leurs statistiques (carte nationale) |
| `communes_R<code>.json` | `type\|annee` → commune | Un fichier par région, chargé à la demande : communes (code, nom, département, coordonnées) et statistiques des communes ayant au moins 30 ventes |
| `communes_top.json` | `type\|annee` | Les 10 communes les plus et les moins chères du périmètre (≥ 30 ventes) |
| `cities.json` | `ville\|type` → année ou trimestre | Statistiques des 30 villes suivies et revenu médian estimé des ménages |
