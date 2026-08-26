# CFS Minimal Owner Passive Capture V1

Statut : **capture réelle terminée ; retrait officiel qualifié sur `T1A` ;
protocole série propriétaire toujours fermé**.

Cette gate a observé un seul retrait constructeur. L'observateur n'a écrit ni
sur le bus série ni dans les fichiers de la K1. Thomas a ensuite autorisé Codex
à lancer une fois la macro constructeur `BOX_QUIT_MATERIAL`.

Le retrait a réussi : la route fraîche `T1A` est passée de `A` à `None`, les
deux phases de retrait ont obtenu une réponse réussie et la macro s'est
terminée. La K1 a demandé elle-même `220 °C` pendant le cycle.

Deux limites importantes restent visibles :

- la macro laisse la cible de buse à `220 °C` après sa fin ; le nettoyage sûr a
  exigé `TURN_OFF_HEATERS` puis une vérification de la cible à zéro ;
- le capteur de la tête reste actif, ce qui signifie que le segment situé après
  le cutter reste dans le chemin chaud.

La capture ne prouve toujours ni la trame sortante complète, ni une prise de
contrôle exclusive du bus face au logiciel constructeur. La liste
`callable_messages` reste donc vide.

## Contenu

- `contract.json` : résultat de la gate et limites ;
- `evidence-map.json` : preuves nettoyées et empreintes privées ;
- `verify_private_capture.py` : vérificateur reproductible sans connexion K1 ;
- `RESULT.md` : conclusion opérationnelle ;
- `NEXT-STOCK-UNLOAD-GUARD.md` : prochaine étape proposée en langage courant.

## Vérification

```powershell
python packages\k1-control-v1\cfs-minimal-owner-passive-capture-v1\verify_private_capture.py
```

Le marqueur vert qualifie cette capture et son retour sûr. Il n'autorise aucun
nouveau retrait, chargement, envoi série ou déploiement.
