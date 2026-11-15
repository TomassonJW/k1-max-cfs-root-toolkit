# 109 - Résilience : plus d'impasse, plus de commande à taper (ADR-080)

Date : 15 novembre 2026. Suite du document 108. Conventions du document 70 :
**[FAIT]** lu dans un journal, un fichier ou un test ; **[HYPOTHÈSE]**
cohérent, non démontré ; **[INCONNU]** non observé.

## 1. Demande

Thomas, le 15 novembre : trouver toutes les pannes du genre, les résoudre de
façon pérenne et résiliente, pas par une commande relancée à chaque fois, et
préparer une installation qui ne demande plus d'IA pour dépanner.

## 2. Méthode

- [FAIT] Relecture des documents 88 à 108, des ADR-058 à 079, du pilotage et
  des notes : onze familles de pannes, section 4.
- [FAIT] Lecture du code posé (départ, fin, porte de lancement, gardes du bac,
  de la buse froide et du capteur) et des sources constructeur lues en local :
  les impasses de la section 5 sont vérifiées ligne à ligne, sauf mention.
- Aucun accès à l'imprimante : une impression tournait.

## 3. Règle

Sept principes, fixés par ADR-080. Tout paquet futur s'y mesure.

1. **Aucun état sans sortie.** Après n'importe quel arrêt, l'action normale
   suivante marche : relancer, reprendre, ou un bouton. Jamais une commande.
2. **Rien d'essentiel en mémoire seule.** Ce qu'un redémarrage efface et qui
   bloque ensuite est écrit sur disque.
3. **Reprendre dans la même opération d'abord.** Une fois, borné, sur preuve.
4. **Retour au repos propre après un arrêt.** Chauffes coupées, tête hors du
   bac quand c'est prouvé sûr, rien qui piège l'action suivante.
5. **Tout vit dans Klipper et démarre seul.** Plus de veille dans `/tmp` ni
   sur le PC.
6. **Une installation unique**, rejouable, qui se vérifie elle-même, à
   reposer après une mise à jour constructeur.
7. **Chaque refus se dit en clair**, avec sa cause et son remède, sur la page.

## 4. Les onze familles de pannes

| Famille | Vu le | Aujourd'hui | Remède définitif |
| --- | --- | --- | --- |
| A. Chargement stock raté au départ, filament pourtant en tête (`key837`) | 21/09, 23/09, 12/11, 15/11 ; 4 chargements sur 7 | repris dans le même départ (ADR-079), posé, pas encore vu | fait ; à observer |
| B. Preuve perdue après redémarrage ou arrêt d'urgence, départ refusé | 2/10, 15/11 | `KCTRL_RETAINED_ADOPT` à la console | tranche 1 : fiche du filament en tête écrite sur disque |
| C. Fin d'impression : la routine stock pousse en boucle | 15/09, 31/10, 1/11 | gardes posées (buse froide, fin V5, capteur V2) ; l'arrêt d'urgence demande d'éteindre | tranche 3 : arrêt propre avant l'arrêt d'urgence, boucle bornée |
| D. Changement de bobine en cours d'impression qui échoue | 23/09 | reprise protégée (ADR-072) ; l'échec lui-même arrête la pièce | tranche 2 : même reprise qu'au départ, sinon vraie pause |
| E. Fausse fin de bobine, pause, reprise dans le vide | 12/11 | un message indique la commande à taper | tranche 2 : « Reprendre » remet le CFS en service et purge |
| F. Fin ou annulation ratée qui bloque le lancement suivant | 2/10, 5/11 | redémarrer Klipper, puis famille B | tranche 1 : le lancement suivant repart, le départ reprouve tout |
| G. Arrêt d'urgence : Klipper quitte, il faut éteindre et rallumer | 5 fois | Thomas rallume ; puis famille B | tranches 1 et 3 : plus rien de bloqué au retour, moins d'arrêts |
| H. Pauses `key831`, le second CFS ne répond pas | 15/09 | garde du bus posée | tranche 6 : la garde est revérifiée au démarrage |
| I. Reprise de nuit et veille de fin hors de Klipper | 2/10, 1/11 | script en `/tmp` effacé, veille sur le PC | tranche 4 : intégrées à Klipper |
| J. Plateforme : mise à jour constructeur, usure, macros cachées | 31/10, 1/11 | à la main | tranche 6 : autocontrôle au démarrage, repose en un geste |
| K. Refus sans explication ni remède | partout | lire le journal | tranche 5 : page Dépannage |

## 5. Les impasses trouvées dans le code

Une impasse : un état d'où l'on ne sort que par une console ou un redémarrage.

1. [FAIT] **Fin ratée.** La porte de lancement refuse tout fichier tant que la
   fin précédente dit `failed` (`kctrl_print_gate.assert_end_released`). Aucune
   commande ne la remet à zéro ; `START_PRINT` le ferait (`kctrl_end.start`)
   mais la porte passe avant. La page Bobines dit seulement « Fin incomplète ».
2. [FAIT] **Filament en tête après un redémarrage.** L'attribution du filament
   (`attempt`, `adopted`, `extrude_tnn`) et la route du CFS ne vivent qu'en
   mémoire. Après un redémarrage, tout départ répond
   `retained_identity_or_continuity_unproven`.
