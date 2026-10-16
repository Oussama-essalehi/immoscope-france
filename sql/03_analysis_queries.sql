-- =============================================================================
-- 03_analysis_queries.sql — Réponses SQL aux questions métier
-- Prérequis : 01_schema.sql et 02_views.sql exécutés, données chargées
-- (python run.py load). Exécution : psql -f sql/03_analysis_queries.sql
-- =============================================================================
SET search_path TO dvf;

-- -----------------------------------------------------------------------------
-- Q1a. Quel est le prix médian au m² par département et type de bien,
--      sur la dernière année disponible ?
-- -----------------------------------------------------------------------------
SELECT
    departement,
    type_local,
    nb_ventes,
    ROUND(prix_m2_median::NUMERIC)  AS prix_m2_median,
    ROUND(prix_median::NUMERIC)     AS prix_median
FROM v_prix_departement_annee
WHERE annee = (SELECT MAX(annee) FROM dim_date)
ORDER BY departement, type_local;

-- -----------------------------------------------------------------------------
-- Q1b. Quelles communes sont les plus chères et les moins chères au m²
--      (dernière année, communes avec au moins 50 ventes) ?
-- -----------------------------------------------------------------------------
WITH derniere_annee AS (
    SELECT code_commune, nom_commune, departement, nb_ventes, prix_m2_median
    FROM v_prix_commune_annee
    WHERE type_local = 'Ensemble'
      AND annee = (SELECT MAX(annee) FROM dim_date)
      AND nb_ventes >= 50
),
classees AS (
    SELECT
        d.*,
        RANK() OVER (ORDER BY prix_m2_median DESC) AS rang_plus_chere,
        RANK() OVER (ORDER BY prix_m2_median ASC)  AS rang_moins_chere
    FROM derniere_annee d
)
SELECT
    CASE WHEN rang_plus_chere <= 10 THEN 'Top 10 plus chères' ELSE 'Top 10 moins chères' END AS groupe,
    nom_commune,
    departement,
    nb_ventes,
    ROUND(prix_m2_median::NUMERIC) AS prix_m2_median
FROM classees
WHERE rang_plus_chere <= 10 OR rang_moins_chere <= 10
ORDER BY prix_m2_median DESC;

-- -----------------------------------------------------------------------------
-- Q1c. Prix médian au m² par commune et type de bien, toutes années confondues
--      (communes avec au moins 100 ventes du type)
-- -----------------------------------------------------------------------------
SELECT
    nom_commune,
    departement,
    type_local,
    COUNT(*)                                                         AS nb_ventes,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2)::NUMERIC) AS prix_m2_median
FROM v_ventes
GROUP BY nom_commune, departement, type_local
HAVING COUNT(*) >= 100
ORDER BY departement, prix_m2_median DESC;

-- -----------------------------------------------------------------------------
-- Q2a. Comment évoluent le prix médian au m² et le volume de ventes par année,
--      dans chaque département ?
-- -----------------------------------------------------------------------------
SELECT
    departement,
    annee,
    nb_ventes,
    ROUND(prix_m2_median::NUMERIC)                                        AS prix_m2_median,
    ROUND((100 * (prix_m2_median / LAG(prix_m2_median) OVER w - 1))::NUMERIC, 1) AS evol_prix_pct,
    ROUND(100 * (nb_ventes::NUMERIC / LAG(nb_ventes) OVER w - 1), 1)      AS evol_volume_pct
FROM v_prix_departement_annee
WHERE type_local = 'Ensemble'
WINDOW w AS (PARTITION BY departement ORDER BY annee)
ORDER BY departement, annee;

-- -----------------------------------------------------------------------------
-- Q2b. Tendance mensuelle par ville principale : volume, médiane du mois et
--      médiane glissante sur 3 mois
-- -----------------------------------------------------------------------------
SELECT
    ville_principale,
    debut_mois,
    nb_ventes,
    ROUND(prix_m2_median::NUMERIC)     AS prix_m2_median,
    ROUND(prix_m2_median_3m::NUMERIC)  AS prix_m2_median_3m,
    nb_ventes_12m_glissants
FROM v_tendance_mensuelle_ville
ORDER BY ville_principale, debut_mois;

