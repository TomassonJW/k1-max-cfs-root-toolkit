# HANDOFF — index de reprise

## 22 septembre — V3 : purge et retrait confirmés ; arrêt envoyé par Codex

Thomas confirme la purge puis le rembobinage. La tête se libère environ 0,9 s
après le lancement CFS ; l'extrudeur reste programmé pour 7,5 s, comme la
primitive constructeur. Codex envoie M112 après une image masquée par une main,
puis le surveillant renvoie un arrêt à tort après shutdown. La fin complète
et le parc restent non qualifiés. Accès récupéré sans effet physique :
ready/standby, cibles zéro, tête libre, deux CFS connectés sans route, axes
non référencés. Pas de nouvelle palpation sans nettoyage frais. Pilote V3 clos,
interdit de rejeu ; politique locale d'arrêt unique/pause froide testée.
Lire [le document 95](docs/95-essai-v3-retrait-observe-arret-codex.md).

## 22 septembre — essai V2 clos KO au chargement ; machine récupérée

Dernier état : Thomas confirme finalement redémarrage, retrait terminé et
nettoyage buse/plateau. Une lecture et la caméra confirment tête libre, aucune
route, cibles zéro, XY seuls référencés. Le filament est récupéré manuellement ;
le démarrage intermittent et le retrait automatique restent non qualifiés.

Actualisation : récupération logicielle seulement. Thomas signale le retrait
officiel encore indisponible et un nouveau redémarrage nécessaire. La capture
passive suivante voit coupe puis retrait depuis l'interface, buse en chauffe
vers 200 °C, tête encore chargée ; fin non confirmée. Aucun nouvel essai lancé.

Le surveillant a envoyé l'arrêt d'urgence après huit messages full alors que
le capteur de tête était actif depuis 33,449 s et E encore commandé à 3 mm/s.
Pas d'erreur console avant cet arrêt ; débit physique non confirmé. Ni pause
prévue ni retrait V2 exécutés. L'ancien surveillant était trop large : ne pas
rejouer cet essai ou désactiver simplement sa protection.

Service Klipper puis verrou MCU récupérés sans commande physique. État final
ready/standby, chauffes zéro, tête chargée, aucune route déclarée après reset,
axes non référencés ; 22 empreintes inchangées. Aucun retrait ni nouvel essai.
La buse n'est plus réputée propre pour une palpation après cette insertion.
Le diagnostic du chargement et la récupération filament restent nécessaires.
Le successeur local startup-grip-observer-v2 distingue les phases : 89 tests
verts et rejeu de trois captures. Il conserve les deux chargements réussis
et arrête encore le cas actuel, dont la route n'était pas confirmée. Thomas
pense qu'aucun filament n'est sorti sans en être certain ; nouvel essai demandé,
mais retrait officiel surveillé et nettoyage restent à confirmer d'abord.
Lire [le document 94](docs/94-essai-v2-arret-surveillant-chargement.md).


## 21 septembre — retrait coordonné V2 installé ; essai physique restant

Récupération manuelle terminée après extinction/rallumage : la coupe officielle
a été sautée sur capteur de tête vide, puis le CFS a répondu OK au retrait.
L'effort moteur rapporté ne prouve ni dommage ni absence de dommage. V1 était
revenu idle au reboot ; les anciennes mentions « retrait en attente » et
« V1 verrouillé en échec » ci-dessous décrivent l'état historique du KO.

Sur le GO suivant, V2 est posé à froid : un fichier remplacé, backup V1 exact,
nouveau processus Klipper confirmé, 22 empreintes et validation indépendante
vertes. 199 tests ciblés passent. Version end-overlap-v2 active/idle,
physical_validation=false. Aucun mouvement commandé ni chauffe ; caméra
avant/après examinée. Aucun mesh actif et offsets zéro conservés tels que
trouvés après le reboot manuel ; axes désormais non référencés.

Buse sale, plateau propre mais haut : aucun palpage ni nouveau cycle à ce
stade. Le prochain geste est un nettoyage frais de la buse avant préparation
des références puis du cycle intégré supervisé. Ne pas rejouer le test V1.
Lire [le document 93](docs/93-retrait-cfs-chevauchement-v2-pose.md).


## 21 septembre — essai retrait séparé KO ; chevauchement corrigé hors imprimante

Coupe/relâchement OK, tête restée au cutter, retrait T1B refusé key849/0x19 ;
CFS rouge, aucun rembobinage visible, tête encore détectée chargée. Chauffes
zéro, Klipper prêt, phase failed, sans M112 ni nouvel essai. V1 reste installé
et verrouillé en échec. Le M400 ajouté après les deux rétractions supprimait
le chevauchement des 15 mm lents avec le CFS : différence réelle confirmée.
V2 corrige cet ordre localement, 170 tests ciblés verts avec une vraie file
simulée et un témoin négatif V1. Non installé, pas encore de paquet de pose.
Retrait officiel de récupération demandé ; résultat humain encore attendu.
Lire [le document 92](docs/92-retrait-cfs-chevauchement-moteurs-v2.md).


## 21 septembre — retrait CFS séparé installé et actif, validation physique restante

La mission « prépare puis installe directement, GO » est close côté pose :
`separated-end-v1` remplace deux fichiers, est actif et au repos. 22 empreintes
et deux backups exacts confirmés indépendamment ; tête vide, aucune route,
chauffes zéro, axes libérés. Aucun mouvement ni essai physique pendant la pose.
Profil `default` et offsets XYZ zéro réellement observés conservés sans mouvement.
Lire [le document 91](docs/91-retrait-cfs-separe-installe-a-froid.md) et le paquet
`packages/k1-control-v1/end-separated-v1/` pour la reprise et le rollback.
Les essais V1/R2 sont clos KO ; ne pas les rejouer. Le nouveau retrait supprime
le trajet au bac, vérifie les ACK et attend l'état CFS. Sa qualification
physique reste à faire ; le chargement intermittent n'est pas déclaré corrigé.
142 tests ciblés verts ; suite complète 1668 verts, les deux échecs historiques,
2 xfail et 55 sous-tests verts. Ne pas relever le plateau depuis une position
incertaine. Aucun nouveau GO technique nécessaire pour achever la pose autorisée.



21 septembre, pose réalisée. **Fin CFS installée désactivée et validée à froid**
(document 87, capture `20260921-cfs-end-disabled-install`). La récupération
manuelle du matin était bien terminée : aucune pause/route, tête vide, chauffes
zéro. Les 24 chemins correspondent ; sept fichiers posés, transition réelle
Klipper et deux validations froides, puis contrôle HTTP indépendant et navigateur
réel Bobines/Mainsail. Aucun mouvement ni chauffe. Géométrie initiale inactive/Z
zéro préservée, garde de pose corrigée pour ne pas imposer l’état historique.
`kctrl_end.enabled=false`, aucun travail de fin pendant, porte normale disponible.
Reste la qualification active du cycle ; l’état matériel n’est pas bloqué.

## 21 septembre — interface et paquet désactivé prêts, aucune connexion K1

Lire `docs/86-fin-cfs-interface-et-paquet-desactive-v1.md` et le README de
`packages/k1-control-v1/end-after-refill-install-disabled-v1/` avant la suite.
La mission suivante est le préflight frais puis la pose désactivée, avec les
sept fichiers du manifeste et le plan ordonné versionné. Les bases UI/porte
sont attendues depuis le dépôt, pas encore confirmées sur la machine ; tout
écart impose un arrêt avant remplacement. Générateur hors réseau, pas un
déployeur automatique. La nouvelle UI et la porte sont testées localement :
203 tests Python ciblés, 33 Node. Aucun changement physique ni distant.
Le défaut actuel reste installé. Pas d'activation par simple changement de
configuration ; qualification caméra du cycle réel encore distincte.


## 21 septembre — qualification froide close, correctif cutter révisé

Lire le [document 85](docs/85-qualification-firmware-fin-cfs-lecture-seule-v1.md)
et le [manifeste nettoyé](inventory/redacted/20260921-cfs-end-cold-v1/qualification.json).
Le GO suivant a autorisé la lecture seule du firmware ; aucun effet machine.
16 empreintes inchangées, cibles zéro, axes libérés, capteur de tête vide,
T1/T2 sans route, `kctrl_end` non chargé.

Deux questions fermées pour le hash épinglé : `if_in_resume` retourne bien
`do_resume_status` ; le relâchement cutter arrive après retrait dans le journal
manuel. Le candidat attendait ce relâchement trop tôt : corrigé et reproduit
avec les vrais temps. Confirmation de coupe avant retrait, relâchement avant
fin stock, sans retry. 72/72 tests, dont six avec le répartiteur exact ; suite
complète 1 538 verts, deux échecs antérieurs, deux xfail, 55 sous-tests verts.

Suite unique utile : raccordement de l'état de fin à l'UI et paquet de pose/
rollback avec empreintes et validation désactivée. Ne pas répéter la collecte
close. Ne pas activer par simple toggle. Aucun nouveau END_PRINT différé n'a
été testé physiquement ; la trace de récupération était un retrait manuel
sans TNN. Une future qualification complète exigera caméra et présence utile.
Modèle conseillé pour cette préparation : GPT-5.6 Sol/high ; Sol/medium possible
pour l'affichage seul, conserver high pour pose et retour arrière.

Les points de reprise précédents ci-dessous sont historiques.

## 21 septembre — correctif préparé et testé, aucune connexion ni installation

Point de reprise actuel : [document 84](docs/84-correctif-fin-apres-releve-hors-imprimante-v1.md),
[contrat candidat](packages/k1-control-v1/owned-start-print-v2/end-after-refill-candidate.md)
et ADR-069 retenue hors imprimante. GO de Thomas consommé pour construction et
validation locale uniquement. `kctrl_end.py` et sa configuration désactivée
sont séparés des macros installées, qui restent inchangées.

66 tests ciblés verts : relève interne A → B, deux CFS, reprise, preuves de
coupe, température, annulation, délai, erreurs et absence de retry. Suite locale :
1 532 réussis, 2 échoués préexistants, 2 échecs attendus, 55 sous-tests verts.
Les deux échecs sont reproduits sur une copie de la base `6fd0f7e` ; la CI les
connaissait déjà. Aucun test assoupli et aucun firmware constructeur publié.

Suite recommandée : qualification à froid en lecture seule du firmware exact
et de l'intégration ; isoler ce qui exigera ensuite une preuve physique.
`do_resume_status=False` ne prouve pas encore le prédicat compilé `if_in_resume`.
La disponibilité de tous les marqueurs cutter et l'affichage de la fin différée
restent à traiter avant pose/activation. Le module n'arrête pas à lui seul un
moteur CFS autonome déjà en marche. Le défaut de fin installé reste présent.
Pas d'effet filament, de remise à zéro arbitraire du firmware ni de simple toggle
`enabled: true`. Modèle conseillé : GPT-6 Astra/high ; Sol/high possible pour
la collecte bornée, avec revue approfondie avant activation.

Les entrées suivantes sont historiques.

## 21 septembre — incident après relève T1A → T1B, diagnostic clos ; correction proposée

Lire d'abord le document 83 et l'ADR-069 **proposée**. La fin validée le 15
ne couvre pas la relève automatique : le 18, cache T1A obsolète, coupe refusée
« In resume », rembobinage néanmoins demandé à A, tête encore chargée, puis
`BOX_END`. Le `10h37m` a atteint `END_PRINT` ; l'historique reste ouvert
jusqu'à l'annulation manuelle du 21. Thomas confirme avoir rembobiné T1B.

Suite : construire hors imprimante une fin fondée sur la route fraîche,
une coupe confirmée et un arrêt thermique garanti. Qualifier le prédicat
stock `if_in_resume` et le résultat de coupe avant toute nouvelle séquence.
Ni forcer T1B, ni désactiver la relève, ni remettre arbitrairement un attribut
stock à zéro. Trois reproductions synthétiques privées, 21 assertions de fin
et 7 tests de bornage verts ; aucun code de commande modifié, aucune pose.
Capture privée `inventory/raw/20260921-cfs-end-incident/` ; les six empreintes
contrôlées sont inchangées. Le `12h34m` existe dans l'historique mais plus au
chemin G-code exact fourni. Les points du 15 ci-dessous restent historiques.


## 15 septembre, 19:00 — audit de l'impression de 18:02 (document 82) : fin propre en 42 s (ADR-067 validée), zéro pause, zéro silence du bus ; relances de chargement, 5 sur 6 depuis le CFS 1

**Point de reprise, dans l'ordre :**

1. **Relances de chargement** (document 82, section 8, geste 1) : Thomas
   échange une bobine entre le CFS 1 et le CFS 2 (le noir en `T2B`, le bleu
   en `T1A`) et charge chacune trois fois depuis l'écran. Si la relance suit
   l'unité, regarder le tube CFS 1 → hub et l'entrée du hub. Deux impressions
   cumulées : CFS 1, 5 relances sur 6 chargements ; CFS 2, 1 sur 7. Un
   chargement raté coûte 85 à 90 s.
2. **Garde du bus, preuve décisive encore à venir** : l'impression de 18:02
   n'a eu qu'un rapport du capteur fini par `F7` (question suivante retenue
   314 ms, répondue) ; le cas du matin, rapport toutes les 5 s en veille et
   question au CFS 2 derrière, ne s'est pas présenté. À la prochaine veille :
   `http://192.168.1.64:4409/printer/objects/query?serial_485+serial485`
   (`kctrl_marked`, `kctrl_held`), puis `bus.sh` et `silences_cfs.py`.
3. **Fin d'impression** : validée sur une fin réelle (`T2B`, 18:28) ; reste
   à observer une fin avec `filament_useup` à 1 (le cas du matin), l'audit
   en direct alerte si la boucle revient.
4. **Lectures du journal** : seulement par les scripts bornés ou une fenêtre
   `dd` écrite à la main ; jamais `tail -n N` ni `grep` sur `klippy.log`.
   Recette d'audit d'une impression : document 82, section 2.

### Fait (vérifié)

- **Document 82** : `MultiColo_Cube_PLA_15m31s.gcode`, 18:02:28 → 18:28:29,
  26 min 01 s, `completed`, cinq `T`, 0 pause, 0 code CFS, `key61` bruit
  connu. Fin : « retrait (fin) de T2B … coupe, puis rembobinage » à
  18:27:47, « fait, tete vide » à 18:28:15 (28 s), `box_end` → `Exiting` en
  14 s, 0 tronçon, aucune alerte au rejeu de `audit_live.py`. Bus : 1 218
  questions au CFS 2, 0 muette, 0 CRC faux ; compteurs `calls` 3 911,
  `seen` 3 108, `marked` 3, `held` 1, `unknown` 0. Changements : 290, 284,
  200, 201 s ; purge 280 mm (2 min 14 s) à chaque fois ; relances sur
  `T1A`, `T2D`, `T1D` (sept poussées avant le capteur de tête, « buffer is
  always full »).
