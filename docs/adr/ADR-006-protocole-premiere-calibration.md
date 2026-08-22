# ADR-006 — Première calibration par checkpoints observables

Date : 2026-08-22

Statut : accepté hors imprimante, non autorisé à l'exécution

## Contexte

Le runtime Z/mesh et le chemin borné du premier Z sont installés et validés à
vide. Ils fournissent les briques techniques, mais aucune première calibration
n'a été menée et aucune interface quotidienne ne les orchestre encore.

Cette première calibration change deux états persistants : un profil mesh dans
`printer.cfg`, puis le Z accepté dans le stockage atomique. Elle comporte aussi
chauffe, nettoyage, homing, mesures et mouvements bas. Une commande monolithique
rendrait les écarts difficiles à attribuer et supprimerait les checkpoints
humains nécessaires au premier Z.

## Options examinées

### Une macro unique de calibration complète

Refusée. Elle enchaînerait les actes physiques sans preuve observable entre les
deux meshes ni confirmation humaine à `0,1 mm`. Son rollback après un restart
`SAVE_CONFIG` serait aussi difficile à raisonner.

### Le bouton générique de calibration Mainsail

Refusé comme pilote de cette gate. L'essai précédent a produit un mesh `Base`
transitoire, sans identité plaque/température, comparaison, seuil explicite ni
contrat d'enregistrement compréhensible.

### Une séquence locale découpée en actions gardées

Retenue. Le pilote local n'ajoute aucun fichier sur la K1 et n'accepte qu'une
liste figée de commandes déjà présentes. Chaque action exige le nom exact de la
gate, la capture privée et les checkpoints précédents.

## Décision

`G4-K1-CONTROL-FIRST-CALIBRATION-V1` utilise :

- `PEI_TEXTURED_A`, identifiant numérique `1` ;
- plateau `60 °C`, buse stabilisée à `140 °C` pendant `600 s` ;
- nettoyage stock borné `140 → 180 → 140 °C`, puis homing explicite ;
- deux mesures `6 × 6` Lagrange sur `5–295 mm` ;
- qualification par écart absolu point par point, maximum `0,025 mm` ;
- aucun troisième mesh automatique en cas de KO ;
- profil accepté `k1_p001_t060_r001_n06x06` ;
- seed Z neutre et explicite `0,0 mm`, puis les paliers installés par ADR-005 ;
- confirmation humaine du jeu, remontée de `5 mm`, puis commit atomique du Z.

L'ordre de checkpoint est : préflight, préparation, mesh 1, mesh 2 et
qualification, commit mesh, reprise thermique et homing, ouverture Z, un palier
par action, ajustements facultatifs, confirmation et park, acceptation ou
annulation, validation.

`Cancel` ferme la session Z et conserve le mesh qualifié. `Rollback` restaure
le `printer.cfg` exact et l'absence initiale du stockage Z ; il conserve les
deux composants déjà installés.

## Conséquences

La mission sera plus lente qu'une macro unique, car deux stabilisations et des
checkpoints humains sont assumés. En échange, toute divergence est localisée et
aucun rerun coûteux n'est implicite.

Une calibration réussie ne prouvera pas l'autonomie de calibration : Thomas
devra encore pouvoir choisir ces paramètres, voir les deux résultats et utiliser
enregistrer/annuler/restaurer depuis une vraie interface. Elle ne prouvera pas
non plus l'autonomie production, toujours fermée par Orca, `START_PRINT`, le
`+0,27 mm`, les températures CFS et G5.
