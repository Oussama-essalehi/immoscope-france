-- =============================================================================
-- 02_views.sql — Vues analytiques sur le schéma en étoile
-- Médianes : PERCENTILE_CONT(0.5) (la moyenne est trop sensible aux biens
-- atypiques). Les vues sont recréées à chaque chargement.
-- =============================================================================
SET search_path TO dvf;

-- -----------------------------------------------------------------------------
-- v_ventes : table de faits dénormalisée (point d'entrée des requêtes ad hoc)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ventes AS
SELECT
    f.id_mutation,
    d.date,
    d.annee,
    d.trimestre,
    d.mois,
    d.annee_mois,
    d.debut_mois,
    c.code_commune,
    c.nom_commune,
    c.code_departement,
    c.departement,
    c.ville_principale,
    c.est_metropole,
    t.type_local,
    f.valeur_fonciere,
    f.surface,
    f.prix_m2,
    f.nb_pieces,
    f.surface_terrain,
    p.tranche_prix,
    p.tranche_surface,
    p.tranche_pieces
FROM fact_ventes      f
JOIN dim_date         d USING (date_key)
JOIN dim_commune      c USING (commune_key)
JOIN dim_type_local   t USING (type_local_key)
JOIN dim_profil_bien  p USING (profil_key);

-- -----------------------------------------------------------------------------
-- v_prix_departement_annee : médianes par département, type et année
-- (GROUPING SETS ajoute la ligne « Ensemble » tous types confondus)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_prix_departement_annee AS
SELECT
    departement,
    COALESCE(type_local, 'Ensemble')                              AS type_local,
    annee,
    COUNT(*)                                                      AS nb_ventes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2)          AS prix_m2_median,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valeur_fonciere)  AS prix_median
FROM v_ventes
GROUP BY GROUPING SETS ((departement, type_local, annee), (departement, annee));

-- -----------------------------------------------------------------------------
-- v_prix_commune_annee : médianes par commune, type et année
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_prix_commune_annee AS
SELECT
    code_commune,
    nom_commune,
    departement,
    ville_principale,
    COALESCE(type_local, 'Ensemble')                              AS type_local,
    annee,
    COUNT(*)                                                      AS nb_ventes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2)          AS prix_m2_median,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface)          AS surface_mediane
FROM v_ventes
GROUP BY GROUPING SETS (
    (code_commune, nom_commune, departement, ville_principale, type_local, annee),
    (code_commune, nom_commune, departement, ville_principale, annee)
);

-- -----------------------------------------------------------------------------
-- v_evolution_annuelle_ville : prix et volume annuels des villes suivies,
-- variation sur un an avec LAG
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_evolution_annuelle_ville AS
WITH annuel AS (
    SELECT
        ville_principale,
        COALESCE(type_local, 'Ensemble')                              AS type_local,
        annee,
        COUNT(*)                                                      AS nb_ventes,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2)          AS prix_m2_median,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valeur_fonciere)  AS prix_median,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface)          AS surface_mediane
    FROM v_ventes
    WHERE ville_principale IS NOT NULL
    GROUP BY GROUPING SETS ((ville_principale, type_local, annee), (ville_principale, annee))
)
SELECT
    a.*,
    LAG(prix_m2_median) OVER w                                        AS prix_m2_median_n1,
    ROUND((100 * (prix_m2_median / LAG(prix_m2_median) OVER w - 1))::NUMERIC, 1)
                                                                      AS evol_prix_m2_pct,
    LAG(nb_ventes) OVER w                                             AS nb_ventes_n1,
    ROUND((100 * (nb_ventes::NUMERIC / LAG(nb_ventes) OVER w - 1)), 1)
                                                                      AS evol_volume_pct
FROM annuel a
WINDOW w AS (PARTITION BY ville_principale, type_local ORDER BY annee);

-- -----------------------------------------------------------------------------
-- v_tendance_mensuelle_ville : volume et prix médian mensuels par ville,
-- avec médiane glissante sur 3 mois.
-- PERCENTILE_CONT n'existe pas en fonction de fenêtre : la médiane glissante
-- est recalculée sur les ventes brutes des 3 derniers mois (LATERAL). La
-- moyenne mobile des médianes mensuelles (fenêtre ROWS) est donnée en
-- comparaison.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tendance_mensuelle_ville AS
WITH mensuel AS (
    SELECT
        ville_principale,
        debut_mois,
        COUNT(*)                                                  AS nb_ventes,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2)      AS prix_m2_median
    FROM v_ventes
    WHERE ville_principale IS NOT NULL
    GROUP BY ville_principale, debut_mois
)
SELECT
    m.ville_principale,
    m.debut_mois,
    m.nb_ventes,
    m.prix_m2_median,
    g.prix_m2_median_3m,
    AVG(m.prix_m2_median) OVER (
        PARTITION BY m.ville_principale ORDER BY m.debut_mois
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    )                                                             AS moyenne_mobile_medianes_3m,
    SUM(m.nb_ventes) OVER (
        PARTITION BY m.ville_principale ORDER BY m.debut_mois
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    )                                                             AS nb_ventes_12m_glissants
FROM mensuel m
CROSS JOIN LATERAL (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.prix_m2) AS prix_m2_median_3m
    FROM v_ventes v
    WHERE v.ville_principale = m.ville_principale
      AND v.debut_mois BETWEEN (m.debut_mois - INTERVAL '2 months')::DATE AND m.debut_mois
) g;

-- -----------------------------------------------------------------------------
-- v_classement_villes : rang des villes suivies sur la dernière année
-- (prix au m² et évolution depuis la première année du périmètre)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_classement_villes AS
WITH bornes AS (
    SELECT MIN(annee) AS premiere_annee, MAX(annee) AS derniere_annee FROM dim_date
),
prix AS (
    SELECT e.ville_principale, e.annee, e.prix_m2_median, e.nb_ventes
    FROM v_evolution_annuelle_ville e
    WHERE e.type_local = 'Ensemble'
),
comparaison AS (
    SELECT
        p_fin.ville_principale,
        p_deb.prix_m2_median                                       AS prix_m2_premiere_annee,
        p_fin.prix_m2_median                                       AS prix_m2_derniere_annee,
        p_fin.nb_ventes                                            AS nb_ventes_derniere_annee,
        100 * (p_fin.prix_m2_median / p_deb.prix_m2_median - 1)    AS evol_prix_pct,
        100 * (p_fin.nb_ventes::NUMERIC / p_deb.nb_ventes - 1)     AS evol_volume_pct
    FROM bornes b
    JOIN prix p_deb ON p_deb.annee = b.premiere_annee
    JOIN prix p_fin ON p_fin.annee = b.derniere_annee
                   AND p_fin.ville_principale = p_deb.ville_principale
)
SELECT
    c.*,
    RANK() OVER (ORDER BY prix_m2_derniere_annee ASC)  AS rang_moins_cher,
    RANK() OVER (ORDER BY evol_prix_pct DESC)          AS rang_plus_forte_hausse,
    RANK() OVER (ORDER BY evol_prix_pct ASC)           AS rang_plus_forte_baisse
FROM comparaison c;
