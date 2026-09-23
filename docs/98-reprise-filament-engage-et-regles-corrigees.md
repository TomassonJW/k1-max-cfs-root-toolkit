# 98 — Reprise avec filament engagé : intégration locale et validation restante

Date : 23 septembre 2026. **Reprise et fin validées en réel par Thomas.** Le
dernier ajustement de température est testé et installé à froid, sans nouvel
essai physique après ce delta. La fin `end-rewind-confirm-v3` reste inchangée.

## Résultat du diagnostic physique précédent

Après rétablissement du courant extrudeur nominal (0,55 A configuré,
0,561526 A relu) et passage explicite du CFS T1B en mode PRINT, une avance
de 5 mm a consommé le tampon. La purge suivante a poussé 120 mm en six
portions à 2 mm/s. Les six lectures du tampon indiquent « milieu ». Thomas
confirme le débit et la boule décrochée.

Cette réussite ne sépare pas l'effet du courant de celui du mode CFS ; elle
ne prouve donc pas à elle seule la cause exacte de la première prise ratée.
La route logique du CFS reste vide : aucune finalisation logicielle de
chargement n'a été inventée à partir du seul capteur.

Aucun homing, restart, retrait ou M112 n'a été envoyé pendant cet essai.
Une palpation précise existe dans le journal avant l'échec, à 09:31 (horloge
K1). Thomas ne sait pas si les références ont pu être affectées ensuite.
La prochaine impression doit donc refaire ses références après nettoyage.

Dernier relevé : tête X210 Y273, Z physique calculé 59,975 / Z G-code 60,
cibles buse et plateau zéro, buse refroidie à environ 36 °C. Ces coordonnées
restent des estimations Klipper, pas une mesure physique indépendante.
Le filament est engagé. La purge a invalidé le nettoyage précédent pour
une nouvelle palpation.

## Corrections explicites demandées par Thomas

- Nettoyage manuel à 150 °C, pince puis brosse tenue à la main. Le filament
  peut rester engagé pendant ce nettoyage et le homing XYZ. Une confirmation
  fraîche de propreté puis la température de contact prévue restent requises.
- Aucun nettoyage automatique sur une brosse fixe. Le trajet latéral exécuté
  pendant l'essai est rejeté ; le décrochage courant utilise l'axe Y du bac.
- Déplacements libres aux vitesses normales vérifiées, sans ralentissement
  arbitraire. Ne pas confondre une vitesse de diagnostic avec la production.
- Plateau descendu d'au moins 30 mm pendant tout le passage au bac ; marge
  commandée de 35 mm et sortie à hauteur constante vers Y273 avant remontée.

Les règles actives d'AGENTS, du pilotage caméra et d'ADR-045/037 sont corrigées.
ADR-034 est signalée comme remplacée sur la condition filament. La suppression
globale d'historique a été refusée par le contrôle automatique ; les comptes
rendus historiques sont conservés et ne doivent plus dicter ces règles.

## Vitesses réellement vérifiées

| Opération | Essai diagnostic | Référence normale vérifiée |
|---|---:|---:|
| Déplacement libre vers le bac | 30 mm/s | 400 mm/s dans le binaire constructeur |
| Entrée dans le bac | 30 mm/s | 100 mm/s dans le binaire constructeur |
| Sortie du bac après purge | 30 mm/s | 250 mm/s dans le binaire constructeur |
| Avance du filament pendant purge | 2 mm/s | 6 mm/s, purge constructeur observée |

Le fichier `2_Athletes_PLA_7h39m.gcode` déclare un diamètre de 1,75 mm et des
limites de 23/24 mm³/s pour ses deux filaments. Son premier filament utilise
23, pas 24. À ce diamètre, 2 mm/s vaut environ 4,8 mm³/s ; 6 mm/s vaut environ
14,4 mm³/s. Le candidat respecte aussi la limite du filament effectivement choisi.

