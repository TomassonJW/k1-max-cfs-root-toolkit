# Résilience, tranche 1 : plus d'impasse après un arrêt

Statut : **construit et validé hors imprimante le 15 novembre 2026, non
posé**. Le relevé de l'imprimante reste à faire (`surveyed: false`) : tant
qu'il manque, l'installeur refuse tout sauf ce relevé.
ADR-080, document 109. Remplace `kctrl_start.py` de `start-load-recovery-v1`,
la porte de lancement et deux fichiers de la page Bobines ; tout le reste est
gardé et épinglé.

- `kctrl_start.py` : le départ, même objet `kctrl_start`, révision
  `resilience-v1`.
- `kctrl_print_gate.py` : la porte de lancement, qui publie maintenant sa
  révision.
- `www/bobines/logic.js`, `www/bobines/bobines.js` : la page Bobines.
- `remote_install.py`, `deploy.py`, `build_manifest.py`, `manifest.json` : la
  pose, voir « Pose » plus bas.

## Pourquoi

Trois états ne se quittaient que par une console ou un redémarrage
(document 109, section 5) :

- après un redémarrage, une coupure ou un arrêt d'urgence, filament en tête,
  tout départ refusait (`retained_identity_or_continuity_unproven`) jusqu'à
  `KCTRL_RETAINED_ADOPT` ;
- après une fin ou une annulation ratée, la porte refusait tout fichier
  jusqu'au redémarrage de Klipper ;
- après un départ arrêté pendant sa purge, la tête restait au bac.

## Ce qui change

1. **La fiche du filament en tête.** Le slot prouvé en tête est écrit dans
   `/usr/data/k1-control-v1/state/kctrl_head.json`, seulement quand il change.
   Au départ suivant, cette fiche vaut attribution ; la purge au bac doit
   encore prouver que le tampon du CFS se vide. Elle est effacée dès que la
   tête est vue vide deux fois de suite, ou qu'une coupe, un retrait ou un
   chargement manuel commence.
2. **Une fin ratée ne bloque plus.** La porte ne refuse que trois cas, chacun
   dit en clair : fin encore en cours, fin illisible, arrêt des chauffes non
   confirmé. `START_PRINT` remet la fin à zéro et le départ reprouve filament,
   route et géométrie.
3. **La page l'explique sans bloquer.** Une fin ratée laisse un avis sur la
   page Bobines, dit une fois dans la fenêtre Mainsail, jusqu'à « Compris » ou
   au départ suivant.
4. **Sortie du bac après un départ arrêté.** Tête au bac, axes référencés,
   plateau à 30 mm au moins : sortie vers Y273 à hauteur constante, sous la
   garde du bac. Sinon rien ne bouge.

## Limites

- Un filament changé à la main imprimante éteinte n'est pas vu : la purge
  refuse si le tampon du CFS ne se vide pas.
- La bobine demandée n'est pas celle de la fiche : le départ refuse encore,
  en le disant (`retained_head_holds_<fiche>_not_<demande>`). Le changement
  automatique vient en tranche 5.
- Une coupe, un retrait ou un chargement manuel refusé avant tout effet efface
  quand même la fiche : après un redémarrage, le départ redemande
  l'attribution (tranche 5).
- Moteurs coupés tête au bac : rien ne bouge, l'impasse reste (tranche 3).
- Une fin « coupé mais pas rembobiné » passe la porte, puis le départ s'arrête
  proprement (`buffer_consumption_unconfirmed`) et le suivant répond
  `partial_filament_requires_recovery` (tranche 5).
- Une coupure de courant dans les 5 s qui suivent un chargement lancé à
  l'écran peut laisser une fiche périmée ; la purge la dément.
- La sortie du bac se fait sans le décrochage habituel.
- L'écriture de la fiche bloque Klipper quelques millisecondes, seulement
  quand le slot change.
- Le navigateur peut garder l'ancienne page : la recharger une fois.

## Pose

    python deploy.py survey|preflight|install|validate|rollback

`survey`, `preflight` et `validate` ne font que lire. `install` et `rollback`
redémarrent Klipper, au repos seulement, sans chauffe, sans mouvement, sans
filament, sans toucher à `printer.cfg`.

Ordre :

1. `survey` : compare les quatre cibles et les 32 fichiers épinglés à ce que
   le manifeste attend, et dit quelle case il porterait dans la fiche. Il
   répond toujours, même imprimante occupée.
