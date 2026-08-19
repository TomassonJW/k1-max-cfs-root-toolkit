# Session G3 A1/B/A2 — constats nettoyés

Date : 2026-08-19

Capture : `20260819-185157-g3-aba`

Firmware : `2.3.5.34`

Statut : **session terminée, comparaison physique non qualifiée**

## Périmètre et sécurité

Thomas a lancé les trois impressions et réalisé toutes les interventions physiques. Codex a uniquement lu le flux Klipper existant et créé des fichiers locaux. Aucune commande de chauffe, mouvement, calibration, impression, annulation, configuration ou écriture distante n'a été envoyée par Codex.

Les captures brutes, la cible réseau, les noms privés et les G-codes complets restent sous `inventory/raw/` et ne sont pas publiés.

## Entrées

| Run | Géométrie | Taille privée | SHA-256 |
|---|---|---:|---|
| A1 | `200 × 200 × 0,20 mm` | 70 731 octets | `50B54577A4B8A76A0BB5FB2B48E915D1DC6EA9E5BB87AA1F32404C559A54F856` |
| B | `200 × 201 × 0,20 mm` | 70 797 octets | `D8C1B625649A816398C2034FC573B825548D1B1899B79809FDD2C9B0FAFA59A1` |
| A2 | identique à A1 | 70 731 octets | identique à A1 |

Les deux fichiers demandent `190 °C` pour la buse, `55 °C` pour le lit, un décalage Z protecteur de `+0,27 mm` après `START_PRINT` et une pression d'avance de `0,03` après le retour de `START_PRINT`.

## Résultat physique déclaré par Thomas

| Run | Observation | Intervention |
|---|---|---|
| A1 | légèrement trop bas au départ ; résultat ensuite proche du bon | valeur affichée passée de `0,27` à `0,26` |
| B | résultat plutôt correct | aucune correction Z ; serrage des vis du plateau modifié avant B |
| A2 | potentiellement correct ; réaction du mesh jugée étrange et subtile | Z laissé à `0,27` ; serrage des vis de nouveau rectifié |

Les réglages mécaniques entre les essais changent réellement le plan du plateau. La série ne peut donc pas attribuer une différence au seul millimètre ajouté dans B.

## Chronologie utile

| Run | Événement | Heure machine |
|---|---|---|
| A1 | lancement déclaré | `19:02` |
| A1 | fin naturelle, position correspondant à 70 731 octets | `19:27:14` |
| B | premier réglage Z observé | `19:32:32` |
| B | nettoyage de buse observé | `19:33:36` à `19:34:10` |
| B | pression d'avance `0,044` appliquée | `19:35:54` |
| B | second réglage Z observé | `19:36:18` |
| B | fin naturelle, position correspondant à 70 797 octets | `19:56:47` |
| A2 | nettoyage de buse observé | `20:00:33` à `20:02:16` |
| A2 | pression d'avance `0,044` appliquée | `20:03:01` |
| A2 | dernier réglage Z avec nombreuses reprises | `20:03:30` à `20:04:01` |
| A2 | fin naturelle, position correspondant à 70 731 octets | `20:24:21` |

## Faits établis

### Le chemin Z n'est pas une mesure unique

Le démarrage stock exécute plusieurs phases capables de toucher à la référence Z : premier homing, nettoyage avec ses propres sondages, homing précis, puis contrôle du nivellement. B et A2 ont chacun montré au moins deux séquences Z séparées autour du nettoyage.

Pendant le dernier homing de B, la liste interne finale visible était `[0,256 ; 0,290 ; 5,175]`. Pendant A2, le firmware a poursuivi jusqu'à l'index de tentative 7 et la liste visible a fini à `[0,208 ; 0,258 ; 6,008]`. Ces valeurs sont des mesures internes du chemin de recherche, pas un décalage utilisateur directement applicable. Elles prouvent néanmoins que le nombre de reprises et les valeurs rejetées varient fortement entre deux préparations.

Le code lisible du PR Touch confirme que la procédure déplace le point de recherche, retire temporairement le mesh, réalise plusieurs mesures, conserve une médiane puis restaure le mesh. Le contrôle stock du lit choisit également ses quatre points de coin avec une petite part aléatoire et peut recréer puis sauvegarder le mesh si son seuil est dépassé.

### Deux valeurs de pression d'avance se concurrencent

Les G-codes privés demandent `0,03`. Le journal a pourtant confirmé une commande à `0,044`, avec temps de lissage `0,04`, pendant la préparation de B et d'A2. La capture par console n'a pas permis de confirmer si le `0,03` du fichier a repris la main avant l'extrusion utile.

Le fait certain est donc l'existence de deux producteurs de valeur. La valeur finale active reste à lire directement lors d'une future observation passive. L'interface stock utilisée par Thomas ne permet pas de la corriger pendant l'impression.

### Le nettoyage stock correspond au comportement signalé

La trace A2 montre une phase à température minimale, une montée vers `170 °C`, un passage de nettoyage, puis un refroidissement. Le code lisible choisit un départ variable dans la zone de brosse et réalise essentiellement un trajet linéaire. Il ne met pas en œuvre le nettoyage principal de fin d'impression, à passages rapides en zigzag et refroidissement contrôlé, demandé par Thomas.

### La piste multi-objets reste ouverte

A et B contiennent chacun un seul objet. Cette session ne teste donc pas l'hypothèse selon laquelle plusieurs objets ou des réglages réellement différents changent le comportement du travail suivant.

Le `START_PRINT` lisible ne consomme pas directement le nombre d'objets. Une couche compilée ou l'état laissé par une impression longue peut encore intervenir. Le prochain fichier multi-objets réellement problématique devra être comparé hors ligne à un fichier sain avant toute nouvelle impression de test.

## Qualification Q1 à Q5

| Gate | Verdict | Motif |
|---|---|---|
| Q1 — intégrité | OK | empreintes locales connues ; fins A1/B/A2 cohérentes avec les tailles de fichiers |
| Q2 — conditions initiales | KO | serrage des vis du plateau modifié entre les essais et pendant l'interprétation d'A2 |
| Q3 — chemin d'exécution | KO | grandes étapes communes, mais nombre de reprises Z différent |
| Q4 — observabilité | KO | début A1 incomplet et pression d'avance finale non observable |
| Q5 — pouvoir discriminant | inconnu | résultat physique mélangé aux réglages mécaniques |

La paire n'est pas qualifiée. Gate G3 reste ouverte.

## Décision et prochaine preuve

Aucune quatrième impression sacrifiée n'est justifiée. Les prochains relevés doivent entourer une impression longue réellement utile puis le fichier suivant, surtout s'il contient plusieurs objets ou des réglages différents.

La première installation à préparer reste un overlay stock minimal et réversible, pas un remplacement complet :

1. ordre de démarrage déterministe et journalisé ;
2. nettoyage principal en fin d'impression, avec contrôle court avant sondage ;
3. référence Z établie à un point fixe avec rejet explicite des mesures aberrantes ;
4. mesh recréé uniquement sur demande ou selon une règle explicite, jamais sauvegardé silencieusement ;
5. pression d'avance appliquée une seule fois après le CFS, visible et réglable en direct.

Ce lot doit encore être séparé en changements indépendants sous G4. Aucun déploiement n'est autorisé par cette session.
