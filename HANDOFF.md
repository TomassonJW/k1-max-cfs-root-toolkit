# HANDOFF — index de reprise

## Priorité du 5 septembre 2026 — départ Orca corrigé

Deux tentatives du même travail s'arrêtaient sur la protection de palpage :
220 °C demandés alors que le plafond vaut 105 °C. Le profil Orca **Copie**
envoyait `G28` puis `T0` avant `START_PRINT`. Le `T0` chargeait et purgeait
T1B avant la référence voulue par notre démarrage. Correction limitée au
champ de départ du profil, aligné sur **CopieBIS**, et à une copie du G-code
sur la K1 portant le suffixe **`_KCTRL-fixed.gcode`**. L'original est conservé.
Les macros, le CFS, le maillage et le Z enregistré restent inchangés.

La copie est visible dans Moonraker et vérifiée intégralement : seuls sept
octets ont été retirés, et les `50 877 329` octets à partir de `START_PRINT`
sont identiques. Aucun essai physique, aucune chauffe, aucun mouvement et
aucun redémarrage n'ont été envoyés. Au dernier relevé, le filament est encore
détecté dans la tête, les cibles sont nulles et le travail précédent est en
erreur. Ne pas reprendre le fichier interrompu en cours de route : le nouvel
essai doit repartir du début de la copie après désengagement officiel et
nettoyage manuel confirmé de la buse (ADR-045).

Si Orca était ouvert pendant la correction, recharger le profil corrigé avant
le prochain tranchage ; la modification sur disque ne prouve pas le contenu
déjà chargé dans l'application. Détails :
`docs/62-correctif-depart-orca-g28-t0-v1.md`.

La suite du document décrit la clôture historique du 2 septembre.

Mise à jour : 2026-09-02 au soir, après la session « le Z accepté dans
l'éditeur de maillage », le diagnostic des ondulations, et deux séries de
mesures de résonance. Une impression tournait à la clôture.

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