-- -----------------------------------------------------------------------------
-- Q3. La hausse des taux (2022-2023) a-t-elle freiné le marché ?
--     Par ville : variation du volume vs variation du prix entre l'année de
--     référence (2021, taux bas) et 2023 (taux au plus haut), puis 2025.
--     Un ratio volume/prix fortement négatif = ajustement par les quantités.
-- -----------------------------------------------------------------------------
WITH params AS (
    SELECT 2021 AS annee_avant, 2023 AS annee_apres, (SELECT MAX(annee) FROM dim_date) AS annee_fin
),
annuel AS (
    SELECT ville_principale, annee, nb_ventes, prix_m2_median
    FROM v_evolution_annuelle_ville
    WHERE type_local = 'Ensemble'
)
SELECT
    a.ville_principale,
    a.nb_ventes                                                         AS ventes_2021,
    b.nb_ventes                                                         AS ventes_2023,
    ROUND(100 * (b.nb_ventes::NUMERIC / a.nb_ventes - 1), 1)            AS evol_volume_2021_2023_pct,
    ROUND((100 * (b.prix_m2_median / a.prix_m2_median - 1))::NUMERIC, 1) AS evol_prix_2021_2023_pct,
    ROUND(100 * (f.nb_ventes::NUMERIC / a.nb_ventes - 1), 1)            AS evol_volume_2021_fin_pct,
    ROUND((100 * (f.prix_m2_median / a.prix_m2_median - 1))::NUMERIC, 1) AS evol_prix_2021_fin_pct
FROM params p
JOIN annuel a ON a.annee = p.annee_avant
JOIN annuel b ON b.annee = p.annee_apres AND b.ville_principale = a.ville_principale
JOIN annuel f ON f.annee = p.annee_fin   AND f.ville_principale = a.ville_principale
ORDER BY evol_volume_2021_2023_pct;

-- -----------------------------------------------------------------------------
-- Q4. Classement des villes principales : plus forte hausse, plus forte
--     baisse (première -> dernière année) et prix au m² le plus bas
-- -----------------------------------------------------------------------------
SELECT
    ville_principale,
    ROUND(prix_m2_premiere_annee::NUMERIC)  AS prix_m2_premiere_annee,
    ROUND(prix_m2_derniere_annee::NUMERIC)  AS prix_m2_derniere_annee,
    ROUND(evol_prix_pct::NUMERIC, 1)        AS evol_prix_pct,
    ROUND(evol_volume_pct, 1)               AS evol_volume_pct,
    rang_plus_forte_hausse,
    rang_plus_forte_baisse,
    rang_moins_cher
FROM v_classement_villes
ORDER BY rang_plus_forte_hausse;

-- -----------------------------------------------------------------------------
-- Q5. Combien de m² achète-t-on avec 150 k€, 250 k€ ou 350 k€ dans chaque
--     ville principale (prix médian au m² de la dernière année, par type) ?
-- -----------------------------------------------------------------------------
WITH budgets (budget) AS (
    VALUES (150000), (250000), (350000)
),
prix AS (
    SELECT ville_principale, type_local, prix_m2_median
    FROM v_evolution_annuelle_ville
    WHERE annee = (SELECT MAX(annee) FROM dim_date)
)
SELECT
    p.ville_principale,
    p.type_local,
    ROUND(p.prix_m2_median::NUMERIC)                                     AS prix_m2_median,
    b.budget,
    ROUND((b.budget / p.prix_m2_median)::NUMERIC, 1)                     AS m2_achetables
FROM prix p
CROSS JOIN budgets b
ORDER BY p.type_local, b.budget, m2_achetables DESC;

-- -----------------------------------------------------------------------------
-- Q6. (Enrichissement INSEE Filosofi 2021) Combien d'années de revenu médian
--     d'un ménage faut-il pour acheter le logement médian de la ville
--     (dernière année) ?
-- -----------------------------------------------------------------------------
WITH revenu_ville AS (
    SELECT ville_principale, MAX(revenu_menage_ville) AS revenu_menage_median
    FROM dim_commune
    WHERE est_ville_principale
    GROUP BY ville_principale
),
prix AS (
    SELECT ville_principale, prix_median, prix_m2_median
    FROM v_evolution_annuelle_ville
    WHERE type_local = 'Ensemble'
      AND annee = (SELECT MAX(annee) FROM dim_date)
)
SELECT
    p.ville_principale,
    ROUND(p.prix_median::NUMERIC)                                  AS prix_median_logement,
    r.revenu_menage_median,
    ROUND((p.prix_median / r.revenu_menage_median)::NUMERIC, 1)   AS annees_de_revenu,
    RANK() OVER (ORDER BY p.prix_median / r.revenu_menage_median)  AS rang_accessibilite
FROM prix p
JOIN revenu_ville r USING (ville_principale)
ORDER BY annees_de_revenu;