- ADR-067 validée, ADR-068 première impression sans pause ni silence ;
  documents 80 et 81 mis à jour. Machine : `standby`, buse froide, 99 Mo
  disponibles, `filament_useup` à 0.

### Décisions

- Aucune commande envoyée à la machine pour cet audit ; lectures bornées
  (28 Mo) et rejeu hors dépôt.

## 15 septembre, 18:00 — garde du bus posée et vérifiée au repos (ADR-068), macros de fin essayées à blanc ; tout est en place, la prochaine impression tranche

**Point de reprise, dans l'ordre :**

1. **Prochaine impression, du départ à la fin, avec l'audit en direct**
   (`scripts/audit-en-direct/audit-live.sh` lancé avant le départ). Deux
   choses à trancher :
   - **Pauses `key831`** (garde du bus, ADR-068). Pendant l'impression,
     `http://192.168.1.64:4409/printer/objects/query?serial_485+serial485`
     doit montrer `kctrl_marked` > 0 et `kctrl_held` égal ; aucune pause
     `key831`. Après l'impression, hors dépôt :
     `ssh k1max-root 'sh -s' < scripts/audit-en-direct/bus.sh > bus.txt`
     puis `py -3.10 scripts/audit-en-direct/silences_cfs.py bus.txt` :
     zéro question muette après une trame finie par `F7`. S'il en reste,
     allonger `HOLD_S` (300 ms) dans le fichier, ou la cause est ailleurs
     (`--detail`).
   - **Fin d'impression** (ADR-067). À la console : « K1 Control: retrait
     (fin) de Txx (…) : coupe, puis rembobinage », « retrait (fin) de Txx
     fait, tete vide », puis « box_end -> Exiting en N s, 0 tronçon(s) »
     sans ALERTE. Si une ALERTE « extrude all material » ou « boucle de fin »
     tombe : annuler depuis l'écran, sinon arrêt d'urgence ; la Pause ne fait
     rien. Ce que fait `BOX_END` devant une tête vide est l'inconnue
     (document 81, section 4).
2. **Retour arrière de la garde**, si Klipper ou le bus font autre chose que
   d'habitude :
   `ssh k1max-root 'cp /usr/share/klipper/klippy/extras/serial_485.py.bak-20260915 /usr/share/klipper/klippy/extras/serial_485.py && /etc/init.d/S55klipper_service restart'`.
3. **Lectures du journal** : seulement par les scripts bornés (`purges.sh`,
   `bus.sh`, les deux `.ps1` d'audit) ou une fenêtre `dd` écrite à la main ;
   jamais `tail -n N` ni `grep` sur `klippy.log`. Au repos, le journal grossit
   d'environ 330 Ko par minute (une ligne par trame du bus) : 8 Mo font
   24 minutes.
4. Inconnues restantes, observation seulement : la boucle d'adressage du bus
   (`Error: no response` toutes les ~2 s, adresses 3 et 4 absentes, 137 par
   Mo de journal), `box.filament_useup` encore à 1 au repos, la condition
   exacte de la branche « extrude all material ».

### Fait (vérifié)

- **Garde du bus posée** (document 80, remède 3 ; ADR-068) :
  `/usr/share/klipper/klippy/extras/serial_485.py` remplacé (sauvegarde
  `.bak-20260915`, le stock de deux lignes), poses à 17:44, 17:47 et 17:52
  (forme finale, `md5 b2c2f42b…`, identique au dépôt), Klipper prêt à
  17:52:55, ligne « kctrl serial_485: garde de 300 ms » au journal, aucune
  erreur. Compteurs dans l'objet `serial_485 serial485` : `kctrl_calls`
  44 → 121 en 40 s (les questions du module compilé passent par la garde),
  `kctrl_seen` 30 → 87 (la forme de la réponse est lue), `unknown` 0 ;
  `marked` et `held` à 0 au repos, normal (aucune réponse finie par `F7`
  sans impression) ; `silences_cfs.py` de 17:47 à 17:50 : 37 questions au
  CFS 2, 0 muette. 8 tests sur faux transport ; README du paquet.
- **Macros de fin essayées à blanc** à 17:49, tête vide, au repos :
  `_KCTRL_UNLOAD REASON=essai` → « capteur de tete deja vide, rien a
  couper », `last` = `vide` ; `_KCTRL_UNLOAD_CHECK TOOL=T1A REASON=essai` →
  « retrait (essai) de T1A fait, tete vide ». Rien n'a bougé ni chauffé.
- Moonraker de la machine : `printer/gcode/script` ne prend que la forme
  `?script=…` avec `+` pour les espaces (le corps JSON répond « Missing
  Argument [script] ») ; `objects/list` ne liste que les objets qui ont un
  `get_status`, d'où l'absence de `serial_485` avant la pose. Le port 4409
  relaie `printer/objects/query` depuis le réseau.
- Suite complète : 1 466 tests verts, les deux rouges volontaires de la CI
  inchangés. Machine : `standby`, buse froide, 102 Mo disponibles.

### Décisions prises sans demander

- Deux G-code envoyés à la machine pour l'essai à blanc (ci-dessus), sans
  mouvement ni chauffe par construction (tête vide) ; le rendu réel des
  modèles valait la vérification après l'incident de 14:00.
- Une seule attente par réponse finie par `F7` : la garde est levée une fois
  la question retenue partie, la réponse suivante en ouvre une autre. Sur la
  machine le comportement est le même ; un test le fixe.

## 15 septembre, 14:20 — la fin d'impression vide la tête par nos soins (ADR-067, posé à 14:03), lectures du journal bornées, alertes de fin dans l'audit ; garde du bus écrite, pas posée (document 81)

**Point de reprise, dans l'ordre :**

1. **Prochaine fin d'impression, à observer.** Lancer
   `scripts/audit-en-direct/audit-live.sh` avant la fin. Attendu à la console
   et dans l'audit : « K1 Control: retrait (fin) de Txx (…) : coupe, puis
   rembobinage », « retrait (fin) de Txx fait, tete vide », puis « fin
   d'impression : box_end » et « box_end -> Exiting en N s, 0 tronçon(s) »,
   sans ALERTE. Si une ALERTE « extrude all material » ou « boucle de fin »
   tombe : annuler depuis l'écran, sinon arrêt d'urgence ; la Pause ne fait
   rien. Ce que fait `BOX_END` devant une tête déjà vide est l'inconnue à
   lever (document 81, section 4).
2. **Décision de Thomas sur la garde du bus** (document 80, remède 3).
   Fichier prêt et testé : `packages/k1-control-v1/cfs-bus-guard-v1/serial_485.py`
   (remplace `/usr/share/klipper/klippy/extras/serial_485.py`, deux lignes en
   stock). Pose machine à l'arrêt, avec `.bak-<date>`, puis `silences_cfs.py`
   sur la prochaine impression via `scripts/audit-en-direct/bus.sh`.
3. **Lectures du journal** : seulement par les scripts bornés (`purges.sh`,
   `bus.sh`, les deux `.ps1` d'audit) ou une fenêtre `dd` écrite à la main ;
   jamais `tail -n N` ni `grep` sur `klippy.log`.
   `tests/test_lectures_journal_bornees_v1.py` l'impose dans le dépôt.
4. Inconnues restantes, machine au repos : la boucle d'adressage du bus
   (`Error: no response` toutes les ~2 s depuis 12:43), la condition exacte
   de la branche « extrude all material », le `timeout` du bus à 12:03:17.

### Fait (vérifié)

- **Document 81** : chronologie du 14 (fin en 49 s) et du 15 (25 tronçons,
  ~2 m, Pause sans effet, plantage causé par notre `tail -n`, deux retraits
  ratés), fin stock démontée, hypothèse de la bobine « finie », correctifs.
  La tête à la purge après un rembobinage est la séquence stock
  (`BOX_QUIT_MATERIAL` finit par `BOX_GO_TO_BOX_EXTRUDE_POS`).
- **ADR-067, posé à 14:03** (première pose à 14:00 en erreur : un ` ;` dans
  un message, Klipper coupe les ` ;` en ligne ; corrigé, test ajouté). Klipper
  prêt à 14:04:02, `_KCTRL_UNLOAD` et `_KCTRL_UNLOAD_CHECK` présents,
  `START_PRINT.active_tool` ajouté. 21 tests.
- **Lectures bornées** dans les deux `.ps1`, `purges.sh`, `bus.sh` (nouveau) ;
  7 tests qui balaient `scripts/` et `packages/`.
- **Alertes de l'audit** : rejeu du 15 (alertes à 12:03:20, 12:04:05,
  12:04:45, 12:05:47, tous les 5 tronçons, Pause à 12:19:07) et du 14 (aucune
  alerte, `Exiting` en 49 s). 7 tests.
- **Garde du bus** : enveloppe + 6 tests sur faux transport ; rien posé.
- Suite complète : 1 464 tests verts, les deux rouges volontaires de la CI
  inchangés. Machine : `T1A` rembobiné à 13:23 par Thomas, `standby`,
  buse froide, 102 Mo de mémoire disponible.

### À savoir

- `BOX_RETRUDE_MATERIAL` seul ne fait rien après un redémarrage
  (`last_tnn: None`) : toujours nommer l'emplacement,
  `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=Txx`, ou `_KCTRL_UNLOAD TOOL=Txx
  REASON=manuel` qui coupe d'abord.
- Klipper lit le cfg avec `inline_comment_prefixes=(';', '#')` : aucun ` ;`
  ni `#` dans une chaîne de macro.
- Captures brutes hors dépôt : dossiers brouillon des sessions `1fcc4b93`
  (`logs/fin3.txt`) et `45b6ec41` (`fin14.txt`, rejeux) dans le Temp de
  Claude.

## 15 septembre, 13:15 — fin d'impression en boucle, plantage de Klipper causé par notre lecture du journal, retrait `T1A` bloqué (document 81 à écrire)

**Point de reprise, dans l'ordre :**

1. Avec Thomas, rembobiner `T1A`. Le filament a été coupé à 12:50 mais pas
   rembobiné, et la tête est garée en X38 Y100. Voie d'ADR-044 :
   `BOX_ERROR_CLEAR`, `M109 S220`, puis `BOX_RETRUDE_MATERIAL_WITH_TNN TNN=T1A`.
   Tout G-code envoyé par l'agent attend l'accord de Thomas. Si l'écran reste
   figé : redémarrer la machine (l'impression est finie).
2. Borner les lectures du journal de la machine (voir « Danger ouvert ») et
   ajouter un test qui l'impose.
3. Ajouter les alertes à `scripts/audit-en-direct/audit_live.py`, avec un test
   sur lignes synthétiques.
4. Écrire le document 81, au format du document 80.
5. Machine au repos, en lecture bornée : chercher « extrude all material » dans
   les journaux tournés, et comprendre la boucle d'adressage du bus depuis 12:43.

Le point de reprise du document 80 reste valable : accord de Thomas sur le
remède 3.

### Fait (vérifié dans le journal)

- **Boucle de fin d'impression.** À 12:03, fin de l'impression
  `…Shell_PLA_8h16m`. `box_end` prend la branche « extrude all material,
  last_cmd: T1A », jamais vue le 14. Le 14, la fin normale coupe, rembobine et
  se termine 49 s après `box_end`. Ici, le module pousse des tronçons de 80 mm
  à 2 mm/s, toutes les ~40 s, avec un « filament_sensor true » à chaque tour :
  25 tours de 12:04:05 à 12:20:12. Environ 2,0 m de `T1A` poussés (2 080 mm
  commandés).
- **Pause.** La Pause demandée par Thomas pendant la boucle n'est pas
  appliquée : la macro de fin tient la file G-code.
- **Plantage vers 12:20, causé par notre lecture.** À 12:19:44, nous lançons
  `tail -n 600000 klippy.log | grep`. La mémoire disponible tombe de 94,5 à
  9,8 Mo et le journal reste muet ~9 s. Ensuite : buse lue à 0 °C
  (`heater_fault`), MCU buse « Missed scheduling », `key294`, arrêt.
  « shutdown: Command request » est la propagation de l'arrêt, pas un M112.
- **Redémarrage.** Service puis `FIRMWARE_RESTART`, à la demande de Thomas ;
  prêt à 12:36:09. Le G-code de l'impression était fini : refuser toute reprise
  proposée.
- **Premier retrait, 12:49:32, depuis l'écran.** Coupe réussie à 12:50:04, puis
  la séquence s'arrête : aucun `BOX_RETRUDE_MATERIAL`.
- **Second retrait, 13:02:11.** « Cut sensor not triggered », `key841`, erreur
  Python `'NoneType' object has no attribute 'name'`, `macro_cut_err`.
  `BOX_RETRUDE_MATERIAL` rend la main en 4 ms sans rien faire. La tête se gare
  en X38 Y100, sans chauffe.
- **État à 13:12.** Klipper prêt, `standby`. Buse à 34 °C, cible 0. Tête en
  X38 Y100, Z non référencé. `box connect`, 115 Mo de mémoire disponible. Écran
  figé selon Thomas.
- **Rien d'autre n'a changé.** Ni la machine ni les outils du dépôt ne sont
  modifiés depuis le document 80. PR #67 (document 80 et cette passation)
  fusionnée.

### À savoir

- **Danger ouvert.** Trois scripts lisent encore `klippy.log` sans fenêtre
  bornée ni `nice` ; ne pas les lancer pendant une impression avant correction :
  - `scripts/run-k1-control-cfs-read-only-audit-v1.ps1`, lignes 111 à 123
    (`tail -n 160000`) ;
  - `packages/k1-control-v1/clean-and-reference-v1/capture_recent_cfs_history_read_only.ps1`,
    lignes 43 à 45 ;
  - `scripts/audit-en-direct/purges.sh`.

  Correctif prévu, en quatre éléments :
  - fenêtre `dd bs=1048576 skip=…` de 32 Mo au repos ;
  - 3 Mo seulement si `print_stats` vaut `printing` ou `paused` ;
  - `nice -n 19` ;
  - `cut -c1-600` avant tout `tail -n`.

  Le test associé exige `nice -n 19` et un produit lignes × largeur de 4 Mo au
  plus.
- **Alertes prévues dans `audit_live.py`, et quand elles se déclenchent :**
  - « extrude all material » pendant `box_end` ;
  - tronçons comptés seulement ensuite, car une fin normale écrit aussi deux
    « filament_sensor true » ;
  - `box_end` au-delà de 150 s ;
  - Pause pendant `box_end` ;
  - journal muet plus de 8 s alors que les lignes `Stats` tournaient ;
  - `memavail` sous 40 Mo.

  Vérification : rejouer la capture du 15 (alertes attendues) et le journal du
  14 (aucune alerte).
- **Hypothèses et inconnues.**
  - [HYPOTHÈSE] `box_end` a cru `T1A` épuisé, à cause de l'erreur de tension
    du CFS 1 active depuis 03:45:58 (document 80). Il a donc « tout vidé » :
    sans fin, puisque la bobine est attachée.
  - [HYPOTHÈSE] `BOX_RETRUDE_MATERIAL` ne fait rien parce que le module a perdu
    au redémarrage le filament chargé (`last_tnn: None`).
  - [INCONNU] la condition exacte de la branche « extrude all material » ;
  - [INCONNU] si la boucle s'arrête seule ;
  - [INCONNU] si l'arrêt d'urgence agit tout de suite sur ce firmware ;
  - [INCONNU] la cause de la coupe ratée de 13:02 ;
  - [INCONNU] la boucle « set slave addr / online check » toutes les ~2 s
    depuis 12:43 ;
  - [INCONNU] le client webhooks qui ferme sa connexion toutes les ~11 s à
    13:12.
- **Consigne à Thomas en attendant.** Si une fin d'impression pousse du
  filament en boucle : arrêt d'urgence, pas Pause.
- **Captures brutes, hors dépôt.** Dossier brouillon de la session `1fcc4b93`,
  dans le Temp de Claude : `logs/fin3.txt`, `crash.txt`, `stats485.txt`,
  `retrait.txt`, `retrait2.txt`.

## 15 septembre, 10:45 — pauses `key831` expliquées : le CFS 2 n'entend pas la question qui suit une réponse du CFS 1 finie par `F7` (document 80)

**Point de reprise :** accord de Thomas sur le remède 3 du document 80 (retenir
toute question 300 ms après une réponse finie par `F7`). En attendant, en
lecture seule : dès la fin de l'impression en cours, relire le journal (la
veille du capteur du CFS 1 s'arrête-t-elle ?) ; Thomas vérifie que la bobine
`T1A` tourne librement. Mission garde : vérifier machine au repos que
`box_wrapper` passe par `cmd_send_data_with_response` de l'objet
`serial_485 serial485`, écrire l'enveloppe et ses tests hors machine, la poser
hors impression avec l'accord de Thomas, contrôler la prochaine impression avec
`silences_cfs.py` (zéro silence après `F7`).

### Fait

- Document 80 : trois pauses (05:15:21, 08:01:10, 09:24:23), déclencheur à
  03:45:58 (tension `T1A`, capteur à 1), comptes du 15 septembre et
  contre-épreuves (CFS 1 jamais touché, 13 septembre à `FE` et `CF` sans perte), nos
  modifications hors de cause, remèdes classés.
- `scripts/audit-en-direct/silences_cfs.py` : pour chaque question à un CFS,
  trame précédente, écart et réponse ; contrôles recalculés.
- Rien modifié sur la machine ; impression non touchée (88,7 % à 10:43 ;
  37 silences du CFS 2 de 10:14 à 10:48, deux fois quatre de suite).

### À savoir

- Une pause `key831` : cinq questions d'état de suite sans réponse du même CFS
  (`timeout_times` de 4 à 0), une toutes les 5 s. Le module interroge chaque
  CFS branché, qu'il serve ou non.
- Après un événement de tension, le module interroge le capteur toutes les 5 s,
  en impression comme en pause. Le 13 septembre : 2, puis 0 au bout de 81 s,
  puis une autre question au capteur (réponse 9) jusqu'à 12:48:48, et arrêt.
  Le 15, la valeur reste à 1 depuis 03:45:58 (4 872 réponses à 10:47).
- Extraction du bus : commande en tête de `silences_cfs.py`, depuis un dossier
  hors du dépôt, en basse priorité.

## 14 septembre, 23:30 — audit en direct fait : impression multicouleur sans pause, purge arrondie à 280 mm, relance du noir (document 79, sections 9 et 10)

**Point de reprise :** section 10 du document 79. Correctif 1 chez Thomas
(volumes de purge dans Creality Print, 336 mm³ au plus pour les transitions vers
une couleur plus foncée, puis un cube pour juger les couleurs). Correctif 2 à
instruire en lecture seule : d'où vient « max_volumetric_speed: 14 », qui donne
140 mm/min, avant de proposer un essai à Thomas. Correctif 3 : les trois gestes
de la section 9.4 sur le noir T1A.

### Fait

- Impression `MultiColo_Cube_PLA_15m31s` de 22:30:56 à 22:54:21 : aucun code
  d'erreur du CFS, aucune pause ; cinq `T` avec « runout alarm off » puis « on
  again » (ADR-065) ; départ passé par les contrôles d'ADR-066 sans arrêt,
  aucune tentative de chargement lancée.
- Document 79 : §3.1 et §3.2 corrigés (longueurs poussées et non demandées),
  §5, §6, §7 et §8 mis à jour, sections 9 « Audit en direct » et 10 « Correctifs
  classés » ajoutées.
- `scripts/audit-en-direct/` : suivi du journal en direct (`audit-live.sh`,
  `audit_live.py`), découpe des chargements (`phases.py`), fenêtre de journal
  lisible (`fenetre.py`), relevé des purges sur la machine (`purges.sh`).
  Rejoué sur le journal enregistré : table identique à la table corrigée.

### À savoir

- Réglages du module CFS dans `box.cfg` : `box_first_clean_length`,
  `box_need_clean_length` et `box_need_clean_length_max` à 140,
  `Tn_extrude_velocity: 360` (vitesse de la purge du départ). Le module
  (`box_wrapper`) est compilé ; ses chaînes citent `BOX_GET_FLUSH_VELOCITY_TEST`,
  commande jamais appelée, effets inconnus.
- Le fichier tranché déclare `filament_max_volumetric_speed = 23,24,24,24,24`,
  tour d'amorçage activée (`prime_volume = 25`), purge dans la tour désactivée.
- Suivi en direct arrêté après l'audit. Pour la prochaine impression : lancer
  `scripts/audit-en-direct/audit-live.sh` depuis un dossier hors du dépôt ; le
  journal enregistré et les images n'entrent jamais dans le dépôt.

## 14 septembre, 22:31 — ADR-066 installé à 22:16 ; audit en direct de l'impression multicouleur lancée par Thomas à 22:30:56 (remplacé par 23:30)

**Point de reprise :** suivre l'impression lancée à 22:30:56 (document 79,
section 7), puis écrire la section « Audit en direct » du document 79 et
classer les correctifs. À observer : départ sans pause ; si le CFS abandonne,
arrêt net avec le message `K1 Control [étape]` ; à chaque changement « runout
alarm off during Tn » puis « on again after Tn » sans pause (ADR-065) ; relances
Creality « l'extrudeur n'a pas mordu ».

### Fait

- Copie du cfg depuis `main` (`e8cf8f8`) machine à l'arrêt, empreinte
  conforme, Klipper prêt à 22:16:43, démarrage sans erreur, les deux macros
  chargées, contrôle essayé à vide sans effet.
- Retour arrière si besoin, machine à l'arrêt :
  `k1-control-owned-start-print-v2.cfg.bak-20260914-adr066` recopié sur le cfg,
  puis redémarrage de Klipper.

### À savoir

- Le journal Klipper grossit d'environ 20 Mo par heure (481 Mo le 14 septembre
  à 22:23) : chercher par heure dans le fichier du jour, un `grep` sur tous
  les journaux prend deux minutes.
