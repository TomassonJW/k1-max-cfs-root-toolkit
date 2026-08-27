# HANDOFF — mapping live du garde de retrait CFS

Date de passation : 2026-08-27 09:52:56 +02:00
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`
Tâche source : `01a03f87-9fb5-7ab3-95ed-b4ea07c2743e`

## État à annoncer immédiatement à Thomas

- **Le mapping live du garde est validé avec une correction du contrat.**
- La connexion K1 est restée entièrement en lecture seule.
- Aucun G-code, chauffage, mouvement, retrait, service, restart ou fichier
  distant n'a été produit.
- Deux instantanés confirment Klipper prêt, la machine `standby`, `T1/T2`
  connectés, `t_command` vide et les deux cibles à zéro.
- Aucun slot CFS n'est actuellement engagé : le garde répondrait donc
  `BLOCKED_NO_ENGAGED_ROUTE` sans envoyer de commande.
- Le segment après cutter reste détecté dans la tête.
- La K1 n'expose aucun champ direct de fin de retrait.
- `t_command` ne suit pas le cycle stock : il était resté vide dans la capture
  historique.
- Le garde est corrigé pour utiliser le retour de requête et la route réellement
  libérée. HTTP `ok` seul reste insuffisant.
- Les trois configurations gardent leurs empreintes avant/après.
- Aucun transport de production ni candidat de pose n'a été créé.
- La production reste fermée.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback et son audit CFS
  n'autorisent aucune reprise : le profil diagnostic et quatre G-code sont absents.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste son marqueur de fermeture valide.
- Les quatre G-code ne doivent pas être recréés depuis ce handoff.
- Toute future action physique exige une route fraîche et, si le plateau est
  concerné, la confirmation « plateau réellement libre ».
- Aucun `GO` exact antérieur ne couvre une nouvelle connexion ou action K1.
- Autorisation suivante : **ATTENDRE_GO**.

## État Git

- SHA initial local et distant :
  `33c860fef21c4d2679beac0fc48b811c872734d4`.
- Commit de mission :
  `a283898a91f4b816ebab475bc154b0edfc4f3802` (`map live CFS unload guard state`).
- `main` local et `origin/main` ont été vérifiés sur ce même SHA après
  `git fetch origin`.
- Divergence locale/distante : aucune.
- Statut du checkout cible avant cette mise à jour documentaire : propre.
- Branche de mission séparée : aucune.
- Worktree de mission séparé : aucun.
- Autre worktree observé : aucun.
- Le présent ajustement documentaire de clôture doit être committé et poussé
  séparément ; son SHA final est à relever dans le compte rendu de clôture.

## Capture live retenue

Session privée :
`inventory/raw/20260827-020930-g4-k1-control-cfs-stock-unload-guard-live-preflight-v1`

Empreinte de la capture privée :
`ef9af2d9bcdd812ba8e124ba26e84cb5cc34d7225e62e5f392758146f6b59604`.

Les réponses complètes de `box` restent ignorées par Git car elles contiennent
des identités matérielles. Seuls les états fonctionnels nettoyés sont publiés.

## Première capture rejetée

La session privée `20260827-020828-...` utilisait `curl -sS`. Le curl Creality a
signalé ces options comme invalides. La capture contenait encore des réponses,
mais elle n'est pas retenue comme autorité puisque la commande avait produit des
erreurs. Aucun effet distant n'a eu lieu.

Le collecteur corrigé utilise le curl exact sans ces options. Son script, sa
syntaxe et l'absence de commandes distantes mutantes sont testés.

## Correspondance qualifiée

- `print_stats.state` devient l'état d'impression ;
- `box.state` devient l'état global CFS ;
- les `box.T1..T4.state=connect` deviennent les unités connectées ;
- chaque `box.Tn.filament=A..D` devient une route comme `T1A` ;
- `box.t_command` devient la garde contre une commande active ;
- `extruder.target` et `heater_bed.target` deviennent les cibles thermiques ;
- le capteur principal indique le segment restant dans la tête.

## Correction du garde

Le champ abstrait `stock_unload_state` est retiré du contrôleur et de ses
scénarios. Après une tentative unique, le succès exige maintenant :

1. retour de la requête sans erreur de transport ;
2. disparition réelle de la route attendue ;
3. `t_command` vide ;
4. une seule demande `TURN_OFF_HEATERS` ;
5. buse et plateau réellement demandés à zéro.

Si la route reste engagée, le garde termine en timeout KO sans retry.

## Travail livré

Le paquet
`packages/k1-control-v1/cfs-stock-unload-guard-live-preflight-v1/` contient :

- `capture_live_preflight.ps1` : collecteur live strictement en lecture seule ;
- `verify_private_capture.py` : vérificateur avec sortie nettoyée ;
- `evidence-map.json` et `contract.json` : preuves, mapping et autorité ;
- `README.md`, `RESULT.md` et `NEXT-ADAPTER-OFFLINE.md`.

Le garde précédent, ses scénarios et ses contrats sont alignés sur les champs
réels. ADR-025, D-075, le document 36 et les documents de pilotage sont publiés.

## Vérifications

- vérificateur privé :
  `VERIFY_CFS_STOCK_UNLOAD_GUARD_LIVE_PREFLIGHT_V1_OK` ;
- tests du garde : `18/18` verts ;
- tests du préflight live : `12/12` verts ;
- suite complète : `412` tests exécutés, `409` verts et `3` ignorés connus ;
- suite complète rejouée le 2026-08-27 pendant la clôture : même résultat,
  `OK (skipped=3)` ;
- configurations avant/après : identiques ;
- lecture live : OK ;
- action physique : non exécutée.

## Limites et risques

- L'état actuel ne contient aucune route engagée ; le chemin de succès ne peut
  donc pas être essayé aujourd'hui sans charger d'abord un filament.
- Aucun adaptateur réel n'est encore relié au contrôleur.
- Les délais entre les lectures et le transport Moonraker restent à construire.
- `t_command` ne prouve pas l'avancement du retrait stock.
- La coupe n'a pas de capteur indépendant.
- Le segment après cutter reste dans la tête.
- Aucun slot autre que l'ancien `T1A` n'a été physiquement qualifié.
- Un nouvel essai réel reste interdit.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`