2. Une dérive relue et acceptée se note dans `REPINNED` de
   `build_manifest.py`. Tout conforme : la date va dans `SURVEYED`, le
   manifeste est reconstruit et dit `surveyed: true`.
3. `preflight`, `install`, `validate`.

Quatre cibles, dans cet ordre :

| Fichier | Avant | Après |
| --- | --- | --- |
| `/usr/share/klipper/klippy/extras/kctrl_start.py` | `dbdb1554...` | `e5917f93...` |
| `/usr/share/klipper/klippy/extras/kctrl_print_gate.py` | `69578e57...` | `9240b95c...` |
| `/usr/data/k1-control-v1/current/www/bobines/logic.js` | `3f7513c8...` | `b3000196...` |
| `/usr/data/k1-control-v1/current/www/bobines/bobines.js` | `52760957...` | `da677a5a...` |

32 fichiers épinglés : ceux de `start-load-recovery-v1` moins la porte,
devenue cible, plus les fichiers de la page que ce paquet ne remplace pas et
l'index Mainsail qui l'appelle. Aucun n'est écrit.

Ce que fait `install` :

- refuse tant que le repos n'est pas prouvé (impression, pause, chauffe,
  commande CFS, garde non au repos, auto-remplacement en attente de
  restitution), et le revérifie juste avant l'arrêt de Klipper ; un écart à
  ce moment rend `NOT_INSTALLED_NOTHING_CHANGED` ;
- sauvegarde les quatre fichiers et leurs droits dans
  `/usr/data/k1-control-v1/backups/resilience-v1` ;
- lit la route du CFS une dernière fois avant l'arrêt et écrit la fiche du
  filament en tête : le redémarrage de la pose ne fait donc pas perdre la
  preuve. Une route ambiguë ou une tête vide : pas de fiche, et une ancienne
  fiche est retirée ;
- écrit chaque fichier à côté puis le remplace d'un coup, relit son
  empreinte, écrit les pages en `0644`, efface le bytecode des deux modules ;
- redémarre, attend le repos, puis exige : départ et porte à la révision
  `resilience-v1`, départ neuf, fiche relue par le départ, délai de reprise
  180 s, voisins inchangés, pages lisibles. Réponse : `INSTALLED_IDLE_OK`.

Si une seule de ces preuves manque, l'installeur défait sa propre pose :
arrêt, quatre fichiers remis quoi qu'ils contiennent, fiche retirée,
redémarrage, repos prouvé, `INSTALL_FAILED_ROLLED_BACK`. La sauvegarde est
rangée en `resilience-v1.install-failed-<n>` : une nouvelle pose reste
possible sans rien nettoyer.

`rollback` remet les quatre fichiers et retire la fiche, puis range la
sauvegarde en `resilience-v1.rolled-back-<n>`. Il vérifie tout avant d'arrêter
Klipper et refuse un fichier qui n'est ni l'ancien ni le nouveau
(`rollback_foreign_file`). Après lui, l'ancien comportement revient :
`KCTRL_RETAINED_ADOPT` s'il y a du filament en tête.

Un fichier épinglé qui change pendant que l'installeur travaille n'est jamais
écrit : il est nommé dans la réponse, champ `neighbour`.

Le préflight cherche dans les sources constructeur épinglées les noms appelés
par le départ ; un nom absent ferme la pose. Ceux du CFS, compilé, sont
seulement rapportés.

Les paquets antérieurs épinglent les anciens `kctrl_start.py` et
`kctrl_print_gate.py` : retour arrière de celui-ci d'abord avant d'en reposer
un.

## Validation

Hors imprimante, sans réseau ni SSH :

- départ : 152 tests (`tests/test_resilience_start.py`), dont 37 tests des
  départs précédents rejoués sur ce module ;
- porte : 171 tests (`tests/test_resilience_gate.py`), dont 41 tests de
  l'ancienne porte, le vrai module de fin, et la page comparée cas par cas ;
- page : 70 tests sous node (`logic.test.mjs`) ;
- pose : 231 tests (`tests/test_resilience_install.py`) sur une fausse
  machine qui répond comme Klipper : chaque refus, chaque échec d'écriture,
  chaque retour arrière, la fiche écrite par la pose relue par le vrai départ ;
- 49 pannes provoquées exprès dans l'installeur : 48 vues par le banc, une
  équivalente (un contrôle doublé par un autre). Cette recherche a trouvé un
  vrai défaut, corrigé : après une écriture corrompue, l'installeur refusait
  de défaire sa propre pose.

Pas encore posé, pas encore vu sur une impression réelle.
