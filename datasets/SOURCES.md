# Données AthirAI

Origine, licence et usage de chaque jeu de données. Les licences sont à vérifier avant tout usage commercial (README §43).

## Fichiers produits (`processed/`)

Générés par les scripts de `scripts/data/`. Pour les régénérer, depuis la racine du projet, dans cet ordre (`pdftotext` de poppler est requis pour IFRA) :

```sh
python scripts/data/extract_ifra_limits.py
python scripts/data/extract_piesse_formulas.py
python scripts/data/build_ingredients.py
```

| Fichier | Contenu |
|---|---|
| `ingredients.csv` | **Table unifiée des matières premières**, une ligne par matière, clé = CAS (chiffre de contrôle vérifié). 8 469 matières, dont 6 586 avec CAS. Les autres ont pour identifiant `CID:<n>` (PubChem) ou `NAME:<nom>`. Colonnes : identité (CAS, autres CAS, nom, CID, SMILES, masse moléculaire, n° FEMA), odeur (descripteurs fusionnés de toutes les sources, description, descripteurs IFRA), comportement (étage tête/cœur/fond, ténacité en heures, intensité, impact, dilution conseillée pour sentir, seuil de détection en ppm), dosage (typique et maximum en % du concentré), réglementation (statut IFRA, limite IFRA catégorie 4, n° de norme, allergène UE), `sources` |
| `ifra_standards.csv` | Les 263 normes IFRA, une ligne par norme : CAS, statut (RESTRICTION / PROHIBITION / SPECIFICATION), amendement, limite maximale dans le produit fini pour chacune des 18 catégories (`cat_1` … `cat_12`), encadré « notebox » éventuel |
| `ifra_limits.csv` | Les mêmes limites, une ligne par norme et par catégorie (4 554 lignes) |
| `ifra_categories.csv` | Description en français des 18 catégories de produits IFRA (la catégorie 4 correspond à la parfumerie fine) |
| `piesse_formulas.csv` | 207 recettes de Piesse (1857), 997 lignes d'ingrédients : quantité, unité d'origine, volume approximatif en ml, part de la recette en % |

## Sources brutes

