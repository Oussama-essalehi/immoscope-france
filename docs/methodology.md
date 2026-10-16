# Méthodologie

## 1. Source et périmètre

* **Données** : *Demandes de valeurs foncières géolocalisées* (DVF), produites par Etalab à
  partir des données de la DGFiP — [page du jeu de données](https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees).
* **Fichiers** : un CSV compressé par année et par département. URL vérifiée sur la ressource
  « Données au format CSV » du jeu de données :
  `https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{departement}.csv.gz`.
  Les années sont détectées automatiquement dans le répertoire `latest/csv/` (`years: auto`
  dans `config.yaml`).
* **Périmètre** : les **10 régions les plus peuplées** de France (Île-de-France,
  Auvergne-Rhône-Alpes, Nouvelle-Aquitaine, Occitanie, Hauts-de-France, Grand Est,
  Provence-Alpes-Côte d'Azur, Pays de la Loire, Bretagne, Normandie), soit **77 départements**
  (table région → départements dans `config.yaml`, section `scope.regions`) ; années
  **2021 à 2025**, toutes complètes (janvier à décembre). La Moselle, le Bas-Rhin et le
  Haut-Rhin ne sont pas publiés dans DVF (livre foncier) : le Grand Est est représenté par ses
  7 autres départements. Le téléchargement vérifie la liste publiée pour chaque année et
  signale tout département absent.
* **Villes suivies** : les **30 plus grandes villes** du périmètre, classées par population
  (INSEE Filosofi 2021, arrondissements de Paris, Lyon et Marseille regroupés), choisies
  automatiquement par `src/geo.py` (liste dans `reports/tables/villes_suivies.csv`). Les 5
  premières (Paris, Marseille, Lyon, Toulouse, Nice) sont mises en avant dans les graphiques.
* **Volume brut** : 385 fichiers (77 départements × 5 ans, 475 Mo compressés),
  17 979 120 lignes, 6 522 213 mutations. Les fichiers sont nettoyés département par
  département, puis réunis : un seul département n'a jamais à côtoyer les 76 autres en mémoire.
* **Enrichissement** : INSEE Filosofi 2021, base communale
  ([page INSEE](https://www.insee.fr/fr/statistiques/7756729)) — niveau de vie médian, nombre
  de ménages, d'unités de consommation et de personnes par commune et par arrondissement.

Le schéma réel a été inspecté avant tout traitement (40 colonnes). Les colonnes attendues
(`id_mutation`, `date_mutation`, `nature_mutation`, `valeur_fonciere`, `code_commune`,
`nom_commune`, `code_departement`, `type_local`, `surface_reelle_bati`,
`nombre_pieces_principales`, `surface_terrain`, `longitude`, `latitude`) sont toutes présentes.
Contrôles préalables : dans chaque fichier, chaque `id_mutation` n'a qu'une date
et **une seule valeur foncière** (vérifié sur les 6 522 213 mutations).

## 2. Le piège des mutations multi-lots

Une vente (`id_mutation`) s'étend sur plusieurs lignes : logement, cave, parking, terrain…
La `valeur_fonciere` est le **prix total de la vente, répété sur chaque ligne**. Additionner
les prix des lignes « logement » surestimerait le montant total des ventes d'un facteur
**4,61** sur l'année 2024 (847,6 Md€ au lieu de 183,7 Md€, calcul dans le notebook).

Deuxième piège, découvert à l'inspection des fichiers (non décrit dans la documentation) :
**un même logement est répété sur plusieurs lignes**, une par nature de culture de sa
parcelle (« sols », « jardins », « taillis »…). Exemple : la mutation `2024-333884` contient
une maison de 99 m² vendue 230 000 € sur deux lignes, plus six lignes de dépendances. Compter
les lignes « Maison » ferait croire à deux logements et exclurait à tort la vente.

Solution retenue :

1. une ligne par `id_mutation`, la valeur foncière prise **une seule fois** ;
2. les logements sont comptés **distinctement** sur la clé
   (`id_mutation`, `id_parcelle`, `lot1_numero`, `type_local`, `surface_reelle_bati`,
   `nombre_pieces_principales`) ;
3. la surface de terrain est la somme des lignes distinctes
   (`id_parcelle`, `code_nature_culture`, `surface_terrain`).

Sur 2024, 695 712 mutations contiennent un logement : 595 766 n'ont qu'une ligne « logement »,
mais **658 038** n'ont qu'un logement distinct. Le comptage naïf aurait exclu ~62 300 ventes
d'un seul logement cette année-là.

## 3. Règles de nettoyage (`src/clean.py`)

Chaque règle est une fonction pure testée dans `tests/test_clean.py`. Les seuils sont dans
`config.yaml` (section `cleaning`). Comptages issus de `reports/tables/cleaning_report.csv`.

| # | Règle | Lignes avant | Lignes après | Mutations avant | Mutations après |
|---|---|---:|---:|---:|---:|
| 1 | `nature_mutation = "Vente"` | 17 979 120 | 16 693 554 | 6 522 213 | 6 050 120 |
| 2 | mutation contenant au moins une Maison ou un Appartement | 16 693 554 | 11 905 010 | 6 050 120 | 4 247 245 |
| 3 | une ligne par mutation, exactement un logement | 11 905 010 | 3 932 677 | 4 247 245 | 3 932 677 |
| 4 | prix et surface renseignés et > 0 | 3 932 677 | 3 930 451 | 3 932 677 | 3 930 451 |
| 5 | `prix_m2 = valeur_fonciere / surface_reelle_bati` | – | – | – | – |
| 6a | bornes dures : 9 ≤ surface ≤ 1 000 m², 10 000 € ≤ prix ≤ 20 M€ | 3 930 451 | 3 910 077 | 3 930 451 | 3 910 077 |
| 6b | `prix_m2` entre P1 et P99 par département × type de bien | 3 910 077 | **3 831 945** | 3 910 077 | **3 831 945** |

Les comptages sont la somme des 77 rapports départementaux (les règles ne mélangent jamais
deux départements : les percentiles sont calculés par département).

Détail des règles :

1. **Ventes uniquement.** Exclut les ventes en l'état futur d'achèvement (VEFA, 975 516 lignes :
   logements neufs vendus sur plan, prix d'une autre nature), échanges (209 084), ventes de
   terrain à bâtir (47 400), adjudications (43 947) et expropriations (9 619).
2. **Logements.** On garde *toutes les lignes* des mutations qui contiennent au moins une maison
   ou un appartement : les dépendances et le terrain servent à l'étape 3.
3. **Un seul logement.** 235 634 mutations exclues car elles contiennent plusieurs logements
   (immeuble, lot de plusieurs appartements, maison + appartement) : le prix au m² d'un lot
   n'est pas calculable. 78 934 mutations exclues car elles contiennent un local commercial ou
   industriel (prix non attribuable au seul logement). Les dépendances (caves, parkings,
   garages) et le terrain nu sont tolérés.
4. **Valeurs manquantes.** 2 226 ventes sans prix ou sans surface bâtie.
5. **Prix au m²** calculé sur la surface réelle bâtie (la surface Carrez n'existe que pour les
   lots de copropriété).
6. **Valeurs aberrantes.** (a) bornes dures : surfaces inférieures à 9 m² (seuil légal d'un
   logement décent) ou supérieures à 1 000 m², prix inférieurs à 10 000 € (cessions
   symboliques, ventes entre proches) ; (b) percentiles 1 et 99 du prix au m², calculés
   **par département et par type de bien** pour ne pas couper les biens chers de Paris avec les
   seuils de la Creuse.
7. **Colonnes dérivées** : `annee`, `mois`, `trimestre`, `annee_mois`, tranches de prix, de
   surface et de pièces (bornes inférieures incluses, configurables), puis, une fois les
   départements réunis, `code_region` / `region`, `code_ville` (arrondissements de Paris, Lyon
   et Marseille regroupés), `ville_principale` (30 villes suivies) et `est_metropole`.
8. **Sortie** : `data/processed/ventes_clean.parquet` (3 831 945 ventes, 27 329 communes).

## 4. Modèle de données

Schéma en étoile chargé dans PostgreSQL 16 (`sql/01_schema.sql`) puis exporté en CSV pour
Power BI (`data/gold/`) :

* `fact_ventes` — grain : une vente d'un seul logement ;
* `dim_date` (calendrier journalier), `dim_commune`, `dim_type_local` ;
* `dim_profil_bien` — **dimension fourre-tout** (*junk dimension*) regroupant les trois tranches
  (prix, surface, pièces) : 277 combinaisons observées. Elle évite de répéter trois libellés
  texte sur 3,8 millions de lignes et porte l'ordre de tri des tranches.

`dim_commune` porte la région, le département et la ville de chaque commune (index sur la
région). Les faits sont chargés par `COPY` en blocs de 250 000 lignes. Même compacté,
`fact_ventes.csv` pèse environ 290 Mo, au-delà de la limite de 100 Mo par fichier de GitHub :
la couche `data/gold/` n'est donc pas versionnée et se régénère avec `python run.py export`.

## 5. Méthodes d'analyse

* **Médiane** plutôt que moyenne : la distribution du prix au m² est asymétrique (moyenne
  3 270 € contre médiane 2 653 € sur l'ensemble). En SQL, `PERCENTILE_CONT(0.5)`.
* **Prix courants** : les prix ne sont pas corrigés de l'inflation. Une stabilité nominale
  correspond donc à une baisse en termes réels.
* **Effet composition** : les évolutions « tous types » mélangent maisons et appartements ;
  les tables détaillées et les tests sont aussi fournis par type.
* **Hausse des taux** : 2021 (taux bas) est comparé à 2023 (taux au plus haut), puis à 2025.
* **Test statistique** : test U de Mann-Whitney bilatéral (non paramétrique, adapté à des
  distributions asymétriques) entre le prix au m² de la première (2021) et de la dernière année
  complète (2025), par ville et par type (90 tests : 30 villes × 3 types, au moins 30 ventes par groupe).
  Correction de Bonferroni : seuil 0,05 / 90 ≈ 0,00056. Taille d'effet : probabilité de supériorité
  *P*(vente 2025 > vente 2021) et corrélation rang-bisérielle *r* = 2*P* − 1 (|*r*| < 0,1
  négligeable, < 0,3 faible, < 0,5 moyen, sinon fort).
* **Régions** : les médianes régionales sont calculées sur les ventes de la région (et non
  comme moyenne des médianes départementales), en SQL par la vue `v_prix_region_annee`.
* **Accessibilité** : m² achetables = budget / prix médian au m² de la ville (dernière année),
  hors frais de notaire.
* **Taux d'effort** : années de revenu = prix médian d'un logement / revenu disponible médian
  estimé d'un ménage, avec revenu du ménage = niveau de vie médian × (unités de consommation /
  ménages) (INSEE Filosofi 2021). C'est une approximation (médiane par UC × UC moyennes par
  ménage) et le revenu date de 2021.

## 6. Contrôle croisé SQL ↔ Python

`src/crosscheck.py` compare la médiane du prix au m² calculée par PostgreSQL
(vue `v_evolution_annuelle_ville`, `PERCENTILE_CONT`) et par pandas sur le Parquet, pour
2 villes × 2 années × 3 types (villes réglables dans `config.yaml`, `analysis.crosscheck_cities`).
Paris et Lyon regroupent leurs arrondissements, ce qui teste aussi le rattachement des
communes aux villes. Résultat (`reports/tables/crosscheck_sql_python.csv`) :

| Ville | Année | Type | Ventes SQL | Ventes Python | Médiane SQL | Médiane Python | Écart |
|---|---|---|---:|---:|---:|---:|---:|
| Paris | 2021 | Ensemble | 30 618 | 30 618 | 10 869,57 € | 10 869,57 € | 0 |
| Paris | 2021 | Appartement | 30 447 | 30 447 | 10 860,00 € | 10 860,00 € | 0 |
| Paris | 2021 | Maison | 171 | 171 | 15 322,58 € | 15 322,58 € | 0 |
| Paris | 2025 | Ensemble | 28 453 | 28 453 | 9 714,29 € | 9 714,29 € | 0 |
| Paris | 2025 | Appartement | 28 306 | 28 306 | 9 705,88 € | 9 705,88 € | 0 |
| Paris | 2025 | Maison | 147 | 147 | 12 564,10 € | 12 564,10 € | 0 |
| Lyon | 2021 | Ensemble | 7 963 | 7 963 | 5 027,03 € | 5 027,03 € | 0 |
| Lyon | 2021 | Appartement | 7 746 | 7 746 | 5 000,00 € | 5 000,00 € | 0 |
| Lyon | 2021 | Maison | 217 | 217 | 6 295,19 € | 6 295,19 € | 0 |
| Lyon | 2025 | Ensemble | 6 758 | 6 758 | 4 468,09 € | 4 468,09 € | 0 |
| Lyon | 2025 | Appartement | 6 578 | 6 578 | 4 452,56 € | 4 452,56 € | 0 |
| Lyon | 2025 | Maison | 180 | 180 | 5 301,44 € | 5 301,44 € | 0 |

Les 12 comparaisons sont identiques au centime ; l'étape `check` du pipeline échoue si un écart
apparaît.

## 7. Limites

* DVF ne couvre pas l'Alsace-Moselle (Bas-Rhin, Haut-Rhin, Moselle : livre foncier) ni
  Mayotte : les chiffres du Grand Est portent sur 7 de ses 10 départements.
* Le périmètre couvre 10 des 13 régions métropolitaines : Centre-Val de Loire,
  Bourgogne-Franche-Comté et la Corse n'y figurent pas, l'outre-mer non plus.
* Le filtre « un seul logement » écarte les ventes en bloc (235 634 mutations) et le neuf
  (VEFA) : les résultats décrivent le marché de l'ancien à l'unité.
* Les prix sont des prix **déclarés** à l'acte, sans information sur l'état du bien, les
  travaux, l'étage, l'exposition ou le DPE.
* Les petites communes ont peu de ventes : le tableau de bord masque les médianes calculées sur
  moins de 30 ventes.
* L'identifiant `id_mutation` n'est pas stable d'une publication DVF à l'autre : il sert à
  regrouper les lignes, pas à suivre une vente dans le temps.
