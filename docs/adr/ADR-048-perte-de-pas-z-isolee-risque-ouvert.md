# ADR-048 — Perte de pas Z isolée : risque matériel ouvert, non bloquant

Date : 2026-09-01

Statut : **accepté** ; le défaut est constaté, non reproduit, non corrigé

## Contexte

Le 1er septembre 2026 à 20:52:59, une acquisition de maillage a été refusée par
le firmware :

```
PR_ERR_CODE_HAVE_LOST_STEP: Z-axis motor step loss was found.
RUN_G29_Z check last point res_z:(2.627106359649126) out of lost_step_dis:0.5
```

Le journal de palpage montre la signature exacte du défaut :

```
probe at  18.0,  85.75  ->  z = -0.180
probe at  18.0, 148.50  ->  z = +2.595      saut de 2,78 mm
probe at  82.75,148.50  ->  z = +2.599
...  les vingt points suivants restent entre +2.58 et +2.70
```

Le saut est **discret et unique**, et les contacts postérieurs restent cohérents
entre eux à 0,12 mm près, c'est-à-dire la forme réelle du plateau simplement
translatée. Un plateau qui bouge produit une dérive progressive ou un défaut
localisé ; une référence entière qui saute une fois puis tient, c'est la
position de l'axe Z.

Le sens est établi : les valeurs sont devenues plus positives, donc le contact
s'est produit à un Z commandé plus haut, donc l'axe n'a pas parcouru les
2,78 mm demandés.

Deux causes ont été écartées sur la machine :

- **jeu du plateau** : aucun jeu à la main sur les quatre coins ;
- **obstruction dans la course** : inspection visuelle négative, aucune vis
  perdue.

L'accès à l'entraînement Z demande un outillage indisponible.

## Décision

Le symptôme est mesuré à défaut de pouvoir inspecter la cause.
`KCTRL_Z_REPEAT` palpe un point fixe au centre, fait parcourir à la tête le
même tour de plateau que le maillage, puis repalpe ce point, plusieurs fois.

Résultat de la première exécution, sept contacts au même endroit :

```
PROBE_ACCURACY   -0.019  -0.058  -0.061
après tour 1     -0.039
après tour 2     -0.020
après tour 3     +0.014
après tour 4     -0.036
```

Étendue `0,075 mm`, **aucune dérive, aucun décrochage sur quatre tours**. Le
défaut n'est donc pas systématique.

Le risque est accepté et laissé ouvert. Il n'est pas bloquant : PRTouch
contrôle ce point à la fin de chaque acquisition et refuse un maillage
corrompu, ce qu'il vient de démontrer.

## Conséquences

- Une acquisition refusée pour perte de pas est **rejetée, jamais exploitée** —
  au même titre qu'une séquence palpée sur une buse non confirmée (ADR-045).
- Le défaut reste à investiguer côté matériel, accouplement moteur et tension
  d'entraînement en tête, le jour où l'outillage est disponible.
- Aucune protection équivalente n'existe **pendant une impression** : le
  contrôle est propre à la séquence de maillage. Si le défaut se reproduit et
  devient fréquent, cette absence devient le vrai sujet.
- L'étendue de palpage relevée ici, `0,075 mm` sur sept contacts, est
  supérieure aux `0,034 mm` de l'ADR-013. Le nettoyage de buse a été refait
  avant l'acquisition suivante ; si le bruit reste élevé sur une buse propre,
  il faudra le traiter pour lui-même.

## Voir aussi

- ADR-013 — répétabilité de palpage mesurée sur cette machine
- ADR-045 — aucun palpage sans buse nettoyée à la main
- ADR-047 — plateau voilé et plancher mécanique
