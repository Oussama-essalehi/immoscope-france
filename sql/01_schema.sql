-- =============================================================================
-- 01_schema.sql — Schéma en étoile des ventes immobilières DVF
-- Grain de la table de faits : une vente (id_mutation) d'un seul logement.
-- Le script est rejouable : il recrée le schéma à chaque chargement.
-- =============================================================================

DROP SCHEMA IF EXISTS dvf CASCADE;
CREATE SCHEMA dvf;
SET search_path TO dvf;

-- -----------------------------------------------------------------------------
-- Dimension calendrier (jour), couvre les années complètes du périmètre
-- -----------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key         INTEGER     PRIMARY KEY,          -- AAAAMMJJ
    date             DATE        NOT NULL UNIQUE,
    annee            SMALLINT    NOT NULL,
    semestre         SMALLINT    NOT NULL,
    trimestre        SMALLINT    NOT NULL,
    mois             SMALLINT    NOT NULL,
    mois_nom         TEXT        NOT NULL,
    annee_mois       CHAR(7)     NOT NULL,             -- 'AAAA-MM'
    annee_trimestre  CHAR(7)     NOT NULL,             -- 'AAAA-T1'
    debut_mois       DATE        NOT NULL,
    jour_semaine     SMALLINT    NOT NULL              -- 1 = lundi … 7 = dimanche
);

-- -----------------------------------------------------------------------------
-- Dimension commune (les arrondissements de Paris, Lyon et Marseille sont des
-- communes DVF ; code_ville les rattache à la commune entière)
-- -----------------------------------------------------------------------------
CREATE TABLE dim_commune (
    commune_key           INTEGER     PRIMARY KEY,
    code_commune          CHAR(5)     NOT NULL UNIQUE,
    nom_commune           TEXT        NOT NULL,
    code_departement      VARCHAR(3)  NOT NULL,
    nom_departement       TEXT        NOT NULL,
    departement           TEXT        NOT NULL,         -- '31 - Haute-Garonne'
    code_region           CHAR(2)     NOT NULL,
    region                TEXT        NOT NULL,
    code_ville            CHAR(5),                      -- commune entière (75056 pour Paris 1er)
    ville_principale      TEXT,                         -- NULL hors villes suivies
    est_ville_principale  BOOLEAN     NOT NULL,
    est_metropole         BOOLEAN     NOT NULL,
    latitude              DOUBLE PRECISION,             -- centre médian des ventes
    longitude             DOUBLE PRECISION,
    niveau_vie_median     DOUBLE PRECISION,             -- INSEE Filosofi, € / an / UC
    revenu_menage_median  DOUBLE PRECISION,             -- estimation € / an / ménage
    revenu_menage_ville   DOUBLE PRECISION              -- idem, au niveau de la ville principale
);

-- -----------------------------------------------------------------------------
-- Dimension type de bien
-- -----------------------------------------------------------------------------
CREATE TABLE dim_type_local (
    type_local_key  SMALLINT PRIMARY KEY,
    type_local      TEXT     NOT NULL UNIQUE
);

-- -----------------------------------------------------------------------------
-- Dimension « profil du bien » (dimension fourre-tout / junk dimension) :
-- une ligne par combinaison de tranches de prix, de surface et de pièces.
-- Évite de répéter trois libellés texte sur chaque vente et porte l'ordre de tri.
-- -----------------------------------------------------------------------------
CREATE TABLE dim_profil_bien (
    profil_key             INTEGER   PRIMARY KEY,
    tranche_prix           TEXT      NOT NULL,
    tranche_prix_ordre     SMALLINT  NOT NULL,
    tranche_surface        TEXT      NOT NULL,
    tranche_surface_ordre  SMALLINT  NOT NULL,
    tranche_pieces         TEXT      NOT NULL,
    tranche_pieces_ordre   SMALLINT  NOT NULL,
    UNIQUE (tranche_prix, tranche_surface, tranche_pieces)
);

-- -----------------------------------------------------------------------------
-- Table de faits
-- -----------------------------------------------------------------------------
CREATE TABLE fact_ventes (
    id_mutation      TEXT             PRIMARY KEY,
    date_key         INTEGER          NOT NULL REFERENCES dim_date (date_key),
    commune_key      INTEGER          NOT NULL REFERENCES dim_commune (commune_key),
    type_local_key   SMALLINT         NOT NULL REFERENCES dim_type_local (type_local_key),
    profil_key       INTEGER          NOT NULL REFERENCES dim_profil_bien (profil_key),
    valeur_fonciere  DOUBLE PRECISION NOT NULL CHECK (valeur_fonciere > 0),
    surface          DOUBLE PRECISION NOT NULL CHECK (surface > 0),
    prix_m2          DOUBLE PRECISION NOT NULL CHECK (prix_m2 > 0),
    nb_pieces        SMALLINT,
    surface_terrain  DOUBLE PRECISION,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION
);

CREATE INDEX ix_fact_ventes_date      ON fact_ventes (date_key);
CREATE INDEX ix_fact_ventes_commune   ON fact_ventes (commune_key);
CREATE INDEX ix_fact_ventes_type      ON fact_ventes (type_local_key);
CREATE INDEX ix_fact_ventes_profil    ON fact_ventes (profil_key);
CREATE INDEX ix_dim_commune_ville     ON dim_commune (ville_principale) WHERE ville_principale IS NOT NULL;
CREATE INDEX ix_dim_commune_region    ON dim_commune (code_region);

COMMENT ON TABLE  fact_ventes IS 'Une ligne par vente DVF d''un seul logement (maison ou appartement), après nettoyage';
COMMENT ON COLUMN fact_ventes.valeur_fonciere IS 'Prix total de la mutation (jamais additionné entre les lots)';
COMMENT ON COLUMN fact_ventes.prix_m2 IS 'valeur_fonciere / surface réelle bâtie';
COMMENT ON COLUMN dim_commune.revenu_menage_median IS 'Niveau de vie médian x UC moyennes par ménage (INSEE Filosofi 2021)';