- Pendant un `T` passé par notre enveloppe, les lignes du module Creality
  portent l'origine `[kctrl_tool_change:change:219]`.

## 14 septembre, 22:10 — départ arrêté net sur une pause, deux tentatives (ADR-066) : écrit et testé (installé à 22:16, remplacé par 22:30)

**Point de reprise :** si la PR d'ADR-066 est fusionnée mais pas installée,
installer `k1-control-owned-start-print-v2.cfg` depuis `main` machine à
l'arrêt (sauvegarde `.bak-`, copie par `cat | ssh`, empreinte, redémarrage de
Klipper, `ready`). Puis l'audit en direct du bloc de 21:40.

### Fait

- `_KCTRL_ASSERT_CFS_OK` après le changement d'outil, après les tentatives,
  avant la ligne d'amorce ; `_KCTRL_START_STOPPED` lève l'erreur. Tentatives
  `ATTEMPT=3` et `ATTEMPT=4` retirées.
- `tests/test_owned_start_stops_on_cfs_pause_v1.py` (12 tests) ; suite complète
  verte. ADR-049 amendée ; document 79, section 8.

### À savoir

- Un départ arrêté ne se reprend plus : on relance l'impression. Une pause
  demandée depuis l'interface pendant le départ l'arrête aussi.
- Sur la machine, `virtual_sdcard.py` ne lit pas la pause. Un nouveau départ
  juste après un arrêt en erreur n'a pas encore été rejoué.

## 14 septembre, 21:40 — départ et changements de couleur expliqués (document 79) ; audit en direct à faire pendant une impression lancée par Thomas

**Point de reprise :** quand Thomas lance une impression multicouleur et
prévient, suivre le protocole du document 79, section 7 : journal en direct,
images de la webcam au départ et à chaque changement, vérification de
l'ADR-065 au passage (bloc de 21:05), puis section « Audit en direct » dans le
document. Ne jamais lancer, reprendre ni annuler l'impression soi-même.

### Fait

- Document 79 : chronologie d'un départ normal (12 septembre, 23:20) et du
  changement vers le noir (14 septembre, 20:34), fréquences des relances sur
  les journaux du 9 au 14, tableau de ce qui est normal ou non et de qui le
  décide.
- Le rembobinage complet puis la réinsertion au changement sont la relance
  Creality « l'extrudeur n'a pas mordu » (tampon « plein » à 12 lectures) : 2
  changements sur 3 le 14. Cause inconnue, deux hypothèses dans le document.
- Au départ : aucune relance sur 14 chargements du 10 au 12 septembre ; une
  seule coupe sur tête chargée en 19 départs depuis le 10.

### À savoir

- Deux défauts de notre code confirmés : le départ trace la ligne d'amorce
  alors que le CFS est en erreur (18:39:33, déjà signalé par le document 70) ;
  quatre tentatives de chargement sur un filament cassé (7 minutes). Accord de
  Thomas reçu : arrêt net sur erreur CFS, deux tentatives au lieu de quatre,
  correctif en cours sur sa propre branche (ADR-066).
- Rien n'a été touché sur la machine.

## 14 septembre, 21:05 — alarme de fin de bobine coupée pendant les changements (ADR-065) installée ; première impression multicouleur à observer

**Point de reprise :** à la prochaine impression multicouleur, lire le
journal : « runout alarm off during Tn », « Tn fait », « runout alarm on
again after Tn », et ni « runout event detected » ni pause. Si une pause
revient, lire les lignes autour de `runout` dans `klippy.log` avant de
toucher quoi que ce soit.

### Fait

- 21:00, machine au repos depuis 3 minutes : `kctrl_tool_change.py` et le cfg
  copiés depuis `main` (40199b3), empreintes conformes ; service Klipper
  relancé à 21:00:33, prêt à 21:01:06, « wrapped T0,…,T15 », `KCTRL_TOOLS`
  répond.
- `3DBenchy_C2` fini à 20:56:58 ; T1 (blanc) passé sans pause à 20:50:21.

### À savoir

- Retour arrière : remettre `kctrl_tool_change.py.bak-20260914-adr065`
  (`/usr/share/klipper/klippy/extras/`) et
  `k1-control-owned-start-print-v2.cfg.bak-20260914-adr065`
  (`/usr/data/printer_data/config/`) à leur place, relancer le service.
- Après le redémarrage, l'alarme est coupée : normal, `START_PRINT` la
  réarme à chaque impression.
- Rouge T2A cassé deux fois au buffer, et propositions en attente de
  l'accord de Thomas : voir le bloc de 20:50.

## 14 septembre, 20:50 — pause après chaque changement de couleur : alarme de fin de bobine coupée pendant le changement (ADR-065), à installer entre deux impressions (remplacé par 21:05)

**Point de reprise :** machine à l'arrêt (`print_stats.state` ni `printing`
ni `paused`, `idle_timeout.state` différent de `Printing`), installer depuis
`main` :

```
ssh k1max-root 'cp /usr/share/klipper/klippy/extras/kctrl_tool_change.py /usr/share/klipper/klippy/extras/kctrl_tool_change.py.bak-20260914 && cp /usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg /usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg.bak-20260914'
git show main:packages/k1-control-v1/owned-start-print-v2/kctrl_tool_change.py | ssh k1max-root 'cat > /usr/share/klipper/klippy/extras/kctrl_tool_change.py'
git show main:packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg | ssh k1max-root 'cat > /usr/data/printer_data/config/k1-control-owned-start-print-v2.cfg'
ssh k1max-root '/etc/init.d/S55klipper_service restart'
```

Attendu : `ready`, journal « kctrl_tool_change: wrapped T0,…,T15 »,
`KCTRL_TOOLS` répond. À la première impression multicouleur : « runout alarm
off during Tn », « Tn fait », « runout alarm on again after Tn », sans
« runout event detected » ni pause. Le cfg ne change que par un commentaire.

### Fait

- Diagnostic dans le journal de `3DBenchy_C2` : T3 part à 19:19:16, retire le
  rouge devant le capteur de tête armé par `START_PRINT` ; « runout event
  detected » à 19:19:35 ; pause à 19:22:36, 12 ms après « T3 fait ».
