# ADR-079 - Un chargement stock raté, filament en tête, est repris dans le même départ

Date : 12 novembre 2026. Statut : accepté ; construit et testé hors
imprimante, pas posé. Complète le départ gardé (`retained-start-v1`).

## Contexte

Le 12 novembre à 17:11 (document 108), le chargement stock de T1B a amené le
filament en tête puis conclu « buffer is always full », `key837` sur [1, "B"],
et mis en pause. La pause a voulu remonter le plateau tête au-dessus du bac ;
la garde du bac a refusé et coupé les chauffes ; le départ s'est arrêté. Relancé
à 17:43, le même départ a vu T1B en tête, l'a purgé au bac (`recover`) et
l'impression est partie. Thomas veut que ça marche à chaque fois, sans relance.

## Décision

Paquet `packages/k1-control-v1/start-load-recovery-v1`, même module
`kctrl_start`, révision `start-load-recovery-v1`.

1. Pendant le `T` stock d'un départ, les lignes `!!` sont lues. Seuls `key837`
   sur le slot demandé et le refus de la garde du bac sont tolérés.
2. Avec ces codes ou une pause stock, une reprise exige avant tout effet : phase
   `material`, CFS hors traitement d'erreur, capteurs tête et sortie à vrai,
   slot demandé en tête et seul engagé, mémoire de levée lisible, consigne
   plateau connue, pause stock réversible. Sinon arrêt chauffes coupées.
3. Effets : drapeaux de pause levés sans `RESUME`, position G-code remise sans
   mouvement, consigne plateau remise, mémoire de levée du CFS effacée,
   `key602` à l'écran, puis la purge K1 Control au bac et `M190`.
4. Une seule reprise par départ, 180 s au plus. La purge exige l'erreur stock
   effacée et le tampon consommé.
5. La garde du bac, la purge, la règle des 30 mm et la sortie vers Y273 ne
   changent pas.

## Alternatives écartées

- Laisser la pause stock remonter le plateau : collision avec le bac.
- `RESUME` stock : relance la routine stock, dont les mouvements et la reprise
  de position ne passent pas par la purge gardée.
- Réessayer le `T` stock : même conclusion probable, et une seconde poussée
  sur un filament déjà en tête.
- Ignorer `key837` sans preuve en tête : un vrai bouchon serait purgé à vide.

## Conséquences

- Le cas du 12 novembre à 17:11 devient un départ normal avec une ligne
  « reprise automatique par purge au bac ».
- Un vrai bouchon s'arrête pendant la purge, tampon non consommé, chauffes
  coupées.
- `key845` et les autres codes arrêtent comme avant.
- L'affichage de l'écran après `key601`/`key602` reste à observer.
- Pose au repos revérifié, accord de Thomas, relevé puis préflight d'abord.
  Retour arrière de ce paquet avant tout paquet antérieur, qui épingle le
  module `retained-start-v1`.