En langage courant : construire uniquement sur l'ordinateur le petit
traducteur qui transforme une réponse K1 nettoyée en données comprises par le
garde. Par exemple, `box.T1.filament=A` deviendra la route `T1A`.

Cette étape est utile pour tester toutes les traductions avant de brancher quoi
que ce soit sur la machine. Elle couvrira une route absente, unique ou ambiguë,
un CFS déconnecté, une réponse incomplète et des températures invalides.

Le prochain GO exact autorisera seulement du code et des tests locaux sur des
exemples sans identité matérielle. Il n'autorisera aucune connexion K1, aucun
G-code et aucun retrait réel.

Critères de fin :

1. aucune identité privée dans les exemples versionnés ;
2. traduction déterministe des unités, routes, commandes et températures ;
3. refus des données absentes, ambiguës ou invalides ;
4. aucun module réseau ou moyen d'envoyer un G-code ;
5. tests du garde et suite complète verts ;
6. prochaine gate réelle préparée mais non autorisée.

## Modèle conseillé pour la reprise

- Optimal : `gpt-5.6-terra`, raisonnement `high`, car la prochaine mission est
  locale, bien bornée et dispose désormais de champs réels clairement mappés.
- Option plus sûre si l'adaptateur grandit ou touche aussi le transport :
  `gpt-5.6-sol`, raisonnement `high` ; compromis : coût supérieur pour un travail
  qui devrait rester purement déterministe.

## Autorisation de démarrage

**ATTENDRE_GO.** La gate live est close et son GO est consommé. Rien dans cette
passation n'autorise une nouvelle connexion K1, un G-code, un retrait, une
chauffe, une pose ou un restart.