- Correctif dans `kctrl_tool_change.py`, 7 tests (31 dans le fichier,
  5 rouges sur l'ancien module), ADR-065, ADR-061 amendée.

### À savoir

- L'impression du soir finit alarme coupée depuis 19:22:42 : une bobine vide
  d'ici la fin ne serait pas détectée. T0 (20:34:05 → 20:37:30) est passé
  sans pause ; T1, blanc, a démarré à 20:47:54.
- Sans l'installation, chaque impression multicouleur s'arrête à son premier
  changement ; `RESUME` suffit, la suite n'a plus d'alarme.
- Retour arrière : recopier les `.bak-20260914`, relancer le service.
- Rouge T2A : `key836` à répétition au chargement (18:18 → 18:38), `key845`
  (buse bouchée) à 18:36:22, `key847` (« empty printing ») à 19:00:52 en
  impression ; cassé deux fois au buffer, débloqué à la main par Thomas.
  Plier un bout en U : s'il casse net, le filament est sec.
- En attente de l'accord de Thomas, rien d'écrit : arrêt net après deux
  échecs de chargement au départ ; départ qui ne continue pas machine en
  pause ; gestes manuels dans Mainsail.

## 14 septembre, 18:20 — copie de maillage ramenée de 70 à 65 °C : aucun trou de 50 à 70 °C

**Point de reprise :** Thomas envoie un G-code par Mainsail et relance son
impression. Pour un fichier à 61–70 °C, première couche sur le carré
280×280 (plateau à 65), régler le Z à la main, puis :

```
KCTRL_Z_SAVE PROFILE=k1_p001_t065_r001_n11x11 Z=<valeur>
```

- Maillages : 55 (50–60 °C), 65 (61–70 °C, copie du 55, Z 0,065). Le 70
  n'existe plus. Profil actif : le 55.
- Retour arrière de ce geste : `.bak-20260914-1810` (`printer.cfg`,
  `k1-control-saved-vars.cfg`), puis Klipper relancé.
- Le bloc 18:15 ci-dessous reste juste pour l'envoi de fichiers ; ce qu'il
  dit du 70 est remplacé par ce bloc.

## 14 septembre, 18:15 — maillage à ±5 °C et copie 70 °C installés (ADR-064) ; envoi de G-code par Mainsail réparé ; geste Bobines du 12 fait

**Point de reprise :** Thomas envoie un G-code par Mainsail (Fichiers G-code →
envoi) et relance son impression. Pour un fichier à 65–75 °C, première
couche sur le carré 280×280 (plateau à 70), régler le Z à la main, puis :

```
KCTRL_Z_SAVE PROFILE=k1_p001_t070_r001_n11x11 Z=<valeur>
```

### Fait le 14 septembre, 17:55–18:15

- Tolérance de bande (`band_tolerance_c: 5`) dans `START_PRINT` et
  `KCTRL_PROFILE_NAME` ; `KCTRL_MESH_COPY` dans `kctrl_mesh.py`. Posés,
  Klipper relancé à 17:58:06. `k1_p001_t070_r001_n11x11` créé depuis le 55,
  Z 0,065 recopié, chargé après redémarrage. Profil actif : le 55.
- Envoi de fichiers : `tmp/` en 711 par `S57k1_control_gateway`,
  `/server/files/upload` en flux direct jusqu'à 1 Go. 156 Mo passés en 59 s.
- Geste du 12 septembre fait au passage : `mainsail_overlay_patch.py` dans
  `state/`, nouveau service posé, « balise deja en place », `/` et
  `/bobines/` en 200.

### À savoir

- 61–64 °C : aucun maillage, refus volontaire avant chauffe ; le message
  donne `KCTRL_MESH_COPY BED_TEMP=<t>`.
- Le 70 est une copie, pas une mesure : si la première couche montre un
  gondolage, calibrer la bande 70 pour de vrai.
- Retour arrière : sauvegardes `.bak-20260914-1755` (six fichiers, voir
  STATE), puis Klipper et passerelle relancés.
- Sur la machine, `/tmp/kctrl_gc.py "GCODE"` envoie une commande à Klipper et
  affiche ses réponses (le `curl` de la machine ne sait pas poster du JSON) ;
  `/tmp` se vide au redémarrage.

## 12 septembre, 23:30 — point 2 fait (premier départ réel par la fenêtre à 23:17) ; PR #58 fusionnée ; reste à poser, machine à l'arrêt, le service qui repose la balise à chaque démarrage

**Point de reprise en un geste :** machine à l'arrêt (`print_stats.state` =
`standby`, vérifier), poser la persistance de la fenêtre :

```
cat packages/k1-control-v1/spool-choice-gate-v1/mainsail_overlay_patch.py | ssh k1max-root 'cat > /usr/data/k1-control-v1/state/mainsail_overlay_patch.py'
cat packages/k1-control-v1/services/S57k1_control_gateway | ssh k1max-root 'cat > /etc/init.d/S57k1_control_gateway'
ssh k1max-root 'chmod 644 /usr/data/k1-control-v1/state/mainsail_overlay_patch.py; chmod 755 /etc/init.d/S57k1_control_gateway; rm -f /usr/data/k1-control-v1/current/mainsail_overlay_patch.py; /etc/init.d/S57k1_control_gateway restart'
```

Attendu au restart : « balise deja en place: …/mainsail/index.html », puis
`http://192.168.1.64:4409/` répond 200 avec la balise et la fenêtre s'ouvre
toujours sur un départ. Sauvegarde préalable de `/etc/init.d/S57k1_control_gateway`
(`.bak-<date>`). Ensuite STATE et HANDOFF (nouveau bloc de tête), commit
`pilotage`, push sur `main`.

### Fait le 12 septembre, 22:58–23:30

- Thomas a lancé BIN4U par la fenêtre à 23:17 : journal « bobines
  raccordees », « lance avec T1A=T1B », ligne de départ « raccorde sur la
  page Bobines ». Point 2 du flux quotidien fait ; impression en cours.
- Persistance de la balise après une nouvelle version de K1 Control
  (Mainsail y est livré, rien d'autre ne le met à jour ; nginx sans
  `sub_filter` ni `addition`) : `S57k1_control_gateway` relance
  `mainsail_overlay_patch.py` depuis `state/` à chaque `start`, sans jamais
  bloquer la passerelle. Écrit, testé (`test_bobines_page_v1`, 21), pas posé.
- PR #58 fusionnée dans `main`, branche supprimée.

### À savoir

- Sur la machine ce soir, le script est encore dans `current/` (dossier de
  version) et le service installé est l'ancien : la balise tient tant que la
  version K1-CONTROL-V1.0.0 reste, le geste ci-dessus la rend durable.
- Retour arrière de la fenêtre : `python3 …/mainsail_overlay_patch.py
  --remove …/mainsail/index.html`, sauvegardes `.bak-20260912-2250`
  (`nginx-active.conf`, `kctrl_print_gate.py`), `index.html.bak-20260912-225208`.
- Fluidd et l'écran n'ont pas la fenêtre : la page `/bobines/`, dont le
  message Klipper donne l'adresse.

## 12 septembre, 22:58 — la fenêtre Bobines dans Mainsail (PR #58) : lancer depuis Mainsail, la fenêtre s'ouvre seule, raccorder, lancer ; premier départ réel à observer, puis fusion

**Point de reprise en un geste :** Thomas lance un fichier depuis Mainsail.
Attendu : rien ne chauffe, la fenêtre Bobines couvre Mainsail en une à
trois secondes avec les filaments du fichier et les bobines du CFS ; il
touche un filament puis sa bobine, « Lancer l'impression » ; la fenêtre dit
« Impression lancée » puis se retire ; au journal, « bobines raccordees
pour … », la ligne de départ « raccorde sur la page Bobines » et `cmd_T
vtnn=` sur la bobine choisie. Ensuite : fusion de #58 (STATE et HANDOFF :
garder tous les blocs de tête, le plus récent en premier), suppression de
la branche, `main` repoussé.

### Fait le 12 septembre, 22:10–22:58

- Sur le refus de Thomas (« pas une page que je dois ouvrir à chaque
  fois »), l'interface est devenue une fenêtre dans Mainsail : `bobines.js`
  (l'interface, montée une fois par `mount`), `overlay.js` (shadow DOM,
  sondage toutes les 750 ms, « Réduire » et pastille, retrait quatre
  secondes après le lancement), balise ajoutée à l'index de Mainsail par
  `mainsail_overlay_patch.py` (copie datée, `--remove`), trois blocs nginx
  (`= /index.html` sans cache). La page `/bobines/` reste (`app.js`, six
  lignes).
- Lenteur du message d'attente corrigée : `may_hold_tool` évite
  l'expression sur les blocs sans `T` ; BIN4U 50 Mo retenu en 2,4 s sur la
  machine (8 s et plus avant), cube 0,25 s.
- Installé à 22:52 machine à l'arrêt (sauvegardes `.bak-20260912-2250`,
  `index.html.bak-20260912-225208`), vérifié dans le vrai Mainsail :
  fenêtre en 0,4 s, réduire, rouvrir, abandonner. Détail dans STATE.
- Tests : 58 + 20 (dont 17 node) ; suite 1371 verts, 2 rouges
  préexistants. Doc 78 et ADR-063 complétés, README du paquet refait.

### À savoir

- L'attente BIN4U que Thomas avait laissée (22:24) est tombée avec le
  redémarrage de Klipper : la relancer.
- Une mise à jour de Mainsail qui réécrit `index.html` retire la balise :
  `python3 /usr/data/k1-control-v1/current/mainsail_overlay_patch.py
  /usr/data/k1-control-v1/current/www/mainsail/index.html`.
- Retour arrière : la même commande avec `--remove`, puis les sauvegardes
  `.bak-20260912-2250` et celles du bloc précédent.
- Fluidd et l'écran n'ont pas la fenêtre : la page `/bobines/`, dont le
  message Klipper donne l'adresse.

## 12 septembre, 22:10 — la page Bobines installée (PR #58) : chaque départ attend le choix de Thomas ; premier départ réel à observer, puis fusion

**Point de reprise en un geste :** Thomas lance un fichier depuis Mainsail.
Attendu : rien ne chauffe, fenêtre « Choix des bobines » dans Mainsail,
page `http://192.168.1.64:4409/bobines/` avec le fichier en attente ; il
raccorde chaque filament d'un clic, « Lancer l'impression » ; au journal,
« bobines raccordees pour … » puis la ligne de départ « raccorde sur la page
Bobines » et `cmd_T vtnn=` sur la bobine choisie. Ensuite : fusion de #58
(STATE et HANDOFF : garder tous les blocs de tête, le plus récent en
premier), suppression de la branche, `main` repoussé.

### Fait le 12 septembre, 21:24–22:10

- Fusion de #53, #57 (remplace #55), #56, #54 dans `main` à 21:24–21:26.
- Mission « choix obligatoire avant le départ » : module `kctrl_print_gate`
  (reprend `SDCARD_PRINT_FILE`, retient sans chauffer, `KCTRL_GATE_CONFIRM`
  / `KCTRL_GATE_CANCEL` / `KCTRL_GATE`), page `www/bobines/`, bloc nginx,
  `START_PRINT` qui prend la table telle quelle quand la porte a confirmé le
  fichier. 38 + 9 (+ 14 node) tests, suite 1354 verts + 2 rouges
  préexistants (les mêmes sur `main`). Doc 78, ADR-063, ADR-062 en repli.
- Installé à 22:02 machine à l'arrêt (sauvegardes `.bak-20260912-2210`),
  `kctrl_mesh.py` de `main` posé au passage ; retenue prouvée à 22:05 sur
  le cube (`pending 1`, `standby`, cibles 0, fenêtre émise, annulation
  propre). Détail dans STATE.

### À savoir

- Retour arrière : recopier les trois `.bak-20260912-2210`, supprimer
  `kctrl_print_gate.py` (+ `.pyc`) et `www/bobines/`, `S57k1_control_gateway
  reload`, `S55klipper_service restart`.
- Un redémarrage de Klipper pendant une attente oublie le fichier : le
  relancer. La reprise après coupure passe sans choix.
- Fichiers servis par la passerelle : `cat >` en root crée en 600, poser
  755 sur le dossier et 644 sur les fichiers, sinon 403.
- La page ne raccorde jamais seule : une bobine identique n'a qu'un badge.
  `MATCH=1` sur `START_PRINT` force l'appariement d'ADR-062 malgré la porte.

## 12 septembre, 21:05 — points 4 et 2 installés (PR #53 + #55) après recalibrage ; premier démarrage réel à observer, puis fusion

