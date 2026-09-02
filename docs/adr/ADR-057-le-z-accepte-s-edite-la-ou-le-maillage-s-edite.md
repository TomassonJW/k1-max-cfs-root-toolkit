# ADR-057 — Le Z accepté s'édite là où le maillage s'édite

Date : 2026-09-02

Statut : **accepté**

## Contexte

Le Z accepté est propre au profil de maillage : `START_PRINT` lit
`z_<profil>` et refuse de démarrer sans lui. Il n'était écrivable que par
`KCTRL_Z_SAVE` en console.

Le réglage utile se trouve pourtant à l'œil, pendant une première couche, en
descendant le Z depuis Fluidd. Cette valeur-là mourait avec l'impression : deux
fois de suite, le Z a dû être remis à la main au démarrage suivant.

## Décision

**L'éditeur de maillage édite aussi le Z du profil affiché. Il ne l'écrit pas
lui-même.**

1. La page montre trois choses : la valeur enregistrée pour le profil, la
   valeur en vigueur sur la machine à l'instant, et un champ pour taper.
   « Reprendre » recopie la seconde dans le champ sans rien écrire.
2. L'écriture passe par `KCTRL_Z_SAVE`, qui reste l'unique écrivain. Le serveur
   de l'éditeur refuse d'avance ce qui est manifestement faux, puis laisse la
   macro revérifier et répondre. Ce qui s'affiche après enregistrement est la
   phrase de la macro.
3. Le nom du profil part dans une commande G-code : seuls les noms que Klipper
   détient déjà comme profils sont acceptés.
4. Enregistrer ne déplace rien. La valeur est lue au démarrage d'impression
   suivant, et la page le dit à l'écran.

## Conséquences

- Un seul écrivain, donc la valeur affichée par l'éditeur, celle listée par
  `KCTRL_Z_LIST` et celle lue par `START_PRINT` ne peuvent pas diverger.
- La plage ±2 mm est refusée aux deux bouts : sur la page pour le dire tout de
  suite, dans la macro parce que c'est elle qui fait foi.
- Le désenveloppage des refus de macro a dû être réparé pour que cette phrase
  arrive lisible ; l'enregistrement du maillage en bénéficie.
- Un Z peut être enregistré pendant une impression. C'est voulu : le bon moment
  pour noter la valeur est celui où on la trouve, et elle ne s'applique qu'au
  démarrage suivant.

## Voir aussi

- doc 56 — ce qui a été posé et les preuves faites sur la machine
- ADR-046 — le point de palpage reste le zéro du profil
