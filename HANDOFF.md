# HANDOFF — retrait officiel CFS qualifié, garde stock à construire

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Mission terminée : `G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`

## État à annoncer immédiatement à Thomas

- **Le retrait officiel du filament `T1A` a réussi.**
- Le CFS 1 est passé du slot A chargé à aucun filament engagé.
- La commande Creality a chauffé automatiquement la buse à `220 °C` pendant
  son cycle : aucune chauffe manuelle préalable n'était nécessaire.
- La commande constructeur a terminé en laissant la consigne à `220 °C`.
  Codex a donc envoyé `TURN_OFF_HEATERS`, puis vérifié une consigne finale à
  zéro. La buse était à `81,42 °C` et continuait de refroidir lors du dernier
  relevé.
- Le capteur de la tête reste occupé : le petit morceau situé après le cutter
  est encore dans la tête. Le retrait CFS réussi ne signifie donc pas que la
  buse est entièrement vide ou nettoyée.
- Le cutter fait partie de la séquence officielle, mais aucun capteur dédié ne
  permet de prouver séparément son mouvement physique.
- La capture passive est **OK**. En revanche, le protocole série indépendant
  reste **KO borné** et `callable_messages=[]` reste vide.
- La voie la plus fiable à court terme est d'encadrer la commande officielle
  Creality, pas d'imiter dès maintenant ses messages série internes.
- L'autonomie production reste non atteinte et la production reste fermée.
- `MESH-EDGE-DIAGNOSTIC-V1` reste suspendue. Son rollback et son audit CFS
  n'autorisent aucune reprise : le profil diagnostic et quatre G-code sont absents.
- `VALIDATE_MESH_EDGE_DIAGNOSTIC_V1_OK` reste son marqueur de fermeture valide.
- Les quatre G-code ne doivent pas être recréés depuis ce handoff.
- Toute future action physique exige une route fraîche et, si le plateau est
  concerné, la confirmation « plateau réellement libre ».
- Aucun `GO` exact antérieur ne couvre une nouvelle connexion ou une nouvelle
  action physique.
- Autorisation suivante : **ATTENDRE_GO**.

## État Git

- SHA initial local et distant :
  `3ab0f468ca6cfcf85bd388175bc2d12b06aa4c67`.
- Commit principal de mission :
  `bbb92a2dc0d1c51d5600355ae6092db38e17b1ab`.
- Ce commit est publié sur `origin/main`.
- Branche de mission séparée : aucune.
- Worktree de mission séparé : aucun.
- Autre worktree observé : aucun.
- Le SHA final de cette passation doit être lu après son propre commit et son
  envoi.

## Action réelle exécutée

Le préflight en lecture seule a confirmé une K1 au repos, les chauffes demandées
à zéro, deux CFS connectés et la route fraîche `T1A`.

Codex a lancé une seule fois la commande officielle `BOX_QUIT_MATERIAL` par
l'API Moonraker. Aucune trame série brute n'a été injectée. La macro installée
sur la K1 enchaîne les opérations Creality de vérification, coupe, retrait et
retour de la tête à la position de chargement.

Le cycle a duré environ `105,88 s`. La capture contient deux demandes de retrait
et leurs deux réponses de succès. Le capteur local du wrapper est ensuite passé
à libre et l'état privé du CFS est passé de `T1A` à aucun filament engagé.

## Point de sécurité thermique

La séquence stock a porté automatiquement la consigne de buse à `220 °C`, mais
ne l'a pas remise à zéro à sa fin.

Une première tentative locale a envoyé par erreur `M104%20S0`. L'API HTTP a
répondu `ok`, alors que le journal Klipper a montré `Unknown command:M104%20` :
la chauffe n'avait donc pas été coupée. La vérification de l'effet réel a évité
de prendre cette réponse HTTP pour un succès.

Codex a alors envoyé la commande sans ambiguïté `TURN_OFF_HEATERS`. Le journal a
confirmé sa fin et l'état final a confirmé les deux consignes à zéro.

Décision importante : le prochain contrôleur devra toujours vérifier le résultat
réel sur la machine, y compris après une réponse HTTP positive, et couper les
chauffes même si le retrait échoue au milieu.

## État final observé de la K1

- impression : `standby` ;
- consigne buse : `0 °C` ;
- température buse au dernier relevé : `81,42 °C`, en refroidissement ;
- consigne plateau : `0 °C` ;
- axes : toujours référencés `xyz` ;
- deux CFS : connectés ;
- commande CFS en cours : aucune ;
- route `T1A` : libérée ;
- capteur de filament de la tête : encore occupé ;
- `printer.cfg`, `gcode_macro.cfg` et `box.cfg` : empreintes inchangées.

Les messages d'erreur et d'absence de réponse déjà présents en arrière-plan sur
le bus CFS continuent avant, pendant et après le retrait. Aucun arrêt, traceback
ou échec du retrait n'apparaît, mais ce bruit de fond devra être diagnostiqué à
part : il n'est pas déclaré sans danger par défaut.