Le fichier déclare 560 mm/s en déplacement et 11000 mm/s² d'accélération.
La configuration machine autorise 800 mm/s et 20000 mm/s², mais le relevé
après l'échec donne encore **500 mm/s²**. Cet héritage explique une partie de
la lenteur et doit être rétabli explicitement au bon moment.

## Périmètre de reprise installé

1. Garder le déroulement de chauffe et de homing déjà installé, avec buse
   nettoyée, contact à 100 °C, stabilisation du plateau et chargement du profil.
2. Identifier le filament présent avant les effets CFS. Une bobine sélectionnée
   dans le prochain fichier ne prouve pas l'identité du filament déjà en place.
3. Vérifier la fin du homing frais et XYZ avant le moindre mouvement de bac.
   Garder les contrôles thermiques et la garde mécanique indépendante.
4. Avant prise ou purge, rétablir le courant extrudeur configuré et vérifier
   sa valeur ; rétablir les limites de déplacement nécessaires.
5. Si le bon filament est conservé ou sa prise précédente attribuable, établir
   le mode PRINT et vérifier son retour, purger au bac sans cutter/réinsertion,
   vérifier la consommation du tampon, décrocher en Y et sortir avant remontée.
6. Finaliser la route constructeur uniquement après réussite, afin que le Tn
   suivant du fichier ne recoupe pas le même filament. Réarmer les alarmes
   au point prévu et conserver la fin existante.
7. Vérifier les cas d'échec, annulation, nouveau départ et changement ultérieur,
   puis construire le paquet avec empreintes, sauvegarde, restauration exacte,
   validation froide et essai physique après nouveau nettoyage.

## Intégration locale écrite après autorisation explicite

Thomas a répondu « Oui, écrire et tester l'intégration locale » au refus du
contrôle automatique. Cette autorisation a permis d'écrire et de tester le
coordinateur. Le contrôle XYZ refusé dans un ancien brouillon reste intact.
Le blocage d'écriture locale est levé. L'installation décrite ci-dessous a
ensuite été réalisée sous l'autorisation persistante de la mission.

`kctrl_start.py` observe la fin effective d'`ACCURATE_G28` pour ce départ.
Des axes `xyz` hérités ne suffisent pas. Une annulation, perte de référence,
modification du fichier ou erreur nouvelle ferme le chemin avec arrêt des
chauffes, sans M112, déplacement compensatoire ou retry ajouté. Le courant E
est restauré à sa configuration puis relu avant le chargement ou la purge.

La décision conserve le bon filament et purge sans Tn. La tête vide ou un
changement de bobine connue utilise le Tn existant, une fois. Les deux anciens
chargements de secours après Tn sont retirés du candidat : une perte du capteur
après la purge ne doit pas recharger silencieusement le chemin conservé.
Les contrôles de présence, de pause, l'amorce et le réarmement de l'alarme
restent au point existant ; la fin V3 reste intacte.

La purge conserve le Z déjà plus bas ou vise une marge de 35 mm. Elle pousse
140 mm à au plus 6 mm/s, limités par le filament choisi, vérifie le mode PRINT
et la consommation du tampon, effectue trois allers-retours en Y, puis sort à
Y273. La route et `last_cmd` sont finalisés uniquement après cette réussite.
Le tampon ne prouve pas à lui seul que du filament sort de la buse : la
qualification visuelle reste nécessaire.

La vérification isolée du binaire exact confirme que ses méthodes peuvent
être enveloppées sur l'instance. Elle révèle aussi une attente constructeur
de 3600 s pour la lecture d'état : le candidat envoie la même requête de
lecture, avec 2 s maximum et sans répétition. La lecture du tampon possède
déjà ce délai de 2 s. Aucun moteur n'a été commandé par ces sondes isolées.

**376 tests ciblés verts** : séquence intégrée avec faux Klipper/CFS, deux
CFS, fichier à plusieurs filaments, absence d'attribution, homing manquant ou
raté, annulation, courant incorrect, ACK perdu, tampon inconnu, limites de débit,
garde mécanique, rendu Jinja, grammaire Python 3.8, et régressions des modules
existants de fin, changement d'outil, pause et amorce. Ce résultat ne qualifie
pas une nouvelle prise physique et n'isole pas encore la cause du key837 initial.