**Point de reprise en un geste :** Thomas lance une impression multi-filament
depuis Mainsail. Attendu au journal : « appariement du fichier sur les
bobines » avec une ligne par filament, puis `cmd_T vtnn=` avec la bobine
retenue. S'il manque une couleur, `KCTRL_SLOT SLOT=<bobine> TOOL=<T du
fichier>` avant de relancer. Ensuite : fusion de #53, #55, #54, #56 (STATE et
HANDOFF : garder tous les blocs de tête, le plus récent en premier), suppression
des branches, `main` repoussé.

### Fait le 12 septembre, 20:59–21:02

- État vérifié `standby` avant chaque geste ; sauvegardes `.bak-20260912-2100`
  de `kctrl_slot_map.py` et `k1-control-owned-start-print-v2.cfg` ;
  `kctrl_tool_change.py` copié (nouveau) ; Klipper relancé, prêt en 10 s.
- Preuves : `help` liste `KCTRL_TOOLS`, `KCTRL_MATCH`, `KCTRL_SLOT`,
  `KCTRL_MAP` ; journal « wrapped T0,…,T15 ; not registered by the box: - » ;
  `KCTRL_MATCH CHECK=1` sur le cube PLA rend la table complète (voir STATE).
- Z sauvé par Thomas : 0,065 (`k1-control-saved-vars.cfg`).

### À savoir

- Retour arrière : recopier les deux `.bak-20260912-2100`, supprimer
  `kctrl_tool_change.py` et son `.pyc`, relancer le service Klipper.
- Le `.pyc` de `kctrl_slot_map` s'est bien régénéré à 21:00:14.

## 11 septembre, 21:00 — boulon perdu, plateau plié, outil « quatre vis seulement » installé (PR #56) ; PR #53, #54, #55 toujours à déployer

**Point de reprise en un geste :** Thomas règle les vis avec
`KCTRL_SCREWS_ONLY` (buse propre, filament hors tête ; le lit reste à 55 C
entre les passes, `TURN_OFF_HEATERS` à la fin). Critère : écart entre vis
sous un huitième (0,0875 mm), sans forcer une vis pour en rattraper une
autre. Ensuite `KCTRL_MESH_CALIBRATE`, carré de calibration, `KCTRL_Z_SAVE`
(le 0,075 date d'avant la panne). Critère du relevé : décalage entre
quadrants sous 0,1 mm, bord avant plat.

### Fait le 11 septembre

- Nuit : trois relevés lus et comparés (doc 77) ; verdict donné à Thomas :
  mesure propre, plateau qui bouge (0,25–0,56 mm entre quadrants) et bord
  avant creusé de 0,5 mm, donc tôle contrainte par ses vis, pas voilée.
- Soir : `KCTRL_SCREWS_PROBE` (Python, quatre `PROBE` bruts aux positions
  mesurées des vis) et `KCTRL_SCREWS_ONLY` (macro), 16 tests, suite à 1292
  verts + 2 rouges préexistants ; installé à 20:45 machine à l'arrêt
  (sauvegardes `.bak-20260911-2050`), commandes visibles dans `help`.
  Première exécution réelle pas encore observée.

### À savoir

- `KCTRL_BED_SCREWS` (25 points) lit un profil enregistré, incliné de 0,10
  par le firmware : pour les vis, préférer `KCTRL_SCREWS_ONLY`.
- Les PR #53 (enveloppe des `T`), #55 (appariement des bobines) et #54 ne
  sont **pas** sur la machine ; le démarrage de 03:35 l'a montré (« dernier
  choix retenu, table CFS effacée »). Déploiement sur accord, machine à
  l'arrêt (docs 74, 75).
- À la fusion, STATE et HANDOFF de #53/#55 et de #56 s'insèrent tous en tête :
  garder les deux blocs, le plus récent en premier.

## 10 septembre, 23:30 — points 4 et 2 écrits et testés (PR #53 + PR point 2), point 5 documenté ; à déployer entre deux impressions (remplacé par 11 sept. 21:00)

**Point de reprise en un geste :** quand la machine n'imprime pas
(`print_stats.state` ni `printing` ni `paused`, vérifié avant chaque action)
et sur le « go » de Thomas, déployer les deux PR ensemble (la branche du
point 2 contient le point 4) : sauvegardes, copie de `kctrl_tool_change.py`
et `kctrl_slot_map.py` dans `/usr/share/klipper/klippy/extras/` et de
`k1-control-owned-start-print-v2.cfg` dans `/usr/data/printer_data/config/`
(par `git show <branche>:<chemin> | ssh k1max-root 'cat > cible'`), puis
`/etc/init.d/S55klipper_service restart`. Contrôle : `printer/info` à
`ready`, ligne `kctrl_tool_change: wrapped` au journal, `KCTRL_TOOLS` et
`KCTRL_MATCH CHECK=1` répondent. Procédures : documents 74 et 75. Fusionner
PR #53 puis la PR du point 2 (et PR #54) une fois déployées et observées.

### Fait à 22:05–23:30, pendant que Thomas imprime (aucune action machine)

- Point 2 : `match` publié par `kctrl_slot_map`, `KCTRL_MATCH`, `START_PRINT`
  qui prend la bobine appariée avant la table et refuse au rendu sans
  bobine ; 47 tests ; doc 75, ADR-062.
- Point 5 : chaîne de relève relue et prouvée au journal du 5 septembre ;
  aucune paire ce soir ; procédure pour la provoquer ; doc 76.
- Suite 1274 verts, 2 rouges préexistants.

### À savoir

- `KCTRL_MATCH` sans `CHECK=1` refuse pendant une impression ; seul
  `START_PRINT` passe `STARTING=1`.
- Aucune couleur approchée n'est acceptée : la plus proche est nommée dans
  le refus, `KCTRL_SLOT` l'impose, `MATCH=0` part sur la table.
- Reste : contacts bruts capturés par `KCTRL_MESH_ACQUIRE` /
  `KCTRL_BED_SCREWS` ; PR #54 à fusionner.

## 10 septembre, 22:05 — point 4 écrit et testé (PR #53), à déployer entre deux impressions ; puis points 5 et 2 (remplacé par 23:30)

**Point de reprise en un geste :** quand la machine n'imprime pas
(`print_stats.state` ni `printing` ni `paused`, vérifié avant chaque action)
et sur le « go » de Thomas, déployer PR #53 : sauvegardes, copie de
`kctrl_tool_change.py` et `kctrl_slot_map.py` dans
`/usr/share/klipper/klippy/extras/` et de
`k1-control-owned-start-print-v2.cfg` dans `/usr/data/printer_data/config/`
(par `cat fichier | ssh k1max-root 'cat > cible'`), puis
`/etc/init.d/S55klipper_service restart` (module Python, jamais
`FIRMWARE_RESTART` seul). Contrôle : `printer/info` à `ready`, ligne
`kctrl_tool_change: wrapped T0,…,T15` au journal, `KCTRL_TOOLS` répond.
Procédure complète : document 74. Fusionner PR #53 dans `main` une fois
déployée et observée sur un premier `T` réel.

### Fait à 20:50–22:05, pendant que Thomas imprime (aucune action machine)

- Journal relu : ADR-060 tient sur deux vrais démarrages (une purge, une
  ligne, Z rendu à l'identique) ; Z 0,065 enregistré par Thomas à 20:15.
- `kctrl_tool_change.py` : enveloppe des seize `T`, refus nets avant la
  commande stock, fiche alignée sur la température du fichier (première
  couche ou courante), pause sur tête vide après un changement, cible
  remise à la valeur du fichier ; `KCTRL_TOOLS`.
- `kctrl_slot_map.py` : bloc de configuration Orca lu en queue de fichier,
  `job_*` publiés dans le statut (base du point 2).
- 24 + 7 tests sur la queue réelle du cube ; suite 1227 verts, 2 rouges
  préexistants. ADR-061, document 74, `GOALS.md` point 4.

### À savoir

- La commande stock `return False` sans erreur Klipper sur un mauvais
  emplacement : c'est l'enveloppe qui rend l'échec visible, pas le firmware.
- La purge stock chauffe toujours à `max(fiche, 200)` ; l'enveloppe remet la
  cible du fichier après. Point 7 de l'audit 70 toujours ouvert, sans effet.
- Suite prévue après déploiement : point 5 (relève auto : documenter
  `auto_refill`, la provoquer exprès sur une impression sans valeur), point 2
  (appariement automatique couleur + matière depuis Mainsail avec `job_*`),
  contacts bruts capturés par `KCTRL_MESH_ACQUIRE` / `KCTRL_BED_SCREWS`, nom
  de sauvegarde unique dans `kctrl_mesh.py`.

## 10 septembre, 12:35 — PR #52 déployée et profil reconstruit appliqué ; prochain geste : le carré 280×280, puis le Z (remplacé par 22:05)

**Point de reprise en un geste :** Thomas imprime le carré 280×280 (plateau à
55 ; le démarrage charge `k1_p001_t055_r001_n11x11` lui-même), règle Z en
direct ; après l'impression, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11
Z=<valeur affichée>` (jamais tant que `print_stats.state` vaut `printing`),
puis point 6 de `GOALS.md`, `STATE.md`, PR #52. Attendu au journal de ce
démarrage : une seule purge (`material_change_flush`), aucun « complément de
purge », aucune ligne stock à F3000 avant « ligne d'amorce » (ADR-060).

### Fait à 12:30–12:33, sur « tu peux appliquer la PR »

- Trois cfg copiés (sauvegardes `.kctrl-bak-20260910-123029`, md5 identiques
  au dépôt), Klipper redémarré 12:30:53, prêt 12:31:27, aucune erreur ;
  macros de mesure sans « standby », `_KCTRL_PURGE_MARK` et
  `_KCTRL_PURGE_REPORT` absents, `_KCTRL_PURGE_BALL` et `_KCTRL_PRIME_LINE`
  présents.
- `KCTRL_MESH_APPLY` étape 1 puis 2 à 12:32:54 : 120 points, pas de 0,079,
  zéro gardé en X150 Y150 ; profil vivant identique au fichier reconstruit,
  écrit dans `printer.cfg`. Retour possible : `KCTRL_MESH_UNDO` (une étape)
  ou `KCTRL_MESH_APPLY` sur un JSON tiré de
  `experiments/2026-09-10-mesh-brut-sans-rampe/profil-actif-avant.json`.
- Réponses données à Thomas avant d'agir : pas de nouvelle mesure du plateau
  (même rampe) ; la pente avant/arrière est réelle et progressive, 0,18 entre
  les vis ; la validation est le carré.

### À savoir

- La bannière `SAVE_CONFIG` revient à chaque démarrage (`[auto_addr]
  mb_addr_table_uniids`, journal 12:31:27) : permanente, jamais la presser.
- Après un redémarrage le profil actif est `default` ; c'est `START_PRINT`
  qui charge le bon profil (`BED_MESH_PROFILE LOAD=`).
- Petit défaut vu : deux applications dans la même seconde ont reçu le même
  nom de sauvegarde `…-123254.json`, la seconde a écrasé la première ;
  compteur ou microsecondes à ajouter dans `kctrl_mesh.py`.
- La machine n'a ni `bash` ni `sftp-server` : `ssh k1max-root 'sh -s'` et
  copie par `cat fichier | ssh k1max-root 'cat > cible'`.

## 10 septembre, 12:15 — cube fini ; une purge, une ligne écrites et testées ; le maillage est incliné par le firmware, reconstruction prête ; rien de déployé (remplacé par 12:35)

**Point de reprise en un geste :** sur le « go » de Thomas, machine à l'arrêt
(`print_stats.state` autre que `printing`, vérifié avant chaque action) :
(1) déployer la branche `fix/demarrage-une-purge-une-ligne` — copie avec
sauvegarde de `k1-control-owned-start-print-v2.cfg`,
`k1-control-mesh-acquisition-v2.cfg` et `k1-control-mesh-reference-v2.cfg`,
puis `/etc/init.d/S55klipper_service restart`, md5 et journal vérifiés ;
(2) appliquer le profil reconstruit — copier les deux `.json` de
`experiments/2026-09-10-mesh-brut-sans-rampe/` dans
`/usr/data/printer_data/config/`, puis `KCTRL_MESH_APPLY FILE=…etape1.json`
et `…etape2.json` (sauvegarde automatique, `KCTRL_MESH_UNDO` pour revenir) ;
(3) Thomas imprime le carré 280×280, règle Z en direct, puis
`KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=<valeur>` après
l'impression. Ne jamais presser `SAVE_CONFIG` : la bannière levée à 11:43:08
par `Z_OFFSET_APPLY_PROBE` ne porte rien d'utile (sonde à 0, inchangée).

### Observé sur le cube de 11:15, fini à 11:43:07

- Deux purges dans le bac : la purge stock du `T{position - 1}` (complète, à
  200, finie à 11:18:56), puis notre complément de 254 mm à 190, chaîne écrite
  le 2 septembre pour un chargeur qui purgeait alors sur une buse à 109 °C.
  Deux lignes : `CX_PRINT_DRAW_ONE_LINE` trace ses trois cordons lents à
  chaque démarrage normal (`can_break_flag` vaut 3 après tout `M109`), puis
  la nôtre.
- Première couche ratée : buse trop loin à l'avant, trop près à l'arrière.
  Cause : le profil lui-même, pas son application (document 73).
- Z vivant à +0,180 en fin de cube, remis à zéro à 11:43:08 par l'interface ;
  rien d'écrit dans le profil.
- `KCTRL_BED_SCREWS` refusé six fois de 11:43:51 à 11:49:19 : l'état vaut
  `complete` après une impression, pas `standby` (`SDCARD_RESET_FILE` le
  remettrait). Filet corrigé sur la branche : refus seulement pendant
  `printing` ou `paused`.

### Décidé et écrit (branche `fix/demarrage-une-purge-une-ligne`, PR #52)

- ADR-060 : le démarrage ne pousse plus de filament lui-même ; une seule
  ligne, la nôtre ; `_KCTRL_PURGE_BALL TEMP=200 LEN=100` reste en manuel.
- Les quatre macros de mesure refusent `printing` et `paused`, rien d'autre
  (`tests/test_mesh_acquisition_state_gate_v1.py`).
- Document 73 et `experiments/2026-09-10-mesh-brut-sans-rampe/` : la rampe
  mesurée sur les cinq mesures du matin, le profil reconstruit, les vis
  (0,177 mm d'écart réel, arrière plus haut, contre 0,077 vu par le rapport).
- 1196 tests verts, deux rouges préexistants inchangés.

### Mission suivante

`KCTRL_MESH_ACQUIRE` et `KCTRL_BED_SCREWS` capturent les contacts bruts
pendant la mesure ; `KCTRL_MESH_MERGE` et `KCTRL_SCREWS_REPORT` ne lisent plus
jamais les profils enregistrés. À ouvrir après validation du carré sur le
profil reconstruit.

## 10 septembre, 11:25 — le cube a chargé à 190 : l'alignement est observé sur un vrai chargement ; Z en cours de réglage (remplacé par 12:15)

**Point de reprise en un geste :** quand le cube est fini et que Thomas donne
le Z affiché dans Mainsail, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11
Z=<valeur>` (jamais tant que `print_stats.state` vaut `printing`), puis
mettre à jour le point 6 de `GOALS.md`, `STATE.md`, la PR #51.

### Observé sur le cube de 11:15 (fichier à 190 / 55)

- 11:15:03 : `START_PRINT` a écrit `200/200 -> 190` dans la fiche `00001`
  avant toute chauffe (base modifiée à cette seconde).
- 11:17:32 : `get next material temp: 190` au chargement, à nouveau à
  11:18:27 pour la purge ; filament à la tête, purge stock finie à 11:18:56,
  complément de 120 mm à 190 C, ligne d'amorce à 11:20:02, impression partie
  à 11:20:09. Aucun refus, aucune erreur du chargeur.
- Nuance : la purge stock chauffe à `flush_temp: 200`, pas 190. Journaux du
  5 au 10 septembre : fiche 220 → purge 220, fiche 200 → purge 200, fiche 190
  → purge 200. La purge suit donc la fiche avec un plancher à 200, dont
  l'origine n'est pas isolée (le G-code dit `filament_flush_temp = 0`). Sous
  le filet (205) ; sans effet pour du PLA à 190. Un fichier sous 185 C ferait
  refuser la purge par le filet : à traiter le jour où un tel fichier arrive
  (plafond du filet à `max(fichier + 15, 205)`, ou plancher retrouvé).
- Thomas règle le Z en direct sur la première couche : 0,14 → 0,03 à 11:25.

### Bruit connu, sans effet

- `Unknown command:SET_HOTEND_FAN` au départ (docs/70).
- `Error: no response` toutes les 11 s : balayage d'adresses du bus 485
  (`auto_addr_wrapper`, commande 161), présent toute la journée, sans lien
  avec l'impression.

## 10 septembre, 11:10 — alignement déployé et prouvé ; zéro Z à refaire ; le flux visé est écrit (remplacé par 11:25)

**Point de reprise en un geste :** relire les « Précisions de Thomas du
10 septembre » dans `GOALS.md` (le flux quotidien visé, point par point, avec
l'état de chacun), puis carré 280x280, réglage en direct,
`KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=…`, puis le cube. Ce cube
sera la première observation d'un vrai chargement avec l'alignement : le
journal doit dire `get next material temp: <température du fichier>`.

### Déployé à 11:06, vérifié à 11:07

- Les trois fichiers de la branche sont sur la machine (md5 identiques au
  dépôt), sauvegardes `.kctrl-bak-20260910-1106xx` à côté ; Klipper redémarré,
  prêt, machine à l'arrêt, chauffes à zéro.
- `KCTRL_MATERIAL_ALIGN` : « déjà à 200 C, rien écrit », puis `200 → 205`
  écrit et relu, puis retour `200`, puis refus net sur une fiche absente.

### Ce qui a été ajouté depuis 10:25

- `KCTRL_MATERIAL_ALIGN MATERIAL=<fiche ou type d'emplacement> TEMP=<°C>` :
  écrit la température du fichier dans la fiche que le chargeur va lire,
  atomiquement, et relit. `START_PRINT` l'appelle en première commande. Le
  chargeur relit la base à chaque chargement (prouvé le 9 septembre), la base
  n'est réécrite qu'à l'allumage (prouvé par les `uptime`), donc plus aucune
  correction à la main. Section 8 du document 67.
- 1193 tests verts ; les deux rouges préexistants inchangés.

### Ce qui reste ouvert

- Le changement de bobine en cours d'impression passe par le `cmd_T` d'origine,
  fiche d'usine si le matériau diffère de celui du départ ; à envelopper
  (`T0`..`T15`, `rename_existing`) dans une mission à part.
- La base est une réponse du cloud Creality téléchargée à chaque allumage
  avant la mise à l'heure (`reqId` daté 2020, `result.version` qui change
  d'un allumage à l'autre) ; le serveur Creality qui l'écrit n'est pas isolé.
  Sans conséquence avec l'alignement.

## 10 septembre, 10:25 — correctif du chargement écrit, à déployer ; zéro Z à refaire (remplacé par 11:00)

**Point de reprise en un geste :** déployer les trois fichiers de la branche
`fix/cfs-temperature-chargement` sur la machine (cat vers
`/usr/data/printer_data/config/` pour les deux `.cfg`, vers
`/usr/share/klipper/klippy/extras/` pour `kctrl_slot_map.py`), puis
`/etc/init.d/S55klipper_service restart`. Ensuite carré 280x280, réglage en
direct, `KCTRL_Z_SAVE PROFILE=k1_p001_t055_r001_n11x11 Z=…`.

