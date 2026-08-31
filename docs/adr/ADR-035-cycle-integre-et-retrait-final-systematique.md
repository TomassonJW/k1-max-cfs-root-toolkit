# ADR-035 — Cycle intégré et retrait final systématique

Statut : **cycle cible conservé, candidat stock clos KO et effets désactivés**

## Contexte

Le 31 août 2026, la revue du candidat R4 a montré un écart de compréhension :
R4 est une séquence de démarrage installée, pas le cycle quotidien complet
attendu par Thomas. Les validations précédentes ont qualifié des briques
séparées, mais elles n'ont pas encore produit un parcours simple depuis
Mainsail qui possède le retrait initial, l'attente du nettoyage manuel, les
références, le chargement, la purge, l'impression et la fin.

L'ancien contrat retenait par défaut le bon filament engagé à la fin. Thomas a
maintenant demandé explicitement une fin normale qui retire complètement le
filament, le rembobine, descend le plateau, parque la tête, refroidit puis
libère les moteurs.

## Décision

K1 Control doit devenir l'unique propriétaire visible du cycle quotidien. Le
parcours cible est le suivant :

1. un bouton `Préparer l'impression` dans K1 Control ouvre un cycle unique ;
2. toute route engagée est coupée, la pointe locale est rétractée de `12 mm`
   hors de la zone chaude, puis la route est rembobinée sous une température
   explicite du contrat, avec une seule tentative et une preuve de libération ;
   si les capteurs voient le T1A déclaré mais que sa route logique a été perdue
   après un redémarrage, il est réassocié une seule fois avant ce retrait ;
3. K1 Control s'arrête et demande le nettoyage manuel de la buse ;
4. `Buse propre — Continuer` est la seule confirmation humaine nécessaire à
   cette frontière ;
5. la machine stabilise le contexte de référence, fait X/Y puis l'unique
   référence Z précise, sans calibration de mesh ;
6. le profil `k1_p001_t055_r001_n11x11` et le Z accepté sont chargés et relus ;
7. `T1A` est chargé par des primitives bornées, à une température explicitement
   fournie par le travail ; toute réécriture CFS imprévue ferme le cycle ;
8. une seule purge utile est déposée hors de la zone du modèle et prouvée par
   caméra ;
9. le modèle utilise les températures explicites du contrat Orca ;
10. la fin lève la buse, descend le plateau, coupe, rétracte localement puis retire le filament,
    vérifie le rembobinage, parque ensuite la tête, met les chauffes et
    ventilateurs à zéro, puis libère les moteurs ;
11. un effet incertain n'est jamais rejoué automatiquement.

La quatrième révision du propriétaire de démarrage reste une brique réutilisée,
mais elle n'est plus présentée comme la version complète. Le nouveau cycle
intégré possède aussi les actions CFS, l'interface, le lancement du fichier et
la fin.

## Frontières de sécurité

- Le nettoyage de buse reste manuel.
- Une insertion, une purge ou un retrait invalide toute confirmation précédente
  de buse propre.
- Aucun mesh n'est recalculé pendant un travail quotidien.
- Les primitives `BOX_EXTRUDE_MATERIAL`, `BOX_EXTRUDER_EXTRUDE`,
  `BOX_CUT_MATERIAL` et `BOX_RETRUDE_MATERIAL` restent interdites sur la K1
  tant que leurs commandes exactes, températures et effets n'ont pas passé une
  gate physique bornée avec Thomas présent.
- Le `220 °C` stock n'est jamais accepté comme valeur implicite.
- La caméra arrête la progression si la purge, la buse ou la première couche ne
  sont pas concluantes.

## Conséquences

- La politique de fin `keep_engaged` de JOB-LIFECYCLE-OFFLINE-V1 devient une
  preuve historique, pas la cible produit.
- `END-SEQUENCE-V1` doit inclure le retrait et le rembobinage dans la fin
  normale ; le bouton séparé de retrait n'est plus le chemin quotidien.
- Le cutover Orca ne sera autorisé qu'avec un début et une fin K1 Control
  atomiques et sans `START_PRINT`, `END_PRINT`, `Tn` ou offset Z historique.
- Les prochaines validations physiques sont regroupées dans un essai intégré ;
  aucune nouvelle série de micro-tests répétitifs n'est demandée avant que le
  candidat complet soit vert hors imprimante.

## Alternatives refusées

- **Conserver R4 comme produit quotidien** : il ne possède ni chargement CFS,
  ni interface complète, ni fin.
- **Continuer à demander les clics CFS stock** : la température et les effets
  ne sont pas possédés par K1 Control.
- **Garder le filament engagé en fin normale** : contraire au besoin explicite
  fixé le 31 août 2026.
- **Qualifier chaque commande dans une mission utilisateur séparée** : conserve
  la fragmentation qui a masqué l'absence d'intégration.

## Résultat réel du 31 août 2026

Le candidat a contredit sa propre frontière de sécurité en appelant
`BOX_EXTRUDE_MATERIAL` avant sa qualification isolée. Le run a confirmé la
preuve historique : la primitive a référencé X/Y, annoncé `flush_temp: 220`,
porté la buse au-dessus de `220 °C`, vidé le mesh actif puis échoué sans engager
`T1A`. Le garde a remis les cibles à zéro et aucun retry n'a été lancé. Le
profil `11 × 11` a ensuite été restauré.

Ce candidat ne doit plus être exécuté. Les quatre effets CFS stock sont retirés
des macros appelables et le composant installé reste en mode `offline`. La
prochaine décision doit soit remplacer ces effets par un propriétaire CFS
borné dont la température et les mouvements sont réellement contrôlés, soit
assumer explicitement un clic humain officiel à cette frontière. Une nouvelle
gate intégrée est interdite avant cette décision et la qualification séparée
du chargement et du retrait retenus.

## Suite de décision

ADR-036 choisit depuis le propriétaire CFS direct au-dessus du seul transport
`serial_485` stock. Sa preuve hors imprimante obtient `24/24`; la pose et les
effets physiques restent fermés. Cette suite ne change pas le KO réel ci-dessus
et ne rend pas le candidat stock rejouable.
