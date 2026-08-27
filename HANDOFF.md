# HANDOFF — validation live en lecture seule de l'adaptateur CFS

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`

## État à annoncer immédiatement à Thomas

- **La validation live de l'adaptateur est close OK en lecture seule.**
- Deux états K1 frais ont été lus et donnent la même traduction fonctionnelle.
- `sn` et `uuid` sont retirés avant l'appel à l'adaptateur ; la capture brute
  reste privée et ignorée par Git.
- Klipper est prêt, la K1 est au repos, `T1/T2` sont connectés, aucune route
  n'est engagée, la commande CFS est vide et les cibles sont à zéro.
- Les trois configurations gardent les mêmes empreintes avant et après.
- Le garde n'a été ni importé ni appelé. Aucun G-code, chauffage, mouvement,
  retrait, fichier distant, service ou restart n'a eu lieu.
- L'état fonctionnel reste `BLOCKED_NO_ENGAGED_ROUTE`. Aucun transport ni
  candidat de pose n'existe et la production reste fermée.

## État livré

Le paquet
`packages/k1-control-v1/cfs-stock-unload-guard-adapter-live-read-only-v1/`
contient le collecteur strictement en lecture seule, la projection locale sur
liste blanche, la vérification de la preuve privée, le contrat fermé et le
résultat public nettoyé. La capture privée de référence est
`20260827-110102-g4-k1-control-cfs-stock-unload-guard-adapter-live-read-only-v1` ;
seule son empreinte SHA-256 est publiée.

La forme live a révélé une différence exacte avec les exemples synthétiques :
les unités non provisionnées `T3/T4` utilisent l'état texte `None`. L'adaptateur
reconnaît désormais cette valeur uniquement pour `T3/T4` comme état inactif.
Elle reste refusée pour `T1/T2`, et toute autre valeur inconnue reste refusée.

La décision D-077 complète ADR-026 sans changer l'architecture : le collecteur,
le nettoyage, l'adaptateur et le garde restent séparés. Les documents
canoniques sont `docs/38-validation-live-adaptateur-garde-retrait-cfs-v1.md`,
D-077, `GATES.md`, `STATE.md` et
`design/job-lifecycle-contract-v1.json`.

## Git vérifié avant le commit de passation

- SHA de départ local et distant :
  `973fcabbcfad54115671bad94ecb6c27dc3826b6` ;
- divergence avant clôture : `0/0` ;
- branche de mission séparée : aucune ;
- worktree de mission séparé : aucun ;
- autre worktree observé : aucun ;
- ressource étrangère observée : aucune ;
- le commit final, le SHA local/distant et la propreté seront communiqués dans
  le compte rendu final.

## Vérifications

- capture SSH revue : **OK**, sortie `exit_code=0` ;
- validation privée nettoyée : **OK**,
  `VALIDATE_CFS_STOCK_UNLOAD_GUARD_ADAPTER_LIVE_READ_ONLY_V1_OK` ;
- deux lectures stables et empreintes inchangées : **OK** ;
- tests ciblés garde, mapping et adaptateurs : **OK**, `61/61` ;
- suite complète : **OK**, `443` exécutés, `440` verts et `3` ignorés connus ;
- `git diff --check` : **OK** avant staging ;
- validation physique ou retrait : **non exécuté**, hors périmètre ;
- production : **fermée**.

## Limites et risques

- l'état live courant ne contient aucune route engagée : aucune précondition de
  retrait n'est satisfaite ;
- le validateur refuse volontairement toute dérive de forme, ce qui peut exiger
  une nouvelle revue après une évolution du firmware ;
- le futur transport n'existe pas encore ; les délais, erreurs réseau,
  réponses trompeuses et arrêt thermique doivent encore être reliés sans
  affaiblir le garde ;
- la capture privée ne doit jamais être ajoutée à Git ni recopiée dans une
  passation publique.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`

En langage courant : construire hors imprimante la petite couche qui pourra un
jour lire l'état K1 et transmettre uniquement les deux commandes déjà figées
par le garde. Elle sera testée sur des réponses synthétiques ou enregistrées,
avec délais, erreurs, faux retours positifs et absence totale de relance
automatique.

Contraintes : aucune connexion K1, aucun G-code réel, aucun processus distant,
aucun retrait, aucune chauffe et aucun candidat de pose. Relire ADR-023 à
ADR-026, D-077, le contrat du garde et le paquet live présent.

Critères de fin : interface minimale documentée, encodage exact, erreurs et
timeouts fermés, deux commandes seulement, tests de non-répétition, aucune
capacité live dans les tests, suite complète verte et nouvelle passation.

Autorisation de démarrage : **GO_DIRECT dans ce clavardage tant que
`$session-tas` reste actif ; sinon ATTENDRE_GO**. Cette autorité ne couvre
toujours aucune connexion ni action physique.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, pour relier les erreurs
de transport aux invariants thermiques sans ouvrir un chemin d'effet. Option
économique : `gpt-5.6-terra` en `medium`, avec plus de risque d'oublier un cas
de timeout ou de répétition.