### Ce que la matinée a établi

- Vis du plateau réglées par Thomas en trois passes (`KCTRL_BED_SCREWS`),
  écart final 0,08 mm ; voile résiduel 0,14 mm hors plan, hors de portée des
  vis.
- Mesh 11x11 refait à 09:52 (`KCTRL_MESH_CALIBRATE`, deuxième essai ; le
  premier a été refusé pour un contact aberrant de 0,07 mm sur la jonction
  sud-ouest / nord-ouest). Écrit dans `printer.cfg`, chargé.
- À 10:06, l'impression du cube s'est figée dans le chargement CFS : la base
  matière avait été **réécrite au redémarrage de 08:44** (Generic PLA à 220),
  la fenêtre a abaissé à 205, le chargeur a attendu 220 pour toujours. Arrêt
  d'urgence à 10:14, redémarrage Klipper, base recorrigée à 10:19.
- Le correctif (lecture de la fiche avant de chauffer, refus au lieu
  d'abaissement) est écrit et testé hors machine : 77 tests verts sur les deux
  fichiers concernés, 1174 sur la suite. Section 7 du document 67.

### Ce qui n'est pas prouvé

- Le correctif n'a pas encore tourné sur la machine.
- La base sera réécrite au prochain redémarrage ; le contrôle de `START_PRINT`
  le dira, mais rien ne la recorrige tout seul.

## 10 septembre, 01:20 — la machine est propre, la table des bobines est vide

**Point de reprise en un geste :** avant toute impression,
`KCTRL_SLOT SLOT=T2D TOOL=T1B`. Sans ça `START_PRINT` **refuse de démarrer**.

### Ce que la nuit a prouvé

Le correctif du changement d'outil **fonctionne**. Journal du départ de 00:51 :

```
00:53:23  cmd_T last_cmd=None, get_fialment_sensor_detect()=True
00:53:23  z_down move_z: 0.8          <- sain, contre 44.027 la veille
```

La coupe est arrivée **au début** de la séquence, avant tout chargement et
avant toute purge, et l'accumulateur Z n'a plus dérivé pendant `START_PRINT`.
Aucun `Move out of range` pendant le démarrage. La séquence est allée au bout :
chargement, purge, ligne d'amorce, première couche. **C'est le premier départ
complet depuis que le problème existe.**

### Ce qui a arrêté ce départ, et ce n'était pas la séquence

```
00:53:28  [box] cut to return failed          (x5 en 20 s)
00:53:48  key841 "cut error, cut sensor not detected, cutting not rebound"
00:53:48  error: printing to pause
```

Le capteur de coupe n'a pas vu la lame revenir. Cinq essais, abandon, pause.
Piège de lecture à connaître : la pause est décidée à 00:53:48 mais la purge et
la ligne d'amorce se déroulent **après**, jusqu'à 00:55:22, parce que Klipper
vide d'abord la file déjà tamponnée. Le dernier message du journal
(`SET_HOTEND_FAN`, `key61`) n'est **pas** la cause : il vient d'un webhook de
`/usr/bin/master-server`, pas du gcode, et tombe là par coïncidence.

Le cutter a ensuite refonctionné (`cut to return OK` à 01:03:45 et à 01:15:44)
sans que `box.cfg` change d'un octet — md5 `dd05b5bb69929389d233cc1e487a44de`
avant comme après, positions inchangées (`cut_pos_x: 38`, `cut_pos_y: 303.2`,
`cut_pos_offset: 1.3`). **Défaillance intermittente non expliquée.** Sauvegarde
`box.cfg.kctrl-bak-avant-calib-cutter-20260910`.

### La corruption Z de 01:07 : deux reprises superposées

```
01:05:36  cmd_T box_resume_extrude: last_tnn = T2D, tnn = T2D   <- le CFS reprend seul
01:07:05  record_z_pos: 2.410
01:07:05  record_z_pos: -40.590                                  <- 24 ms plus tard, -43.00 mm
01:07:05  Move out of range: 210.000 291.500 -40.590 [357.808]
```

Le CFS avait déjà fait sa reprise ; la relance depuis l'écran en a superposé une
seconde et le compteur Z a soustrait deux fois. **Ce n'est pas `START_PRINT`.**
Règle qui en sort : **un seul chemin de reprise**. Ne jamais relancer depuis
l'écran après un `box_resume_extrude`. La machine n'a pas été figée cette fois
(`idle_timeout: Ready`), aucun redémarrage Klipper n'a été nécessaire.

Confirmé au passage, et c'est la validation de la thèse de cause racine :
quand `last_cmd` vaut `T2D` et que l'outil demandé vaut `T2D`, le module fait
`box_resume_extrude` et **ne coupe pas**. La coupe n'a jamais eu lieu que sur
`last_cmd = None`.

### État machine au moment de la passation, vérifié

| | |
|---|---|
| `print_stats.state` | `cancelled` |
| chauffes | 0 / 0, en refroidissement |
| `homed_axes` | `''` |
| capteur de tête | **False** — filament retiré, tête vide |
| `box.last_cmd` | `None` |
| `kctrl_slot_map.map` | **`{}`**, `error: tnn_map vide` |
| `tn_data.json` | `tnn_map: None`, `last_cmd: None` |
| variables retenues | `kctrl_slot = T1A`, `slot_last_choice = T1B` |
| config déployée | md5 `3ca58a94014711baab93702d50dab0c7` |

L'annulation a vidé la table des bobines. Le repli `slot_last_choice` **ne
s'applique qu'à `T1A`** (par construction, voir
`test_the_remembered_slot_is_only_the_first_filament`), or le fichier démarre
sur `T1B`, et aucun `slot_choice_t1b` n'existe. Donc `chosen` est vide et
`START_PRINT` lève une erreur explicite au lieu de deviner — comportement
voulu, mais il **faut** réécrire la table avant de relancer.

Tête vide au prochain départ = `last_cmd None` + capteur False = **chargement
normal, aucune coupe**. C'est l'état nominal du CFS, et le cutter sort du
chemin critique pour ce départ-là.

### Ce qui reste ouvert, par priorité

Le rapport d'audit indépendant `docs/70-audit-independant-sequence-demarrage-v1.md`
tient la liste complète et sourcée (§4). Les trois premiers :

- **P1 — rendre l'accumulateur Z avant de sortir du bloc CFS.** `RESTORE_POSITION`
  après `BOX_MATERIAL_FLUSH`, ou remplacer `BOX_EXTRUDE_MATERIAL` +
  `BOX_GO_TO_EXTRUDE_POS` par le stock `BOX_START_PRINT_EXTRUDE_MATERIAL
  START_PRINT=8`. C'est la cause de fond des `Move out of range`.
- **P2 — faire échouer `START_PRINT` sur erreur CFS.** Constaté cette nuit :
  après `key841`, la séquence a continué à purger et à tracer comme si de rien
  n'était.
- **P5 — ligne d'amorce trop fine.** Défaut de conception assumé de
  `_KCTRL_PRIME_LINE` : monter le débit **et** la vitesse ensemble a fait
  *baisser* la section par trait — 0,133 mm² contre 0,150 mm² pour la stock,
  soit 0,37 mm de large contre 0,75. Les 3 passes donnent bien 2,7x la matière
  au total, mais chaque trait est deux fois plus fin que le stock. Correctif :
  descendre `variable_line_speed` de 9000 à 6000 (100 mm/s) à débit constant,
  ou suivre l'audit et plafonner à 15 mm³/s — le profil Orca officiel du
  `CR-PLA @K1 Max_CFS-C` déclare 18 mm³/s. Le zéro Z n'est **pas** en cause :
  `homing_origin Z = 0.14` est bien appliqué (écart mesuré entre
  `gcode_position` et `position`).

Non résolu et non expliqué : l'intermittence du capteur de coupe. Deux passages
du forum Creality cités par l'audit pointent des débris et le réglage de
`cut_pos` (TC2841).

### Tests

`tests/test_kctrl_zone_guard_v1.py` : **2 rouges assumés**, ils affirment que le
mouvement incriminé à Y 291,5 est refusé alors que `zone_y_min` vaut 296.
L'audit tranche (P4) : viser Y ≥ 285, et n'appliquer le plancher qu'en dehors
du palpage et pendant `printing`. Le garde n'est **pas déployé**.
Deux autres rouges préexistants et sans rapport :
`test_cfs_direct_owner_offline_v1::test_unload_requires_head_sensor_to_clear`,
`test_job_lifecycle_offline_v1::test_all_canonical_scenarios_are_implemented_once`.

---

# HANDOFF — index de reprise

Soiree du 8 septembre, apres la campagne : la hotend a lache — fils dessoudes,
chauffage commande a fond sans aucune montee. Thomas l'a remplacee par une piece
identique. Les resonances n'ont **pas** ete refaites, a raison : une hotend
identique ne change ni la masse ni la raideur de la tete. Le PID de la buse a
ete refait (`PID_CALIBRATE TARGET=220`) et ecrit a la main dans `[extruder]` :
`Kp 20,695 / Ki 1,533 / Kd 69,844` contre `25,013 / 2,566 / 60,966`. Sauvegarde
`printer.cfg.bak-avant-pid-20260908-233200`. Redemarrage fait a 23:41, valeurs **actives et verifiees** (PID, plus
`ei 42,6` / `mzv 46,6`). La table des bobines a survecu : `T1A -> T1B`.
Avance de pression laissee a `0,04` et zero Z laisse a `+0,05 mm`, sur
decision de Thomas. La machine est prete a imprimer. Voir document 66.

Appliqué le 8 septembre à 22:43, sur accord de Thomas : `ei 42,6 Hz` sur X et
`mzv 46,6 Hz` sur Y, en direct par `SET_INPUT_SHAPER` et à la main dans le bloc
`#*#` de `printer.cfg` (sauvegarde `printer.cfg.bak-avant-application-20260908-224352`).
Attention : `save_config_pending` est à `true`, Klipper garde en mémoire les
`ei 55.8` préparés par `SHAPER_CALIBRATE` ; un `SAVE_CONFIG` écraserait
l'édition manuelle et redémarrerait la machine. Le zéro Z et l'avance de
pression ont été refaits par Thomas lui-même.

Résultat de la campagne du 8 septembre, 22:10-22:25, après remplacement de la
buse et de l'extrudeur. Les quatre balayages ont tourné, les deux axes ont bien
été mesurés séparément. **Rien n'a été appliqué.** Y est nettement meilleur :
`mzv 46,6 Hz`, zéro vibration, accélération admissible `6 397` contre `4 500`.
X reste le point faible : `ei 42,6 Hz` et `22,3 %` de vibrations, contre
`24,7 %` le 2 septembre — le remplacement ne l'a pas réglé, aucun filtre ne
descend sous `12 %`. Courroies équilibrées, pic `44,7 Hz` des deux côtés.
Attention : `SHAPER_CALIBRATE` a écrit `ei 55.8` sur les deux axes dans le bloc
`#*#` — c'est la valeur de Y recopiée sur X, fausse de `13,2 Hz`, et elle
deviendrait active au prochain redémarrage. Les valeurs vivantes en mémoire
sont encore celles du 2 septembre. Sauvegarde :
`printer.cfg.bak-avant-resonance-20260908-221021`. Décision en attente de
Thomas. Voir document 65.

Toujours ouvert : la buse a changé, donc le zéro Z et l'avance de pression
(`0,044`) sont à reprendre avant les prochaines impressions.

Priorité du 8 septembre : la tête d'impression a été modifiée, les mesures de
résonance sont donc à refaire. La campagne est **préparée et validée, pas
lancée** — Thomas bricole encore sur la machine et on se recale avant de
mesurer. Un seul lancement,
`scripts/run-k1-control-resonance-campaign-v1.ps1`, une vingtaine de minutes :
les deux axes réellement mesurés chacun, les deux courroies séparément, les
cinq filtres évalués hors ligne, comparaison avec le 2 septembre, rien
d'appliqué. L'analyseur a été passé sur les CSV du 2 septembre et les reproduit
au dixième près (`ei 40,2 Hz / 24,7 %` sur X, `mzv 39,0 Hz / 0,0 %` sur Y).

À savoir : le calibrage de la machine a tourné ce soir à 21:47 depuis l'écran.
Il n'a mesuré **qu'un seul axe** — les deux CSV ont la même empreinte
`bd083f5c…` — et a écrit `ei 56.2` sur les deux axes dans le bloc `#*#`,
effaçant la série du 2 septembre. Ne pas le relancer depuis l'écran. Notre
campagne échoue explicitement si les deux axes rendent le même fichier.
Question ouverte et bloquante pour la suite : **ce qui a été changé sur la
tête**. Si la partie chaude ou la géométrie ont bougé, le zéro Z et l'avance de
pression (`0,044`) sont à reprendre aussi. Voir document 64.

## Priorité du 5 septembre au soir — le départ ne refuse plus une buse chaude

Trois départs se sont arrêtés au même octet dans la journée : 16:21, 16:43 et
17:47. Le correctif du matin agissait sur le profil de tranchage et sur une
copie du fichier ; il ne pouvait rien pour les fichiers déjà tranchés, et c'est
l'original qui a été relancé.

La cause était dans le garde de palpage, pas dans le fichier : une **cible**
buse au-dessus du plafond interrompait la séquence, alors qu'une **température**
au-dessus du plafond était simplement coupée et attendue. Une cible est
maintenant coupée et annoncée elle aussi. La protection ne change pas : pendant
la fenêtre, `M104` et `M109` au-dessus du plafond restent refusés et la buse est
toujours ramenée sous le plafond avant tout contact.

Posé sur la machine, `FIRMWARE_RESTART` fait, prouvé à froid : cible `220 C`
debout, buse `75,5 C`, la fenêtre s'ouvre sans erreur et la cible retombe à
zéro. Aucun mouvement, aucun contact.

**Pour relancer** : essuyer la buse à la main — le capteur de tête voit encore
le filament laissé par les purges avortées, et une bavure figée fausserait le
contact (ADR-045) — puis lancer depuis l'écran, l'application ou la page web
Creality, pour garder le popup de correspondance des bobines. N'importe lequel
des deux fichiers convient désormais, l'original comme la copie
`_KCTRL-fixed.gcode`. Reprendre du début, pas de reprise en cours de fichier.

État au moment d'écrire : table CFS lisible, premier filament sur `T1B` ;
profil `k1_p001_t055_r001_n11x11` présent, Z accepté `+0,050 mm` ; chauffes à
zéro, rien en cours. Détails : `docs/63-depart-tolere-buse-deja-chaude-v1.md`
et ADR-059. Le correctif du matin est décrit dans le document 62.

La suite du document décrit la clôture historique du 2 septembre.

## Reprise immédiate

**Lancer les impressions depuis l'écran tactile, l'application Creality ou la
page web Creality.** C'est là que vit le popup d'origine : les filaments du
G-code avec leurs couleurs d'un côté, les bobines du CFS de l'autre, on les met
en face, et il n'y a rien d'autre à faire. Fluidd et Mainsail n'ont pas ce
popup — c'est pour cela que tout partait sur `T1A`.

`START_PRINT` lit maintenant la réponse du popup. Le rechargement automatique en
cours d'impression est armé.

Sans écran dans la boucle, trois commandes font le même travail :

```
KCTRL_MAP                        voir la correspondance filament -> emplacement
KCTRL_SLOTS                      voir les bobines et celle qui partira
KCTRL_SLOT SLOT=T2B TOOL=T1B     forcer une correspondance
```

Détail, preuves et journaux : `docs/55-popup-de-correspondance-des-filaments-v1.md`
et ADR-056. Session précédente : doc 54 et ADR-055.

**Le Z accepté se tape maintenant dans l'éditeur de maillage** (port `7130`),
dans la barre du haut, à côté du profil. « Reprendre » recopie le décalage en
vigueur sur la machine — celui que l'on vient de trouver à l'œil pendant une
première couche — et « Enregistrer Z » le garde pour ce profil. Il s'applique au
démarrage d'impression suivant. Doc 56 et ADR-057.

**L'écran brosse la buse tout seul avant de démarrer, c'est normal.** Il envoie
`CX_NOZZLE_CLEAR` directement par l'API, et cette macro Creality chauffe le lit
à `50 C` — sa valeur par défaut, pas celle du fichier. Notre `START_PRINT` ne
brosse pas et ne recalibre rien. Voir un brossage et un lit à 50 au lancement
n'est donc pas le signe que la mauvaise séquence part.

**Les ondulations ne viennent pas du maillage.** Longueur d'onde mesurée à la
règle : `3 à 10 mm`, là où les points du maillage sont espacés de 29 mm. Le
document 58 se trompait de cause. Ce qui reste vrai du 58 : le `11 × 11` porte
bien `0,08 mm` d'ondulation crête à crête sur 60 mm, et un repalpage après
nettoyage sous la feuille magnétique reste utile — mais pour le maillage
lui-même, pas pour ce défaut-là.

**L'input shaping est mesuré et appliqué.** X tournait à `57,2 Hz` recopié de Y
alors qu'il résonne autour de `40 Hz`, et à 270 mm/s cela fait une ondulation
tous les 6 à 7 mm — exactement le relief senti sur les couches 2 et 3. En
vigueur et écrit dans `printer.cfg` après deux séries de mesures : X `ei` à
`40,2 Hz`, Y `mzv` à `39,0 Hz`. Modifier le maillage ou le Z n'a aucun effet sur
ce réglage.

**Les courroies sont bonnes, ne pas y toucher.** Mesurées séparément, elles
tombent à `0,3 Hz` l'une de l'autre — `39,8` et `40,1 Hz`, même largeur, même
énergie. Le resserrage des vis fait par Thomas a fait monter X de `36,0` à
`40,2 Hz` et effondré la forêt de bosses parasites.

**Il reste un pic à `14,0 Hz` sur X, et sur X seulement** : 35 % de l'énergie
sous 30 Hz, contre 4 % sur Y et 1,5 % sur chaque courroie. Trop bas pour une
courroie ou un rail, c'est une masse entière qui se balance — support, pieds,
CFS posés contre la machine, panneaux. À 270 mm/s il produit des vagues de
19 mm, donc ce n'est **pas** le défaut visible (mesuré à 3-10 mm, soit le pic à
43 Hz, que le filtre corrige). Piste de fond, pas urgence. Doc 61.