## Preuves privées

Session privée :
`inventory/raw/20260827-001616-g4-k1-control-cfs-minimal-owner-passive-capture-v1`

Les données brutes restent ignorées par Git. Seuls les faits utiles, les numéros
de lignes et les empreintes sont publiés. Aucun identifiant matériel privé ni
trame d'identité n'a été ajouté aux fichiers versionnés.

Empreintes principales :

- capture passive :
  `995b94f92928d2f2d048f677b7183201b6b370cc70f6ccd34c70534b4cffcfe2` ;
- état CFS avant :
  `74bfaaae68ca7dc6f989bf4568ed97a761cb3ae9c85f132c376a65b0d8172d39` ;
- état CFS après :
  `94e8c905a79cf087c2c638b1112e3901cc38cdfcfd7bc353bb82920d554caf2b` ;
- état final machine :
  `626b612802835a115a68fcd013f91cfabfb7c0de39d67bde5e990f800d3ac7c1`.

## Travail livré

Le paquet
`packages/k1-control-v1/cfs-minimal-owner-passive-capture-v1/` contient :

- `contract.json` : autorité, résultat et limites ;
- `evidence-map.json` : carte des preuves privées sans données identifiantes ;
- `verify_private_capture.py` : vérification déterministe de la capture privée ;
- `README.md` et `RESULT.md` : utilisation et verdict ;
- `NEXT-STOCK-UNLOAD-GUARD.md` : contrat de la prochaine étape hors imprimante.

La décision est enregistrée dans :

- `docs/34-capture-retrait-officiel-cfs-v1.md` ;
- ADR-023 ;
- D-073 ;
- `design/job-lifecycle-contract-v1.json` ;
- `AGENTS.md`, `STATE.md`, `GATES.md`, `ROADMAP.md` et les index du projet.

## Vérifications

- vérificateur privé : `VERIFY_CFS_MINIMAL_OWNER_PASSIVE_CAPTURE_V1_OK` ;
- tests ciblés : `15/15` verts ;
- suite complète : `382` tests exécutés, `379` verts et `3` ignorés connus ;
- contrôle des espaces et fins de lignes Git : OK ;
- recherche d'identifiants privés connus dans les nouveaux fichiers : aucun
  résultat ;
- empreintes des trois configurations K1 avant/après : identiques.

## Limites et risques

- Le morceau de filament après le cutter est toujours détecté dans la tête.
- La coupe physique n'a pas sa propre preuve capteur.
- La macro stock n'a pas coupé seule sa chauffe dans ce passage.
- Une réponse HTTP `ok` ne prouve pas que le G-code a été compris.
- Les slots B/C/D et le second CFS n'ont pas été retirés pendant cette mission.
- Le protocole série complet, l'arrêt en faute, la reconnexion et l'exclusion du
  propriétaire constructeur restent non qualifiés.
- Aucun transport autonome, paquet installable ou changement de production n'a
  été créé.

## Prochaine mission unique

### `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-V1`

En langage courant : construire d'abord, uniquement sur l'ordinateur, un petit
contrôleur autour de la commande Creality existante. Il devra vérifier que la K1
est au repos et que le bon slot est réellement engagé, lancer le retrait une
seule fois, attendre la vraie libération du slot, détecter un faux succès HTTP,
et remettre les chauffes à zéro même si une erreur survient.

Cette étape sert à rendre le retrait officiel reproductible et plus sûr sans
réinventer le protocole interne du CFS. Elle sera testée contre une fausse API :
elle ne se connectera pas à la K1 et ne déplacera aucun filament.

Le futur GO exact de cette mission autorisera seulement la construction et les
tests hors imprimante. Une connexion à la K1 ou un nouveau retrait réel
demandera ensuite une autorisation distincte, après revue du contrôleur figé.

Critères de réussite hors imprimante :

1. refus si la machine n'est pas au repos ou si la route est ambiguë ;
2. un seul lancement de `BOX_QUIT_MATERIAL` ;
3. succès seulement si le slot est réellement libéré ;
4. `TURN_OFF_HEATERS` exécuté dans tous les chemins de sortie ;
5. faux `ok` HTTP détecté ;
6. message clair indiquant que le segment dans la tête peut rester présent ;
7. aucun accès réseau réel dans les tests.

## Modèle conseillé pour la reprise

- Optimal : `gpt-5.6-sol`, raisonnement `high`, car le contrôleur devra gérer
  sans ambiguïté la chauffe, les erreurs partielles et la différence entre une
  réponse HTTP et un effet réellement observé.
- Option économique : `gpt-5.6-terra`, raisonnement `high`, raisonnable pour la
  construction hors imprimante ; compromis : davantage de risque de manquer un
  cas de panne et de devoir reprendre la logique de sécurité.

## Autorisation de démarrage

**ATTENDRE_GO.** La mission de capture est close. Rien dans cette passation
n'autorise une nouvelle connexion à la K1, un autre cycle filament ou une pose
sur l'imprimante.