3. [FAIT] **Tête au bac, moteurs coupés.** Verrou de la garde posé et axes non
   référencés : tout mouvement est refusé, prise d'origine comprise, jusqu'au
   redémarrage. Un départ arrêté pendant sa purge laisse la tête au bac.
4. [FAIT] **Tête vide, route engagée** : `partial_filament_requires_recovery`
   à chaque lancement, sans sortie décrite.
5. [FAIT] **Arrêt d'urgence de la garde capteur** : une poussée de plus de
   1 mm dans les 15 minutes qui suivent une fin, même lancée à l'écran par
   Thomas, coupe Klipper.
6. [FAIT] **Pause, CFS au repos** : « Reprendre » ne dépose rien ; la sortie
   est `BOX_SET_BOX_MODE` à la console.
7. [FAIT] **Refus d'un changement en cours d'impression.** Une erreur qui n'est
   pas une erreur G-code est seulement affichée (`key60`) et le fichier
   continue (`gcode.py`, lignes 208 à 223). [HYPOTHÈSE] L'impression peut donc
   continuer avec la mauvaise bobine.
8. [FAIT] **Erreur CFS gardée** (`last_err`) : le fichier suivant met en pause
   avant sa première ligne (`virtual_sdcard.py`, lignes 977 à 995). Masqué
   aujourd'hui par le drapeau de pause resté posé. À ne jamais démasquer à
   moitié : les deux s'effacent ensemble ou pas du tout.
9. [FAIT] **Le chien de garde du départ** ne peut pas interrompre un `T` stock
   bloquant ; il marque seulement l'échec.
10. [FAIT] **Hors de Klipper** : reprise de nuit en `/tmp`, veille de fin sur
    le PC.
11. [FAIT] **Remis en cause par l'écran ou le constructeur** : auto-remplacement
    remis à 1, CFS laissé au repos après une purge stock, mesh « default »
    rechargé à chaque prise d'origine.

## 6. Tranche 1 : `resilience-v1`

Paquet `packages/k1-control-v1/resilience-v1`. Trois fichiers changent sur
l'imprimante, rien d'autre.

- **La fiche du filament en tête** (`kctrl_start.py`, impasse 2). Le slot
  prouvé en tête est écrit dans `state/kctrl_head.json`, seulement quand il
  change. Écrit sur une route du CFS lue, un départ réussi, une prise ratée
  attribuable ou une attribution de l'opérateur. Effacé dès que la tête est
  vue vide deux fois de suite, ou qu'une coupe, un retrait ou un chargement
  manuel commence. Au départ, cette fiche vaut attribution : la purge au bac
  doit encore prouver que le tampon du CFS se vide. Plus de
  `KCTRL_RETAINED_ADOPT` après un redémarrage.
- **Une fin ratée ne bloque plus** (`kctrl_print_gate.py`, `logic.js`,
  impasse 1). La porte ne refuse que si la fin est en cours, illisible, ou si
  l'arrêt des chauffes n'est pas confirmé. La page explique, sans bloquer.
- **Sortie du bac après un départ arrêté** (`kctrl_start.py`, impasse 3).
  Tête au bac, axes référencés, plateau à 30 mm au moins : sortie vers Y273 à
  hauteur constante, sous la garde du bac. Sinon rien ne bouge.
- **Une pose à plusieurs fichiers**, base de l'installation unique.

Limites de la fiche : un filament changé à la main imprimante éteinte n'est
pas vu ; la purge refuse alors si le tampon du CFS ne se vide pas. Si la
bobine demandée n'est pas celle de la fiche, le départ refuse encore, en le
disant ; le changement automatique vient en tranche 5.

## 7. Tranches suivantes, dans l'ordre

2. **Reprise en un geste.** « Reprendre » remet le CFS en mode impression sur
   la bobine engagée, purge au bac avec preuve, revient et reprend. Un
   chargement raté en cours d'impression est repris comme au départ ; un
   refus devient une vraie pause.
3. **Moins d'arrêts d'urgence.** La garde capteur arrête la poussée par un
   arrêt propre avant de couper Klipper ; un chargement lancé à l'écran ne la
   déclenche plus ; la boucle de fin stock est bornée.
4. **Veilles dans Klipper.** Reprise de nuit et surveillance de fin intégrées.
5. **Page Dépannage.** Chaque refus : une phrase, un bouton. « Quelle bobine
   est en tête ? » quand la fiche manque. Filament partiel rembobiné au
   départ. Boîte noire des derniers événements.
6. **Installation unique.** Manifeste de tout ce qui est posé, autocontrôle au
   démarrage, repose en un geste après une mise à jour constructeur.

## 8. Ce qui ne peut pas être rendu impossible

Un vrai bouchon, une bobine vide sans jumelle, une coupure de courant, un
arrêt du microcontrôleur. Ces cas doivent finir propres, expliqués, à un clic
de la suite : c'est ce que visent les tranches 1 à 5.

## 9. Preuves et pose

Voir le README du paquet. Pose au repos seulement, sur l'accord de Thomas.
