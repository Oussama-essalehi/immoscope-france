# Guide de construction du tableau de bord Power BI

Ce guide permet d'ouvrir le projet `DVF_Analyse.pbip`, de le connecter aux données et, si un
visuel ne s'affiche pas correctement, de le **reconstruire à la main**, page par page et visuel
par visuel.

Le projet est un **Power BI Project (.pbip)** :

| Dossier | Contenu | Format |
|---|---|---|
| `DVF_Analyse.SemanticModel/` | modèle sémantique : tables, relations, mesures DAX, paramètre `DataFolder` | TMDL |
| `DVF_Analyse.Report/` | rapport : 4 pages, visuels, filtres, thème | PBIR |
| `theme.json` | thème personnalisé (copie importable à la main) | JSON de thème Power BI |

Les fichiers ont été vérifiés hors de Power BI Desktop : schémas JSON publiés par Microsoft
(`python run.py validate-pbi`), validateur officiel `powerbi-report-author validate`
(0 erreur, 0 avertissement) et lecture du TMDL par la bibliothèque Microsoft Analysis Services
(TOM). Le rendu réel doit cependant être contrôlé dans Desktop (voir § 4).

---

## 1. Prérequis

1. **Power BI Desktop** récent (Windows), à jour.
2. Si Desktop le demande : *Fichier > Options et paramètres > Options > Fonctionnalités en
   préversion* — cocher **Enregistrement en projet Power BI (.pbip)**, **Stocker le modèle
   sémantique au format TMDL** et **Stocker les rapports au format PBIR**, puis redémarrer.
   (Dans les versions où ces formats sont devenus le standard, ces options n'apparaissent plus.)
3. **Visuel Azure Maps** autorisé : *Options > Sécurité > Visuels de carte et de carte remplie*
   (cocher l'utilisation des visuels de carte). Dans un compte d'organisation, l'administrateur
   doit aussi autoriser Azure Maps dans le portail d'administration.
4. Les fichiers CSV de `data/gold/` présents. Ils ne sont **pas versionnés** (`fact_ventes.csv`
   pèse environ 290 Mo, au-delà de la limite de GitHub) : les générer avec `python run.py all`
   (Docker requis pour PostgreSQL, compter 20 à 30 minutes dont le téléchargement).

## 2. Ouvrir le projet et définir `DataFolder`

1. Double-cliquer sur `powerbi/DVF_Analyse.pbip`.
2. Les visuels sont vides au premier lancement : le modèle ne contient pas encore de données.
3. *Accueil > Transformer les données (flèche) > Modifier les paramètres*.
4. Renseigner **DataFolder** avec le chemin **absolu** du dossier `data\gold\` du dépôt,
   **terminé par une barre oblique inverse**, par exemple :
   `C:\Users\Oussama\dev\dvf-immobilier-analyse\data\gold\`
5. Valider, puis cliquer sur **Appliquer les modifications** / **Actualiser**.
6. Enregistrer (`Ctrl+S`) : le projet reste au format .pbip.

> Le paramètre n'est défini qu'une fois : les 5 requêtes (`dim_date`, `dim_commune`,
> `dim_type_local`, `dim_profil_bien`, `fact_ventes`) construisent leur chemin avec
> `DataFolder & "<table>.csv"`.

En cas d'erreur « Formula.Firewall » : *Fichier > Options > Confidentialité* (fichier actif)
> *Ignorer les niveaux de confidentialité*, puis actualiser.

## 3. Le modèle sémantique

### Tables

| Table | Lignes | Rôle |
|---|---|---|
| `fact_ventes` | 3 831 945 | une vente d'un seul logement |
| `dim_date` | 1 826 | calendrier 2021-2025, **marquée comme table de dates** (colonne `date`) |
| `dim_commune` | 27 329 | communes (arrondissements de Paris, Lyon et Marseille inclus), département, région, ville principale, revenus INSEE |
| `dim_type_local` | 2 | Appartement / Maison |
| `dim_profil_bien` | 277 | tranches de prix, de surface et de pièces (triées par colonnes `*_ordre`) |
| `Paramètre Budget` | 41 | paramètre de simulation (100 000 € à 500 000 €, pas de 10 000 €) |
| `_Mesures` | – | toutes les mesures DAX, rangées par dossier d'affichage |

### Relations (plusieurs-à-un, filtrage dans un seul sens)

| De | Vers |
|---|---|
| `fact_ventes[date_key]` | `dim_date[date_key]` |
| `fact_ventes[commune_key]` | `dim_commune[commune_key]` |
| `fact_ventes[type_local_key]` | `dim_type_local[type_local_key]` |
| `fact_ventes[profil_key]` | `dim_profil_bien[profil_key]` |

Pour les recréer à la main : vue *Modèle*, glisser la clé de `fact_ventes` sur la clé de la
dimension, cardinalité *Plusieurs à un (\*:1)*, direction *Unique*. Puis clic droit sur
`dim_date` > *Marquer comme table de dates* > colonne `date`.

### Mesures (`_Mesures`)

| Dossier | Mesure | Format | Définition |
|---|---|---|---|
| 1. Volume | Nb Ventes | `#,0` | `COUNTROWS ( fact_ventes )` |
| 1. Volume | Nb Ventes N-1 | `#,0` | même période un an plus tôt (voir DAX ci-dessous) |
| 1. Volume | Évolution Volume % | `+0.0%;-0.0%;0.0%` | (N − N-1) / N-1 |
| 2. Prix | Prix Médian m² | `#,0 "€"` | `MEDIAN ( fact_ventes[prix_m2] )` |
| 2. Prix | Prix Moyen m² | `#,0 "€"` | `AVERAGE ( fact_ventes[prix_m2] )` |
| 2. Prix | Prix Médian Vente | `#,0 "€"` | `MEDIAN ( fact_ventes[valeur_fonciere] )` |
| 2. Prix | Surface Médiane | `#,0 "m²"` | `MEDIAN ( fact_ventes[surface] )` |
| 2. Prix | Prix Médian m² N-1 | `#,0 "€"` | même période un an plus tôt |
| 2. Prix | Évolution Prix m² % | `+0.0%;-0.0%;0.0%` | (N − N-1) / N-1 |
| 3. Classement | Rang Ville Prix m² | `0` | rang dense, 1 = ville la plus chère |
| 4. Carte | Prix Médian m² (≥ 30 ventes) | `#,0 "€"` | prix médian si au moins 30 ventes |
| 4. Carte | Nb Ventes (≥ 30 ventes) | `#,0` | nombre de ventes si au moins 30 ventes |
| 5. Simulateur | Budget Sélectionné | `#,0 "€"` | `SELECTEDVALUE ( 'Paramètre Budget'[Budget], 250000 )` |
| 5. Simulateur | m² Achetables | `#,0 "m²"` | `DIVIDE ( [Budget Sélectionné], [Prix Médian m²] )` |
| 5. Simulateur | Années de Revenu | `0.0 "ans"` | prix médian / revenu médian du ménage (INSEE) |

Chaque mesure porte une description (visible au survol dans le volet *Données*). Le DAX
complet est dans `DVF_Analyse.SemanticModel/definition/tables/_Mesures.tmdl` ; les mesures
« N-1 » et « Évolution » sont les plus longues :

```dax
Prix Médian m² N-1 =
VAR _annee = MAX ( dim_date[annee] )
RETURN
    IF (
        HASONEVALUE ( dim_date[annee] ),
        CALCULATE ( [Prix Médian m²], SAMEPERIODLASTYEAR ( dim_date[date] ) ),
        CALCULATE ( [Prix Médian m²], REMOVEFILTERS ( dim_date ), dim_date[annee] = _annee - 1 )
    )

Évolution Prix m² % =
VAR _annee = MAX ( dim_date[annee] )
VAR _n =
    IF (
        HASONEVALUE ( dim_date[annee] ),
        [Prix Médian m²],
        CALCULATE ( [Prix Médian m²], REMOVEFILTERS ( dim_date ), dim_date[annee] = _annee )
    )
VAR _n1 = [Prix Médian m² N-1]
RETURN
    IF ( NOT ISBLANK ( _n1 ), DIVIDE ( _n - _n1, _n1 ) )

Rang Ville Prix m² =
IF (
    HASONEVALUE ( dim_commune[ville_principale] )
        && NOT ISBLANK ( SELECTEDVALUE ( dim_commune[ville_principale] ) ),
    RANKX (
        FILTER ( ALLSELECTED ( dim_commune[ville_principale] ), NOT ISBLANK ( dim_commune[ville_principale] ) ),
        [Prix Médian m²], , DESC, DENSE
    )
)
```

`Nb Ventes N-1` et `Évolution Volume %` suivent le même modèle avec `[Nb Ventes]`.

**Paramètre de simulation** (à recréer si besoin) : *Modélisation > Nouveau paramètre >
Plage numérique*, nom `Paramètre Budget`, type *Nombre entier*, minimum 100000, maximum
500000, incrément 10000, valeur par défaut 250000, *Ajouter un segment* coché. Renommer la
colonne en `Budget` et supprimer la mesure générée (la mesure `Budget Sélectionné` existe déjà).

## 4. Contrôles à faire à l'ouverture

Après l'actualisation, sans aucun filtre sauf mention contraire :

| Où | Attendu |
|---|---|
| Page 1, carte « Nombre de ventes » (aucune sélection) | **3 831 945** |
| Page 1, « Prix médian au m² » (aucune sélection) | **2 653 €** |
| Page 1, segment Année = 2025 | 714 276 ventes ; 2 691 € ; évolution prix **+2,6 %** ; évolution volume **+13,7 %** |
| Page 1, aucune sélection | évolutions = 2025 vs 2024, donc mêmes valeurs que ci-dessus |
| Page 3, Année = 2025 | Paris 9 714 € (rang 1), Boulogne-Billancourt 8 300 €, Montreuil 5 994 €, … Saint-Étienne 1 243 € (rang 30) |
| Page 3, matrice (tous types) | Paris : 2022 −1,2 %, 2023 −5,3 %, 2024 −5,7 %, 2025 +1,3 % ; Lyon : +0,7 %, −4,5 %, −7,1 %, −0,4 % ; colonne 2021 vide (pas de 2020) |
| Page 4, budget 250 000 € (défaut) | Paris 26 m², Lyon 56 m², Marseille 75 m², Saint-Étienne 201 m² |
| Page 4, carte « Prix médian au m² (villes suivies) » | 3 956 € |
| Page 2, tableau des plus chères (toutes années) | Paris 6e Arrondissement 14 444 €, Paris 7e 14 180 €, Paris 4e 12 917 € |

Points à vérifier visuellement :

1. **Thème** : fond de page gris très clair, visuels blancs à bordure fine, couleurs bleu /
   orange / vert d'eau. Sinon : *Affichage > Thèmes > Parcourir les thèmes* > `powerbi/theme.json`.
2. **Carte (page 2)** : les bulles couvrent les 77 départements ; choisir une région pour une
   carte lisible (Azure Maps limite le nombre de points affichés). Si la carte reste vide,
   vérifier l'autorisation Azure Maps (§ 1) puis que `latitude` / `longitude` ont bien la
   catégorie *Latitude* / *Longitude* dans le modèle.
3. **Segments synchronisés** : changer « Région » ou « Type de bien » sur la page 1 doit se
   répercuter sur les pages 2, 3 et 4 (*Affichage > Synchroniser les segments* pour contrôler).
4. **Page 3** : le segment Année ne filtre que le classement (interactions désactivées vers la
   matrice et les petits multiples — *Format > Modifier les interactions*).
5. **Page 4** : le curseur Budget est un segment « valeur unique » ; le filtre de page
   `annee = 2025` est visible dans le volet *Filtres*.
6. Les titres, libellés et formats sont en français (séparateur de milliers espace, virgule
   décimale) car le modèle est en culture `fr-FR`.

Si un visuel affiche une erreur, le supprimer et le recréer avec le § 5.

## 5. Reconstruire les visuels à la main

Canevas 1280 × 720 px. Positions indicatives `x, y, largeur, hauteur`. Pour chaque visuel :
*Format > Général > Titre* activé avec le texte indiqué.

Segments communs (paramètres identiques sur chaque page où ils apparaissent) :

| Segment | Champ | Style | Synchronisation (*Affichage > Synchroniser les segments*) |
|---|---|---|---|
| Région | `dim_commune[region]` | Liste déroulante | groupe `sync_region` (pages 1 à 4) |
| Département | `dim_commune[departement]` | Liste déroulante | groupe `sync_departement` (pages 1, 2) |
| Type de bien | `dim_type_local[type_local]` | Liste déroulante | groupe `sync_type` (pages 1 à 4) |
| Année | `dim_date[annee]` | Liste déroulante | groupe `sync_annee` (pages 1 à 3) |

### Page 1 — Vue d'ensemble

| # | Visuel | Position | Champs | Mise en forme |
|---|---|---|---|---|
| 1 | Zone de texte | 24, 12, 1232, 56 | « Marché immobilier : les 10 régions les plus peuplées de France » + sous-titre « Ventes DVF d'un seul logement (maison ou appartement), 2021-2025, hors Alsace-Moselle (non couverte par DVF) » | 20 pt semi-gras ; 11 pt gris |
| 2-5 | Segments Région, Département, Type de bien, Année | 24/320/636/892, 76, 280/300/240/200, 80 | voir tableau ci-dessus | |
| 5 | **Carte** (nouvelle carte, plusieurs valeurs) | 24, 164, 1232, 108 | Valeurs : `Nb Ventes`, `Prix Médian m²`, `Évolution Prix m² %`, `Évolution Volume %` | Titre « Indicateurs clés (année la plus récente de la sélection pour les évolutions) » ; renommer les champs en « Nombre de ventes », « Prix médian au m² », « Évolution du prix au m² sur un an », « Évolution du volume sur un an » |
| 6 | **Graphique en courbes** | 24, 280, 1232, 212 | Axe X : `dim_date[annee_mois]` ; Axe Y : `Prix Médian m²` | Titre « Prix médian au m² par mois » ; axe X de type catégoriel |
| 7 | **Histogramme groupé** | 24, 500, 1232, 208 | Axe X : `dim_date[annee_mois]` ; Axe Y : `Nb Ventes` | Titre « Nombre de ventes par mois (même axe temporel que le graphique du prix) » |

> Prix et volume sont volontairement dans deux graphiques alignés plutôt que sur un graphique
> à double axe : deux échelles différentes sur un même graphique suggèrent une corrélation
> arbitraire. Si un graphique combiné est préféré : *Graphique en courbes et histogramme
> groupé*, axe X `annee_mois`, colonnes `Nb Ventes`, ligne `Prix Médian m²`.

### Page 2 — Carte des prix

| # | Visuel | Position | Champs | Mise en forme |
|---|---|---|---|---|
| 1 | Zone de texte | 24, 12, 1232, 56 | « Carte des prix au m² par commune » + « Taille des bulles = prix médian au m² ; communes avec au moins 30 ventes dans la sélection. Choisissez une région pour une carte lisible » | |
| 2-5 | Segments Région, Département, Type de bien, Année | comme page 1 | | |
| 5 | **Azure Maps** | 24, 164, 760, 544 | Emplacement : `dim_commune[nom_commune]` ; Latitude : `dim_commune[latitude]` ; Longitude : `dim_commune[longitude]` ; Taille : `Prix Médian m² (≥ 30 ventes)` ; Info-bulles : `Nb Ventes (≥ 30 ventes)` | Titre « Prix médian au m² par commune ». Optionnel : *Couche de bulles > Couleur de remplissage > fx* : dégradé sur `Prix Médian m² (≥ 30 ventes)` de `#CDE2FB` (bas) à `#104281` (haut) |
| 6 | **Tableau** | 800, 164, 456, 268 | `dim_commune[nom_commune]`, `dim_commune[departement]`, `Prix Médian m² (≥ 30 ventes)`, `Nb Ventes (≥ 30 ventes)` | Titre « Communes les plus chères au m² (≥ 30 ventes) » ; tri **décroissant** sur le prix |
| 7 | **Tableau** | 800, 440, 456, 268 | mêmes champs | Titre « Communes les moins chères au m² (≥ 30 ventes) » ; tri **croissant** sur le prix |

Les mesures « ≥ 30 ventes » renvoient une valeur vide sous 30 ventes : les petites communes,
aux médianes instables, disparaissent automatiquement de la carte et des tableaux.

### Page 3 — Comparaison des villes

Filtre **de page** : `dim_commune[ville_principale]` *n'est pas vide*.

| # | Visuel | Position | Champs | Mise en forme |
|---|---|---|---|---|
| 1 | Zone de texte | 24, 12, 1232, 56 | « Comparaison des 30 plus grandes villes » + « Classement, évolution annuelle et tendance trimestrielle du prix médian au m² » | |
| 2-4 | Segments Région, Type de bien, Année (titre « Année (classement) ») | 24/320/576, 76, 280/240/240, 80 | | |
| 4 | **Graphique à barres groupées** | 24, 164, 400, 544 | Axe Y : `ville_principale` ; Axe X : `Prix Médian m²` ; Info-bulles : `Rang Ville Prix m²`, `Nb Ventes` | Titre « Classement des villes par prix médian au m² » ; tri décroissant ; étiquettes de données activées |
| 5 | **Matrice** | 440, 164, 816, 260 | Lignes : `ville_principale` ; Colonnes : `dim_date[annee]` ; Valeurs : `Évolution Prix m² %` | Titre « Évolution annuelle du prix médian au m² (%) ». Optionnel : *Éléments de cellule > Couleur d'arrière-plan > fx* : dégradé divergent bleu `#2A78D6` (min) / gris `#F0EFEC` (0) / rouge `#E34948` (max) |
| 6 | **Graphique en courbes** | 440, 432, 816, 276 | Axe X : `dim_date[annee_trimestre]` ; Axe Y : `Prix Médian m²` ; **Petits multiples** : `ville_principale` | Titre « Tendance trimestrielle du prix médian au m² par ville » ; 30 villes : Power BI affiche une grille défilante (*Format > Petits multiples > Disposition* pour régler lignes et colonnes) |

Interactions (*Format > Modifier les interactions*, segment Année sélectionné) : **Aucun** vers
la matrice et vers les petits multiples, pour qu'ils gardent toutes les années.

### Page 4 — Simulateur budget

Filtres **de page** : `dim_commune[ville_principale]` *n'est pas vide* ; `dim_date[annee]` = 2025
(dernière année complète — à modifier dans le volet *Filtres* pour simuler une autre année).

| # | Visuel | Position | Champs | Mise en forme |
|---|---|---|---|---|
| 1 | Zone de texte | 24, 12, 1232, 56 | « Simulateur : combien de m² pour mon budget ? » + « Prix médians 2025 (filtre de page modifiable), hors frais de notaire » | |
| 2 | **Segment** | 24, 76, 360, 80 | `'Paramètre Budget'[Budget]` | Style **Valeur unique** (curseur) ; en-tête « Budget d'achat » |
| 3 | Segments Région, Type de bien | 400/656, 76, 240/200, 80 | | |
| 4 | **Carte** (plusieurs valeurs) | 872, 76, 384, 80 | `Budget Sélectionné`, `Prix Médian m²` | Titre « Budget et prix de référence » |
| 5 | **Graphique à barres groupées** | 24, 168, 600, 540 | Axe Y : `ville_principale` ; Axe X : `m² Achetables` | Titre « Surface achetable avec le budget sélectionné » ; tri décroissant ; étiquettes |
| 6 | **Graphique à barres groupées** | 640, 168, 616, 260 | Axe Y : `ville_principale` ; Axe X : `Surface Médiane` | Titre « Surface médiane des logements vendus » ; tri décroissant ; étiquettes |
| 7 | **Tableau** | 640, 436, 616, 272 | `ville_principale`, `Prix Médian m²`, `m² Achetables`, `Prix Médian Vente`, `Années de Revenu` | Titre « Détail par ville (années de revenu : INSEE Filosofi 2021) » ; tri décroissant sur `m² Achetables` |

## 6. Thème

Le thème `DVF_Theme` est déjà enregistré dans le rapport
(`StaticResources/RegisteredResources/`). Pour le réappliquer : *Affichage > Thèmes >
Parcourir les thèmes* > `powerbi/theme.json`. Palette catégorielle : `#2A78D6`, `#EB6834`,
`#1BAF7A`, `#EDA100`, `#E87BA4`, `#008300`, `#6250D6`, `#E34948` (même palette que les
graphiques Python de `reports/figures/`).

## 7. Captures d'écran pour le README

Après vérification, exporter une capture de chaque page (`Win + Maj + S`, ou *Fichier >
Exporter > PDF*) et les enregistrer sous :

- `reports/figures/dashboard_vue_ensemble.png`
- `reports/figures/dashboard_carte.png`
- `reports/figures/dashboard_villes.png`
- `reports/figures/dashboard_simulateur.png`

## 8. Revalider après modification

Les fichiers PBIR / TMDL sont du texte versionné : après une modification dans Desktop,
`python run.py validate-pbi` revérifie les schémas et la cohérence modèle ↔ visuels, et
`git diff` montre exactement ce qui a changé.