**La surextrusion à l'arrivée du remplissage sur les parois est diagnostiquée**,
et ce n'est pas le maillage : le `pressure_advance_smooth_time` de `0,040 s` est
plus long que les rampes de freinage de la machine, qui durent `0,029 s`. Rien
n'a été corrigé ni testé, la calibration demande une impression. Doc 57.

## État réel

La machine est au repos et cohérente avec le dépôt. Relevé à la clôture :
Klipper `ready`, impression `standby`, chauffes à `0`, maillage actif
`k1_p001_t055_r001_n11x11`. Les empreintes des deux fichiers que nous possédons
sur la machine sont identiques à celles du dépôt :

```
k1-control-owned-start-print-v2.cfg   c46527dc369d7d327a1521a1feba8f13
kctrl_wait.py                         b8a680c3cdd5c1faac0f066920eeb548
kctrl_slot_map.py                     e446f4de6e14308e243ac363acb7a335

mesh-editor/server.py                 5fb3fb44765c8f1f2404029530e1de26
mesh-editor/www/app.mjs               6c0af23d7d0adf546051b92726c781ba
mesh-editor/www/index.html            894334d9bf9ff81ccf9ba2cd69b742a4
mesh-editor/www/styles.css            957f037e67bacd1102bff7653e3f37d3
```

Suite complète en local : `1053` verts, `2` rouges laissés volontairement (voir
plus bas).

Une CI GitHub tourne désormais à chaque poussée et sur chaque PR
(`.github/workflows/tests.yml`) : `pytest` et les tests du front de l'éditeur
de maillage. Elle couvre `834` tests. Elle **ne peut pas** couvrir seize
modules qui s'appuient sur les captures brutes de `inventory/raw/`, que
`.gitignore` garde volontairement hors du dépôt — identité machine, relevés
privés, G-code de plusieurs mégaoctets. Ces seize-là ne tournent que sur la
machine qui détient les preuves, et ils sont nommés un par ligne dans le
workflow plutôt que masqués derrière un motif.

### Ce que cette session a fermé

**La purge de démarrage est sous notre contrôle et bornée des deux côtés.**
Rien ne pousse de filament tant que le capteur de tête ne le voit pas :
`KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2 TIMEOUT=15`, une commande Python
et non un macro — un `G4` dans un macro appelé depuis `START_PRINT` n'est jamais
mis en file, ce qui a été mesuré et documenté dans l'ADR-053. La buse est
chauffée et attendue avant la première poussée. Le complément de purge vaut
`120 mm` : `200` donnent la boule qui se décroche, `180` débordent du bac,
`120` est le plafond retenu par Thomas. Réglable à chaud par
`SET_GCODE_VARIABLE MACRO=_KCTRL_PURGE_BALL VARIABLE=purge_mm VALUE=<n>`.

**L'éditeur de maillage corrige au pas et par sélection multiple.** Pas de
`0,005` / `0,01` / `0,02` / `0,05`, accélération à la répétition, rectangle avec
`Maj`, ajout et retrait avec `Ctrl`, anneau, annulation par groupe. ADR-052.

**La surface imprimable réelle est établie** : `X 0 → 300`, `Y 0 → 295`,
`Z 0 → 300`. La limite `Y` est appliquée ligne par ligne pendant l'impression
dès qu'un CFS est déclaré et met l'impression en pause. Elle n'est pas relevée,
et pourquoi est écrit dans l'ADR-054.

### Écarts ouverts, mesurés

- **`Tn_extrude_temp` est descendu à `200`** dans `box.cfg` le 2 septembre. La
  clé n'est pas modifiable à chaud : `MODIFY_BOX_CFG TN_EXTRUDE_TEMP=` répond
  `success` sans rien enregistrer, et `SAVE_BOX_CFG` confirme `ok:no save`. Une
  session PETG demande de remonter la valeur dans le fichier puis de redémarrer
  Klipper. Voir doc 54 et ADR-055.
- **Le rechargement automatique n'est pas encore prouvé de bout en bout.** Toute
  la chaîne est vérifiée pièce par pièce, mais seule une bobine réellement
  épuisée en cours d'impression peut le démontrer.
- **Le popup de correspondance n'a pas été vu tourner.** La table qu'il écrit
  est lue et prouvée à froid, mais aucune impression n'a été lancée depuis
  l'écran. Premier vrai départ à faire par Thomas. Voir doc 55.
- **Le multi-filament n'a jamais tourné sur cette machine.** Les changements de
  couleur passent par le `cmd_T` stock, qui lit les volumes de purge dans le
  fichier tranché ; rien de tout cela n'a été exécuté ici.
- **Le rapport de purge ne mesure rien d'utile.** Il a affiché `-2 mm` : les
  routines box émettent des `G92 E0` dans l'étape matière et l'axe extrudeur
  repart de zéro sous le repère. Il le dit désormais au lieu d'afficher un
  chiffre faux. Le compteur honnête est la position du moteur pas à pas, que
  `G92` ne touche pas, et se lit en Python.
- **Le Z accepté est stocké en un seul enregistrement global**, pas par profil
  de mesh. Préalable bloquant à toute campagne multi-températures.
- **Chaque `FIRMWARE_RESTART` remet le maillage actif sur `default`.** Il faut
  recharger `k1_p001_t055_r001_n11x11` derrière, sinon l'impression part sur un
  maillage vide.
- **L'éditeur de maillage est un service depuis le 2 septembre au soir**,
  `/etc/init.d/S58k1_control_mesh_editor`, posé par
  `scripts/deploy-k1-control-mesh-editor-v1.ps1`. Il démarre avec la machine.
  `Ouvrir-Editeur-Maillage-K1-Max.cmd`, à la racine, monte le tunnel et le
  relance s'il manque. Le démarrage au boot lui-même n'a pas encore été prouvé :
  aucun redémarrage complet n'a eu lieu depuis la pose.
- **`Tnn_map` ne survit pas à la machine.** Un arrêt d'urgence ou une coupure
  rend un `tn_data.json` sans la table, et seul le popup de l'écran la remplit.
  `START_PRINT` se rabat désormais sur `slot_last_choice`, le dernier
  emplacement choisi par `KCTRL_SLOT`, et le dit sur sa ligne de démarrage.
  `KCTRL_SLOTS` affiche la même résolution avant de lancer. Voir ADR-058.
- **Deux tests laissés rouges volontairement**, ils signalent des divergences
  réelles et non des tests à réparer :
  `test_all_canonical_scenarios_are_implemented_once` (divergence
  `end_full_unload` du design contre `end_keep_engaged` du moteur) et
  `test_unload_requires_head_sensor_to_clear`.

### Pièges de la machine, à ne pas redécouvrir

- `FIRMWARE_RESTART` relit la configuration mais **pas** les modules Python.
  Modifier `kctrl_wait.py` ou `kctrl_slot_map.py` exige
  `/etc/init.d/S55klipper_service restart`, qui remet le maillage actif sur
  `default` — le recharger derrière. Si
  les contrôles de mouvement de l'écran meurent ensuite :
  `/etc/init.d/S99start_app restart`.
- **Vérifier `print_stats.state` avant toute commande machine.** Une impression
  peut avoir été lancée depuis l'écran entre deux échanges, sans que rien ne le
  signale ici. Le 2026-09-02 un `TURN_OFF_HEATERS` est parti sur une machine
  qu'on croyait au repos : la buse est tombée de `190` à `175 C` en pleine
  première couche avant d'être rétablie.
- **Ne jamais lancer `SAVE_CONFIG` sur cette imprimante.** Attention : la règle
  ne couvre pas tout. `SHAPER_CALIBRATE` écrit dans `printer.cfg` de lui-même,
  sans qu'aucun `SAVE_CONFIG` soit demandé — observé le 2026-09-02, journal
  `save_config: set [input_shaper] shaper_freq_x = 50.6`. Sauvegarder le fichier
  **avant** de lancer la commande, pas après. Doc 60.
- `scp` n'existe pas ici. Déployer par `ssh hote "cat > /chemin" < fichier`.
- `grep` n'a pas `--include`, `pkill` n'existe pas, `curl` refuse `-s`, `-S`,
  `-o` et `-w`.
