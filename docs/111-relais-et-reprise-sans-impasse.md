# 111 - Relais de bobine et reprise sans impasse (tranche 2)

Date : 15 novembre 2026. Paquet `resilience-v2`, ADR-081. Suite du document 110
(relais raté du 15 novembre) et de la tranche 1 (document 109). Construit hors
imprimante, **non posé**. Conventions : **[FAIT]** vérifié par un essai sur
banc ou lu dans le code ; **[HYPOTHÈSE]** cohérent, non démontré ;
**[INCONNU]** non observé.

## 1. Ce que fait la tranche 2

Quand le changement automatique de bobine rate, « Reprendre » marche, ou
n'est même pas nécessaire. Trois accroches dans le départ `kctrl_start`, sans
rien de nouveau à installer à côté :

1. **Avant le relais** (`BOX_CHECK_MATERIAL_REFILL`) : courant extrudeur remis à
   sa valeur de marche, relu. La pause stock le laisse à 0,28 A.
2. **Chargement raté avec filament en tête** (enveloppe `T1A..T4D`) : le slot est
   attribué par les lignes `key836`/`key837`, la cible du relais, et l'outil
   demandé ; il faut la tête vide avant, chargée après. Route du CFS alignée,
   CFS remis en mode impression, erreur effacée, 5 s d'attente, puis la reprise
   se fait seule : sortie du bac à Y273 hauteur constante, 7 poussées de 20 mm
   au bac avec tampon lu, route écrite, capteur de tête réarmé, limites de
   mouvement, avance de pression et ventilateurs du fichier remis, `RESUME`
   stock, amorce de 0,8 mm.
3. **« Reprendre » à la main** : même chemin. Garde du bac verrouillée : sortie
   vers Y273 d'abord, jamais de remontée du plateau avant. CFS laissé au repos
   après une routine stock : purge au bac avant la reprise.

Rien n'est levé ni relancé dans l'enveloppe `T1A..T4D` (ADR-072) : toute faute
y est avalée, l'état est noté, la phrase est dite après.

## 2. Reprise non prouvée

Une phrase claire à la console (ASCII, sans apostrophe, jamais en `!!`, jamais
le mot « failed »), vraie pause, tête hors du bac, plateau jamais remonté,
buse et courant remis comme à la pause, et « Reprendre » qui retente. Les
raisons ont chacune leur libellé (`RESUME_HINTS`).

## 3. Preuves sur banc

[FAIT] `tests/test_resilience_resume.py` : 388 essais verts. Le scénario du
15 novembre est rejoué : un seul chargement stock, 7 poussées, retour au point
d'arrêt, route, mode, ventilateurs, limites et courant remis, aucun refus de la
garde. Variantes : route qui colle sur la même unité, deux lignes d'erreur,
chargement qui lève, second 0,28 A, chauffe plateau coupée, annulation et
déconnexion pendant la purge, délai dépassé, route changée, capteur illisible,
courant non relu, reprise stock sans effet, relais réussi du 31 octobre
(quatre variantes), pause simple, CFS au repos, départ en cours. Les 76 essais
du départ de la tranche 1 sont rejoués deux fois sur ce module : sans, puis avec
les accroches de reprise. [FAIT] Banc de pose adapté (231 essais).

## 4. Limites connues

- Coupure de courant entre le raté et la reprise : rien n'est gardé en mémoire
  de la reprise ; « Reprendre » après redémarrage de la machine reste à lire.
- Échec d'un changement d'outil en cours de fichier multicolore : laissé au
  stock (tête non attribuée).
- Un chargement demandé pendant une pause, tête chargée et sans ligne d'erreur,
  n'est pas jugé raté.
- Un rechargement `resume_tnn` raté, tête chargée, est laissé au stock.
- `change.last` n'est pas réaligné après un relais ; plusieurs `T` dans un
  fichier à relire.
- Une purge complète de 7 × 20 mm à chaque reprise ; si une pause normale met
  le CFS en mode `"0"`, chaque reprise purge (à lire).
- `box.inside_error` qui reste vrai : attente de 60 s puis phrase.
- Plus de 32 lignes `!!` pendant le chargement : non attribué, stock.
- Annulation pendant la purge : phrase « impression annulée » légèrement
  imprécise (« gardée en pause »), sans effet.
- Plateau à moins de 30 mm pendant une pause verrouillée : reprise refusée
  (`bin_exit_bed_too_high`).
- Hauteur de remontée stock : confiance en `z_safe_pause`.

## 5. Inconnues du code compilé

[INCONNU] `BOX_ERROR_CLEAR` efface-t-il `last_err` (refus propre sinon) ;
`BOX_CHECK_MATERIAL_REFILL` lance-t-il `T` de façon synchrone ; effet exact de
`BOX_RESUME_EXTRUDE` et de `DO_AFTER_PAUSE` ; mode du CFS pendant une pause
normale ; `action.extrude_tnn` après un relais raté ; durée de
`inside_error` ; affichage de l'écran après une reprise automatique ;
`virtual_sdcard` attend-il le verrou avant de rejouer `resume_tnn`. Le relevé
au repos et la première lecture réelle les fermeront.

## 6. Pose

Au repos seulement, avec l'accord de Thomas, repos revérifié juste avant l'arrêt
de Klipper : relevé (lecture seule), manifeste, `preflight`, `install`,
`validate`, rechargement de la page Bobines. Retour arrière : la sauvegarde
`/usr/data/k1-control-v1/backups/resilience-v2`.