Le constructeur local génère six fichiers candidats et leurs empreintes :
cinq modules ajoutés, configuration de départ remplacée. Il reconstitue
d'abord la configuration installée à son empreinte exacte, y compris
`[include k1-control-owned-end-candidate.cfg]`, absent de l'ancienne source
de base. Cette inclusion et le code V3 font l'objet d'un test de conservation.

`manifest.json` décrit les fichiers protégés et la restauration exacte avec
`installer_ready=true`. Son champ statique `installed=false` caractérise le
paquet avant application ; il ne remplace pas le reçu de pose distant.

## Pose et contrôle indépendant à froid

La capture `20260923-retained-start-install-v1` obtient successivement
`PREFLIGHT_OK`, `INSTALLED_COLD_OK` et `VALIDATED_COLD_OK`. Cinq modules sont
ajoutés, la configuration de départ est remplacée et les 22 autres fichiers
protégés restent exacts. La sauvegarde est
`/usr/data/k1-control-v1/backups/retained-start-v1` ; ne pas rejouer la pose.

Un redémarrage du service Klipper a chargé les modules et effacé les références.
Seuls le mesh et les offsets sont remis, sans mouvement et sans restaurer
XYZ. Les deux capteurs détectent toujours le filament ; chauffes zéro et fin
V3 au repos. Une validation séparée relit les empreintes, la sauvegarde, le
mesh, les offsets et ces états.

Les 44 nouveaux tests de pose couvrent les erreurs de copie et de démarrage,
la restauration exacte, les fichiers étrangers, la sauvegarde corrompue et
un arrêt de service incertain. Dans ce dernier cas le déployeur ne prétend
pas connaître l'état du service et ne devine pas une relance.

Thomas confirme ensuite la buse propre et sa présence. T1B est attribué avec
`KCTRL_RETAINED_ADOPT`, sans trame CFS ni effet physique. Le fichier court
`K1-retained-T1B-2layer-20260923.gcode` est lancé une seule fois via le choix
normal des bobines. Il emploie la recette du premier filament du fichier Orca
en échec : 195 °C première couche, 200 °C ensuite, plateau 55 °C, diamètre
1,75 mm et débit maximal 23 mm³/s. Le départ normal est suivi de T0 puis d'un
`PAUSE_BASE` de contrôle visuel, avant deux couches de 30 × 30 mm et la fin V3.
Ce checkpoint appartient uniquement au fichier d'essai, pas aux impressions
normales.

## Essai réel terminé et confirmé

Le homing précis est observé terminé (`reference=1`, valide) à la température
de contact. La branche `recover` garde T1B. La purge se déroule à 6 mm/s de
filament, avec courant nominal relu et CFS en mode PRINT. Au bac, la position Z
après compensation vaut environ 34,976 mm, au-dessus du minimum physique de
30 mm. La tête sort avant la remontée vers l'amorce ; aucun refus de la garde.

Thomas confirme « oui impeccable » pour le débit et le décrochage, puis la ligne
d'amorce. L'attente visuelle dépassant trois minutes, les chauffes sont coupées
sans mouvement ni retrait. Après son retour, elles sont remises sans nouvelle
palpation ; le carré de deux couches est imprimé et la fin V3 atteint `complete`,
sans défaut ni opération restante. Thomas confirme le carré et le retrait :
« oui impeccable, niquel ». La tête est détectée vide et la route T1B libérée.
Aucun M112 n'a été envoyé.

Cet essai qualifie la reprise avec le filament conservé, pas une nouvelle
insertion depuis une tête vide. Le courant et le mode PRINT ont été rétablis
ensemble : leur succès ne démontre toujours pas lequel était la cause unique
du key837 initial.

## Température : écart observé et delta installé