| Fichier / dossier | Contenu | Source | Licence | Usage AthirAI |
|---|---|---|---|---|
| `perfumes.jsonl` (+ `SCHEMA.md`) | 140 228 parfums : notes pondérées, accords, tenue, sillage, « reminds me of » | [Kaggle ledecanteur/fragrantica-perfumes](https://www.kaggle.com/datasets/ledecanteur/fragrantica-perfumes) | **CC BY-NC-SA 4.0 (non commercial)** | Recherche sémantique, analyse d'intention |
| `parfumo_data_clean.csv` | 59 325 parfums Parfumo (autre communauté que Fragrantica) | [TidyTuesday 2024-12-10](https://github.com/rfordatascience/tidytuesday/tree/main/data/2024/2024-12-10) | Scraping Parfumo, à vérifier | Valider sur une source indépendante les modèles entraînés sur Fragrantica |
| `final_perfume_data.csv` | 2 191 parfums de niche avec descriptions | Kaggle (Luckyscent) | Scraping, à vérifier | Texte → profil olfactif |
| `FINAL.csv` | 6 674 molécules, SMILES, masse moléculaire, 110 descripteurs | [Kaggle tajvarhirad/perfume](https://www.kaggle.com/datasets/tajvarhirad/perfume) | Droits des sources, à vérifier | → `ingredients.csv` |
| `pyrfume/` | 10 jeux Pyrfume (voir ci-dessous) | [pyrfume-data](https://github.com/pyrfume/pyrfume-data) | Variable (voir `manifest.toml` de chaque dossier) | → `ingredients.csv`, perception |
| `perfumenuke/data/` | 134 matières : étage, ténacité, impact, dosage moyen et max | [perfumenuke](https://github.com/nuke-haus/perfumenuke) | GPL-3.0 | → `ingredients.csv` |
| `openpom/curated_GS_LF_merged_4983.csv` | 4 983 molécules, 138 descripteurs | [OpenPOM](https://github.com/BioMachineLearning/openpom) | MIT (code) ; données GS/LF à vérifier | Entraîner un modèle molécule → odeur |
| `odor_strength/` | Modèle entraîné d'intensité d'odeur (inodore / faible / moyenne / forte), données PubChem, code | [Fichtelmann & Westermayr 2025](https://arxiv.org/abs/2512.08683), [Zenodo 17828661](https://doi.org/10.5281/zenodo.17828661) | MIT | Intensité des matières sans donnée |
| `dream_mixtures_2024/raw/` | Composition de mélanges (CID) et distances perceptives mesurées | [CWYK-Olfboost](https://github.com/Satarifard/CWYK-Olfboost), [DREAM Mixtures Challenge](https://dreamchallenges.org/olfactory-mixtures-prediction-challenge/) | Apache-2.0 | Composition → perception |
| `ifra_standards/` | Index et PDF des 263 normes IFRA | [IFRA Standards Library](https://ifrafragrance.org/standards-library), 2026-10-14 | Documents publics IFRA | → `ifra_*.csv` |
| `eu_regulation/` | Règlement (UE) 2023/1545 (XHTML) et CSV de ses 62 entrées d'allergènes | [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2023/1545) | Texte officiel UE | → `ingredients.csv` |
| `books/piesse_art_of_perfumery_1857.txt` | *The Art of Perfumery* (Piesse) | [Project Gutenberg #16378](https://gutenberg.org/ebooks/16378) | Domaine public | → `piesse_formulas.csv` |
| `olfactory_perception_benchmark/` | 1 010 questions pour évaluer un LLM sur l'olfaction ; descripteurs en français et en arabe dans `translations/` | [HF opbenchmark](https://huggingface.co/datasets/opbenchmark/Olfactory-Perception-Benchmark) | CC BY 4.0 | Choisir et tester le LLM |
| `zenodo_laymen_74_odors/` | 74 molécules décrites par 1 227 non-experts | [Zenodo 15657278](https://zenodo.org/records/15657278) | CC BY 4.0 | Vocabulaire des clients → molécules |

### Dossiers `pyrfume/`

- Utilisés par `build_ingredients.py` : `goodscents/` (ténacité, intensité, descriptions ; licence GoodScents restrictive), `leffingwell/`, `arctander_1960/`, `ifra_2019/` (glossaire IFRA), `abraham_2012/` (seuils de détection).
- Perception humaine, pour les modèles futurs : `keller_2016/` (480 molécules notées par 55 personnes), `dravnieks_1985/`, `snitz_2013/`, `bushdid_2014/`, `ravia_2020/` (mélanges).

## Limites connues

- **Seule la colonne `ingredient_id` est garantie unique.** Une même molécule peut encore apparaître sous un CAS et sous un `CID:` quand aucune source ne fait le lien.
- 375 matières GoodScents n'ont pas de nom dans le dump (surtout des mélanges et des extraits naturels, par exemple `8002-33-3`). Leur CAS et leur description d'odeur sont présents.
- `smelling_dilution_pct` est la dilution conseillée par GoodScents **pour sentir** la matière, pas une dose maximale en formule. Les doses en formule sont `typical_pct_in_concentrate` et `max_pct_in_concentrate` (perfumenuke, 123 matières).
- `ifra_cat4_max_pct` indique la limite de la première norme qui cite le CAS. Pour une matière couverte par plusieurs normes, se référer à `ifra_standards.csv`.
- Le CSV des allergènes UE ne contient que les entrées **ajoutées ou modifiées** par 2023/1545. Les allergènes inchangés de l'annexe III (linalol, coumarine…) sont à compléter depuis CosIng.
- Dans `piesse_formulas.csv`, les volumes convertissent des mesures impériales de 1857 (poids compté comme 1 g = 1 ml). Les matières sont anciennes (« extrait de pommade », « otto ») et doivent être rapprochées des matières modernes.
- Les `weight` de notes Fragrantica mesurent une présence perçue votée par les utilisateurs, pas une concentration.
- Aucun jeu ne contient de formules modernes avec leurs pourcentages.
- Retiré le 2026-10-15 : `zenodo_gcms_4_perfumes/` (aucune molécule identifiée, toujours disponible sur [Zenodo 3249821](https://zenodo.org/records/3249821)), les 50 autres jeux Pyrfume, le code de l'application perfumenuke, le PDF EUR-Lex en double. Supprimés par erreur et non récupérables : `piramides.json` (160 pyramides, CC BY 4.0, Private Riche) et `perfume_compound.csv` (24 huiles essentielles et leurs composants majeurs) ; à retélécharger depuis leur source d'origine si besoin.