- Un `.pyc` voisin de `kctrl_wait.py` est présent et cohérent avec la source
  (généré à l'import). Après tout redéploiement du module, vérifier qu'il a bien
  été régénéré avant de conclure sur un comportement.

## Règle absolue avant tout palpage

**Aucune calibration, aucun palpage Z, aucun démarrage d'impression sans que
Thomas ait nettoyé la buse à la main et l'ait dit.** Le nettoyage manuel impose
que le filament soit rétracté avant. Le nettoyage automatique de brosse n'a
jamais fonctionné et a été retiré de la séquence possédée : il n'existe aucun
substitut. Une mesure prise sur une buse sale n'est pas dégradée, elle est
fausse et se propage dans un profil persistant. Voir ADR-045.

Ordre imposé : retrait filament, nettoyage manuel confirmé, chauffe, palpage.

## Voie CFS stock : rétablie et prouvée

Le blocage de trois semaines est levé. Après bascule des trois inclusions en
variante `disabled` et redémarrage Klipper, un cycle complet retrait puis
chargement a été exécuté depuis l'écran et capturé par
`gcode/subscribe_output` : coupe réelle (`cut sensor state:1` puis `:0`),
rembobinage CFS effectif, puis chargement jusqu'à `box.T1.filament: A` avec
purge visible et filament correctement inséré, confirmé par Thomas.

État physique après ce cycle : `box.state connect`, `box.T1.filament A`,
`T1.mode 2`, les deux capteurs filament vrais, cibles de chauffe à zéro,
`X/Y` référencés, `print_stats standby`. La machine peut produire.

Le tronçon de filament qui maintenait `filament_sensor` à vrai venait d'un
rembobinage sans coupe antérieur ; il n'a jamais bouché le chemin. Aucune
intervention mécanique n'est nécessaire.

ADR-044 fixe la règle : aucune garde ne doit être réinstallée sur les
primitives `BOX_*` sans une capture équivalente pour son remplaçant.

**Défaut relevé au passage, traité depuis** : la purge annonçait
`flush_temp: 220`, issu de `Tn_extrude_temp` codé en dur dans `box.cfg`. La
valeur est à `200` depuis le 2 septembre. Voir doc 54.

## Verrou CFS et sortie de secours

Le 1er septembre, aucun retrait de filament n'était possible : le composant
`k1_control_cfs_direct_owner`, posé `enabled: true` avec
`stock_commands_blocked: true`, refuse toute commande `BOX_*`, et son propre
retrait n'a jamais été implémenté. Onze refus `stock_effect_command_blocked`
ont été capturés, y compris sur les tentatives manuelles depuis l'écran. Le
firmware Creality n'est pas en cause. Voir ADR-043 et le document 52.

**Sortie de secours officielle**, dans `printer.cfg` :

```
[include k1-control-cfs-direct-owner-disabled-v1.cfg]
[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]
[include k1-control-stock-geometry-handoff-disabled-v1.cfg]
```

puis redémarrage Klipper. Les includes `k1-control-z-mesh.cfg` et
`k1-control-calibration-path.cfg` restent en place : le Z et le mesh sont
conservés. Retour arrière : remettre les trois `-active-`. Sauvegarde machine :
`printer.cfg.bak-before-cfs-unblock`.

## Prochaine action

Machine froide, Thomas présent, dans cet ordre :

D'abord, deux gestes courts qui ne demandent pas la machine chaude :

- **Enregistrer le Z réellement voulu.** Le profil porte `+0,040 mm` alors que
  Thomas a imprimé à `0`. Ouvrir l'éditeur de maillage, « reprendre »,
  « Enregistrer Z » : le démarrage suivant part sur la bonne hauteur.
- **Passer `pressure_advance_smooth_time` à `0,020 s`**, puis une tour de
  réglage du Pressure Advance pour le PLA. Doc 57 porte le calcul et l'ordre
  des opérations.
- **Juger la pièce en cours à l'ongle**, couches 2 et 3 : le relief doit avoir
  disparu. C'est la seule preuve que le nouveau réglage fonctionne, et elle
  n'est pas encore faite. Réserve : cette impression a subi une chute de
  température de `190` à `175 C` en première couche, sans effet attendu sur les
  couches 2 et 3. Doc 60 et 61.
- **Baisser l'accélération du trancheur.** Le profil imprime le remplissage
  plein à `9500 mm/s²` ; les mesures conseillent `3000` sur X et `4500` sur Y.
  Au-delà, le filtre arrondit les angles. Doc 60.
- **Chercher d'où vient le pic à 14 Hz** : support qui fléchit, pied qui
  balance, CFS posés contre la machine, panneaux mal fermés. Ce n'est pas le
  défaut visible, mais c'est ce qui empêche X de descendre sous 20 % de
  vibrations restantes. Doc 61.
- **Nettoyer sous la feuille magnétique, la reposer, repalper le `11 × 11`** et
  comparer au maillage en vigueur. C'est l'expérience qui tranche. Doc 58.

Ensuite :

1. **Un vrai départ depuis l'écran tactile**, buse nettoyée à la main au
   préalable. C'est le seul test qui prouve le popup, la correspondance et le
   chargement sur la bobine choisie. Vérifier ensuite `KCTRL_MAP` : il doit
   montrer ce qui a été choisi à l'écran.
2. **Un multi-filament**, deux couleurs, pour voir les changements d'outil et
   les purges du trancheur. Jamais exécuté sur cette machine.
3. **Confirmer les `120 mm`** de purge à l'œil au-dessus du bac.
4. **Refaire le compteur de purge en Python**, sur la position du moteur pas à
   pas, immune aux `G92`. Il remplacera l'arithmétique par un nombre.
5. Correctif Z-par-profil, puis bande de température supplémentaire.
5. Ligne d'amorce sur `CX_PRINT_DRAW_ONE_LINE_V2`, vitesse portée d'environ
   `F3000` à `F9000`.
6. Rendre le serveur de l'éditeur de maillage persistant au redémarrage.
7. Retirer la ligne `KCTRL_PRODUCTION_ARM` du profil Orca.
8. Capture automatique du Z avant que `END_PRINT` le remette à zéro.
9. Rechargement automatique en fin de bobine — bloqué tant que `END_PRINT` ne
   nous appartient pas, à faire délibérément et à froid.

Lire dans cet ordre à la reprise : ce fichier, `STATE.md`, puis les ADR 053 et
054 pour la purge et la surface imprimable, 052 pour l'éditeur de maillage.

## Archive

L'état du 1er septembre — capteur du cutter qualifié, voie CFS stock
rétablie, recadrage de périmètre — est consigné dans les ADR-041 et 042 et
dans `STATE.md`. Il n'est plus repris ici parce qu'il ne pilote plus
l'action.

La passation détaillée précédente, `HANDOFF-CUTTER-SENSOR-PAUSE-2026-09-01.md`,
reste consultable pour l'historique des preuves. Sa liste de gestes humains est
en revanche **périmée** : son point 2, l'appui manuel sur le levier, est retiré
par ADR-041.

Le contenu ci-dessous est conservé comme archive historique. Il décrit l'état
antérieur à la qualification du capteur et ne doit plus piloter l'action.

# Archive — reprise après refus réel du cutter le 1er septembre 2026

La quantité de purge est corrigée et installée : la reprise fautive utilisait
`30 mm`, alors que le chargement initial stock observé utilise `140 mm`. Le
cycle lit désormais le vecteur et la matrice Orca du G-code ; le fichier
d'essai courant demande notamment `266,081080 mm` pour une transition `0→1`.

Le dernier essai s'est arrêté proprement avant retrait. La tête a essayé la
position stock `X38 Y304,5`, puis des pas de `0,5 mm` jusqu'à la limite publiée
`Y307,5`. Le capteur `cut_pos` est resté à `0` partout. Aucune commande de
retrait n'a donc été envoyée. `T1A` reste chargé, les deux capteurs filament
sont actifs, les chauffes sont à zéro, les axes sont libérés, le mesh
`k1_p001_t055_r001_n11x11` est actif et le Z accepté reste `−0,04 mm`.

Ne pas rejouer automatiquement le cutter et ne jamais dépasser `Y307,5`. La
prochaine étape est une vérification mécanique réelle, à froid, du levier du
cutter et de son capteur. ADR-040 et le `RESULT.md` du paquet
`stock-derived-cycle-activation-v1` sont les références canoniques.

Un moniteur manuel en lecture seule est prêt. Le préflight froid et la caméra
sont verts ; sa première fenêtre de `90 s` n'a vu aucune transition, mais
l'appui humain n'a pas été confirmé. Ne pas en déduire une panne. La prochaine
preuve est l'appui puis le relâchement du poussoir/levier solidaire de la tête,
avec observation obligatoire de `cut_pos : 0→1→0`.

Le texte ci-dessous est l'archive de la reprise précédente.

# Archive — reprise après KO borné de la V1 physique directe

La gate
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` est close KO et ne
doit jamais être rejouée. Capture privée :
`20260831-132914-g4-k1-control-cfs-direct-owner-physical-load-unload-v1`.
L'activation s'est arrêtée sur `stock_auto_refill_invalid` après restart, avant
chauffe, trame CFS, moteur filament ou mouvement d'axe. Le rollback a remis
`enabled=false`, zéro cible, axes libérés, `11 × 11` et Z `−0,04`. Les deux
capteurs sont toujours actifs : le filament initial est resté engagé.

Thomas a corrigé la frontière produit et ADR-037 la rend canonique : tout
retrait passe d'abord par la position cutter et la coupe ; tout chargement est
immédiatement suivi d'une purge dans le vrai bac, de `3 à 4` allers-retours
francs de décrochage, puis d'une preuve caméra. Aucun palpage ou mesh après
insertion. La prochaine mission est uniquement
`G4-K1-CONTROL-CFS-CUTTER-PURGE-INTEGRATED-R2-OFFLINE-V1` : construire et
tester la chorégraphie complète hors imprimante, y compris la persistance
d'`auto_refill`, avant toute nouvelle action physique.

Le texte ci-dessous décrit l'état précédent et reste une archive.

La reprise canonique est désormais :

`docs/51-proprietaire-cfs-direct-candidat-pose-desactivee-v1.md`

ADR-036 est acceptée et `cfs-direct-owner-offline-v1` obtient `24/24`. Le cycle
intégré ne dépend plus d'aucun effet `BOX_*`. Le candidat désactivé obtient
`13/13`, puis il est posé sous
`20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1`. Le
composant est chargé avec `enabled=false`, transport non pris, commandes stock
non remplacées et zéro trame CFS. Une validation intégrée et deux validations
indépendantes sont vertes. L'état final est froid, au repos, axes libérés,
`11 × 11` actif, Z `−0,04`, deux CFS connectés et aucune route logique.

L'ancienne tranche annoncée était
`G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` : activer sous
surveillance, qualifier un seul cycle direct `T1A`, puis remettre un état sûr.
Cette tranche est maintenant close KO et remplacée par ADR-037.

Lire le document 51, ADR-036, puis les derniers blocs de `STATE.md`, `GATES.md`
et `DECISIONS.md`. Le contenu ci-dessous est conservé comme archive des
clôtures antérieures ; il ne décrit plus l'état actuel et ne doit pas piloter
la prochaine action.

L'observabilité V2 est qualifiée hors imprimante puis sur la vraie K1. La gate
d'effet a ensuite désactivé une fois l'auto-remplacement stock, prouvé deux fois
la valeur `0`, restauré une fois la valeur précédente `1` et prouvé deux fois
ce retour exact. Le verdict final est
`CLOSED_OK_EXCLUSION_AND_EXACT_RESTORE_QUALIFIED`. Les captures sont consommées
et ne doivent pas être rejouées.

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est terminé hors imprimante et
`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé en lecture seule. La capture
canonique de ce second Goal reste
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le Goal 3 reste en
cours à `2/7` ; le nettoyage automatique est clos KO et le nettoyage manuel
est obligatoire.

`G4-K1-CONTROL-CFS-OWNER-CORE-OFFLINE-V1` reste clos avec `21/21` scénarios.
Son successeur `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1` est
maintenant clos avec `25/25` scénarios et `15/15` tests ciblés. Le garde pur
sauvegarde la valeur stock, prépare au plus une désactivation non exécutable,
exige deux lectures qui prouvent l'effet puis restaure exactement la valeur
précédente. Un acquittement seul ne prouve rien et un résultat incertain n'est
jamais rejoué.

Le vrai Z accepté `−0,04 mm` vient de `KCTRL_STATE`, sous une connexion
Moonraker persistante. `T1/T2`, l'absence de route, les chauffes zéro, le mesh
`11 × 11` et les configurations sont inchangés. Aucun filament, mouvement,
chauffage, fichier distant ou service n'a été touché. Le Goal 3 reste à `2/7`.

La prochaine mission unique est `G4-K1-CONTROL-START-SEQUENCE-OWNER-V1`.
Il faut d'abord rendre son candidat hors imprimante installable et réversible ;
la pose et l'essai physique resteront une tranche distincte. La production et
les primitives filament non qualifiées restent fermées.

## Archive historique — clôture initiale du Goal 2

Date de passation : 2026-08-27
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Branche cible : `main`
Nouvelle tâche créée : non
Goal actif : absent après clôture

## État à annoncer immédiatement à Thomas

- **`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est terminé.**
- La lecture réelle est qualifiée sans effet, mais la suite physique est
  bloquée : le mesh actif `default` diffère du profil robuste requis.
- Le profil robuste `k1_p001_t055_r001_n06x06` existe encore avec sa bonne
  empreinte ; il n'a pas été chargé, car le Goal 2 l'interdisait.
- Aucune impression, G-code, écriture distante, chauffe, mouvement, restart,
  action CFS ou reconnexion provoquée n'a eu lieu.
- La production reste fermée et le mode Précision reste caché.
- Cette session source doit rester visible et ne doit pas être archivée.

## État livré

La capture privée retenue est
`20260827-142853-goal-p4-k1-read-only-qualification-v1`. Le nettoyage a lieu sur
la K1 avant le retour local : aucun numéro de série, UUID, nom de fichier
d'impression ou contenu de configuration n'est exporté.

Deux lectures stables confirment Klippy prêt, l'imprimante en `standby`, les
cibles à zéro, les axes libérés, `T1/T2` connectés, `T3/T4` non configurés,
aucune route engagée, `t_command` vide, le capteur de tête actif et le Z accepté
à `−0,04 mm`. L'identité filament reste donc classée `engaged_unknown`.

Les lectures d'état ont pris `199,212 ms` et `235,525 ms`, sous le plafond de
`5 s`. La forme est identique entre les deux réponses. Les douze empreintes de
configuration, composants Moonraker et fichiers UI correspondent aux versions
revues et sont identiques avant/après.

Le seul écart bloquant est réel : le mesh actif `default` et le profil robuste
requis `k1_p001_t055_r001_n06x06` sont tous deux des matrices `6 × 6`, mais
leurs empreintes diffèrent. Le robuste existe toujours ; il n'est simplement
pas actif. Le statut fermé est `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

Le collecteur `GET`, la traduction pure, le délai et la règle d'invalidation du
mapping sont qualifiés. Une reconnexion très courte qui revient au même état
entre deux sondages reste invisible ; le futur composant Moonraker devra donc
prendre son époque dans les notifications.

Le pilotage macro est maintenant centralisé dans `GOALS.md` :

1. `GOAL-P4-OFFLINE-CYCLE-CFS-V1` — terminé hors imprimante ;
2. `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` — terminé en lecture seule avec KO
   borné du mesh actif ;
3. `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` — installer et qualifier les
   fonctions physiques par petites tranches avec Thomas présent, après le
   chargement contrôlé du profil robuste ;
4. `GOAL-P4-DAILY-CUTOVER-V1` — basculer enfin vers le fonctionnement quotidien
   complet avant la campagne G5.

Ces noms sont des regroupements de pilotage. Ils ne remplacent pas les gates de
`GATES.md` et ne donnent aucune autorité d'installation ou de production.

## Git vérifié avant le commit de cette passation

- base de mission : `5927a7ff49b67dc52a9ae5af6f1a1193ff19003a` ;
- `main` local et `origin/main` étaient alignés sur cette base ;
- divergence : `0/0` ;
- checkout propre au départ ;
- un seul worktree ; travail réalisé sur `codex/k1-read-only-qualification-v1` ;
- aucune branche de mission ou ressource étrangère observée ;
- le SHA final contenant cette passation sera communiqué dans le compte rendu.

## Vérifications réutilisables

- preuve live nettoyée : **OK**, `2/2` lectures ;
- schéma réel : **OK**, stable et épinglé ;
- délai de lecture : **OK**, maximum observé `235,525 ms` sous `5 s` ;
- empreintes distantes : **OK**, exactes et inchangées ;
- CFS, Z et état au repos : **OK** pour la lecture seule ;
- mesh actif conforme au contrat quotidien : **KO borné** ;
- validation physique ou humaine : **non exécutée**, hors périmètre ;
- effet sur la K1 : **aucun** ;
- suite complète : **OK**, `488` tests exécutés, `485` verts et `3` ignorés ;
- scripts PowerShell : **OK**, `29` fichiers relus sans erreur.

## Prochaine mission unique

### Gate préalable au `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

Thomas doit être devant la K1. La prochaine gate vérifiera l'état sûr et les
empreintes, chargera uniquement `k1_p001_t055_r001_n06x06`, puis relira le nom
actif et la matrice sans lancer d'impression. Elle s'arrêtera au premier écart
et gardera un retour arrière exact.

Relire dans cet ordre : `HANDOFF.md`, `GOALS.md`, le document 41, le `RESULT.md`
et le contrat du paquet `k1-read-only-qualification-v1`, puis le plan futur.

Cette action modifie l'état d'exécution de la K1 et exige une nouvelle
autorisation explicite ; le Goal 2 clos ne l'autorise pas. Concrètement, le
prochain GO permettra seulement de charger le profil robuste déjà présent et
de vérifier sa matrice, pas d'imprimer ni de commencer toutes les tranches du
Goal 3.

Modèle conseillé : `gpt-5.6-terra`, raisonnement `high`, car la tâche est petite
mais touche du matériel réel et doit distinguer précisément profil, matrice et
rollback. Option économique : `gpt-5.6-terra` en `medium`, avec un risque plus
élevé de reprise si un état transitoire ou une incohérence de preuve apparaît.