Le fichier de test reprend 195 °C pour sa première couche et 200 °C pour les
suivantes. La purge conserve le plancher de 200 °C déjà employé par le chemin
constructeur, puis le départ remet 195 °C pour l'amorce. Le T0 du fichier appelle
ensuite l'ancien calcul de couche fondé sur Z : le relevage à 2,36 mm fait choisir
200 °C trop tôt. La reprise constructeur répète cette sélection et le carré a
donc été imprimé à 200 °C malgré la remise préalable à 195 °C. Le maintien à
195 °C n'est pas revendiqué comme qualifié par cet essai.

Le delta `preserve-active-tool-target-v1` intercepte uniquement une sélection
répétant un outil déjà confirmé : même travail et empreinte de fichier, époque,
route actuelle, cache constructeur, dernier outil réussi, deux capteurs,
références et mode PRINT cohérents. Dans ce cas, il vérifie le courant E et
conserve la cible courante, sans appeler le changement constructeur ni aligner
la fiche matériau. Un autre outil ou une preuve manquante conserve le chemin
habituel. Les M104/M109 explicites du fichier restent libres de changer la cible.

Les 27 tests de comportement ajoutés couvrent 195/200/215 °C, les relevages,
les reprises après le délai initial, les deux CFS et les preuves invalidées.
Les 25 tests de pose couvrent le delta d'un fichier et sa restauration. Pose
puis validation indépendante : `TEMPERATURE_PATCH_INSTALLED_COLD_OK` et
`TEMPERATURE_PATCH_VALIDATED_COLD_OK`. Sauvegarde séparée :
`/usr/data/k1-control-v1/backups/retained-start-temperature-v1`. Aucun effet
physique ; la preuve visuelle de ce dernier delta reste au prochain print.

L'état final est prêt/standby, cibles zéro, références effacées, tête vide,
routes vides, deux CFS connectés, fin idle, même mesh 11 × 11 et courant E
nominal. Le carré et la buse nécessitent la préparation habituelle avant un
nouveau homing. Les presets de bobines demandés sont consignés dans ROADMAP ;
aucun nouvel écran ni réglage de température par bobine n'a été installé.

## Preuves

Captures privées : `inventory/raw/20260923-retained-start-v1/`, notamment
`physical-actions.jsonl`, `speed-read-state.json`, `speed-file-read.stdout`,
`isolated-release-and-speed-probe-r2.stdout` et les images de fin de purge.
Les traces du binaire utilisent de faux objets dans un processus isolé : elles
ne sont ni des commandes machine ni une validation mécanique.

Pose froide : `inventory/raw/20260923-retained-start-install-v1/`.
Essai après nettoyage : `inventory/raw/20260923-retained-start-print-v1/`.
Delta température : `inventory/raw/20260923-retained-start-temperature-v1/`.

Le G-code de test est conservé dans la capture privée avec son empreinte
`253b0ca06058c834976845a1ff12930421356fec481fe6b553456a9ea8477269`.
Il a été retiré de l'imprimante après vérification de cette empreinte.

## Fichiers et prochaine action

Code et déploiement : `retained-start-v1/kctrl_start.py`, `remote_install.py`,
`remote_selection_patch.py`, `build_candidate.py` et `manifest.json`.
Tests ajoutés : `test_retained_start_install.py`,
`test_retained_start_duplicate_selection.py`, `test_retained_start_selection_patch.py` ;
test d'intégration adapté. Le README du paquet, AGENTS, STATE, HANDOFF, ADR-071
et ROADMAP sont alignés sur le résultat et les limites ci-dessus.

La prochaine action est humaine : retirer le carré, nettoyer la buse à 150 °C
et lancer une impression normale avec son choix de bobines. Aucun modèle Codex
n'est nécessaire pour ce geste. Pour la future mission de presets :
`gpt-6-sol`, raisonnement `high`, convient à l'interface et aux règles de priorité
thermique ; `gpt-6-luna` en `high` est une option économique pour une maquette UI
seule, avec revue séparée des effets sur l'imprimante.
