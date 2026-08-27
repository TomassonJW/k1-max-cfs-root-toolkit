# HANDOFF — adaptateur hors ligne du garde de retrait CFS

Date de passation : 2026-08-27 10:36:01 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`

## État à annoncer immédiatement à Thomas

- **L'adaptateur hors imprimante est clos OK.**
- Il transforme une réponse K1 déjà nettoyée vers les huit champs du garde.
- La matrice obtient `10/10`, les tests ciblés `17/17` et la suite complète
  exécute `429` tests, dont `426` verts et `3` ignorés connus.
- Aucun réseau, G-code, processus, accès K1, chauffe, mouvement, retrait,
  service, restart ou fichier distant n'a été utilisé.
- Aucun transport ni candidat de pose n'a été créé. La production reste fermée.
- La dernière observation K1 connue reste celle du préflight précédent : aucune
  route engagée, `T1/T2` connectés et cibles zéro. Elle n'a pas été rafraîchie
  pendant cette mission locale et peut donc devenir périmée.
- La prochaine mission proposée est
  `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`.
- Son état est **ATTENDRE_GO**. Aucun `GO` exact antérieur ni `$session-tas`
  d'un autre clavardage ne couvre une nouvelle connexion K1.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue ; son rollback et son audit CFS
  n'autorisent aucune reprise.
- Le profil diagnostic et quatre G-code restent absents ; les quatre G-code ne
  doivent pas être recréés depuis ce handoff.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste le marqueur de fermeture valide.
- Toute future action physique exige une route fraîche et, si le plateau est
  concerné, la confirmation « plateau réellement libre ».

## État livré

Le nouveau paquet
`packages/k1-control-v1/cfs-stock-unload-guard-adapter-offline-v1/` contient :

- `adapter.py`, une fonction pure sans capacité externe ;
- dix exemples synthétiques et `scenarios.json` ;
- un exécuteur local, un contrat fermé, le résultat et la prochaine gate ;
- dix-sept tests qui vérifient traduction, refus, compatibilité avec le garde,
  vie privée, syntaxe Python 3.8 et absence de transport.

La décision structurante est ADR-026 : la forme Moonraker reste séparée du
garde. Une route absente ou un second CFS déconnecté sont traduits pour laisser
le garde expliquer son refus. Plusieurs routes, un état d'unité inconnu, un slot
actif sur une unité déconnectée, une unité `T3/T4` connectée, un champ absent ou
une température invalide sont refusés immédiatement.

Les autorités canoniques sont `docs/37-adaptateur-hors-ligne-garde-retrait-cfs-v1.md`,
ADR-026, D-076, `GATES.md`, `STATE.md` et le contrat machine dans
`design/job-lifecycle-contract-v1.json`.

## Git vérifié avant le commit de passation

- SHA initial local et distant :
  `7656c29345db10cc5bad846a5c9d3c5cf2a2f988` ;
- commit de mission :
  `55add8019ca0f814d637c011651f150e2cd620f1`
  (`add offline CFS unload guard adapter`) ;
- branche de mission séparée : aucune ;
- worktree de mission séparé : aucun ;
- autre worktree observé : aucun ;
- ressources étrangères : aucune observée ;
- le SHA du commit qui contient cette passation et sa concordance avec
  `origin/main` seront communiqués dans le compte rendu final.

## Vérifications

- matrice locale de l'adaptateur : **OK**, `10/10` ;
- tests ciblés adaptateur : **OK**, `17/17` ;
- garde + mapping live + adaptateur : **OK**, `47/47` ;
- suite complète : **OK**, `429` exécutés, `426` verts, `3` ignorés connus ;
- `git diff --check` et contrôle staged : **OK** avant le commit de mission ;
- validation humaine ou physique : **non exécutée**, hors périmètre ;
- connexion K1 : **non exécutée**, hors périmètre.

## Limites et risques

- la future collecte doit encore retirer les identités avant l'adaptateur ;
- seules les valeurs d'unité exactes `connect` et `disconnect` sont acceptées ;
  toute autre forme réelle échouera volontairement jusqu'à revue ;
- aucun état live frais n'a prouvé l'intégration de bout en bout ;
- le garde possède toujours un chemin d'effet, mais cette mission ne le relie à
  aucun transport et ne l'a jamais appelé ;
- l'état courant sans route connue ne permettrait de toute façon aucun retrait.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`

En langage courant : lire deux fois un état K1 frais, retirer les identités
matérielles avant traitement et vérifier que l'adaptateur produit le même état
fonctionnel. Cette étape est utile pour détecter une dérive de forme du firmware
avant de construire un transport. Elle permettra seulement de confirmer la
traduction réelle, pas de retirer du filament.

Contraintes : lectures exactes revues, aucune écriture distante, aucun G-code,
aucune chauffe ou action physique, aucun appel à `StockUnloadGuard.run`,
empreintes des configurations avant/après et arrêt immédiat sur donnée nouvelle
ou ambiguë.

Critères de fin : deux réponses stables, nettoyage prouvé sans identité,
adaptation déterministe, refus attendu si aucune route n'est engagée, empreintes
inchangées, tests ciblés et suite complète verts, puis nouvelle passation.

Autorisation de démarrage : **ATTENDRE_GO**.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, suffisant pour cette
lecture bornée mais sensible à la vie privée. Option économique : le même modèle
en `medium`, avec davantage de risque de manquer une dérive subtile de schéma.
