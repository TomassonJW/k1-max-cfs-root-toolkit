# CLEAN-MOTION-V1 — première tranche physique du Goal 3

Statut : **close OK ; deux brosses qualifiées à froid ; verdict final humain
`E4 OK` ; meilleur profil actuel `11 × 11` actif et inchangé**.

## Faits déjà qualifiés sans mouvement

La capture privée `20260827-clean-motion-v1-read-only-sources-v3` a obtenu
`CAPTURE_OK` uniquement par requêtes GET. Elle confirme les limites logiques
X `−2…306,5 mm`, Y `−0,5…307,5 mm`, Z `−10…305 mm`.

Le `prtouch_v2` actif déclare une zone de nettoyage X `68…94 mm`,
Y `304,5…306,5 mm`, un trajet X de `20 mm` et un delta Z de `−0,15 mm`.
Les commandes stock de nettoyage et de référence sont réellement enregistrées.
Leur code complet n'a pas été exporté.

Ces valeurs prouvaient la configuration logicielle, pas la position physique
de la brosse. Les captures manuelles et les essais observés décrits plus bas
ont depuis établi la géométrie réellement utilisable.

## Pourquoi cette tranche vient en premier

Le contrat de cycle exige un nettoyage autonome, mais la position et la hauteur
réelles de la brosse ne sont pas encore qualifiées. Le PRTouch sait mesurer le
plateau ; il ne doit pas servir à enfoncer la buse dans la brosse. Avant toute
chauffe, purge ou recette de nettoyage, il faut donc mesurer la géométrie à
froid et observer un trajet sans collision.

Le préalable corrigé est maintenant satisfait :
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1 = RESTORE_OK`, avec le meilleur
profil observé `k1_p001_t055_r001_n11x11` confirmé actif par deux lectures
indépendantes. Tous les profils actuels ont des défauts de bord ; aucun n'est
qualifié robuste.

## Confirmations humaines

Thomas a confirmé concrètement :

1. le plateau est entièrement libre ;
2. la brosse et le réceptacle sont installés, immobiles et visibles ;
3. il peut arrêter immédiatement la machine ;
4. il voit directement la buse ou dispose d'une caméra sans angle mort.

Ces confirmations ont autorisé seulement des déplacements à froid par petits
checkpoints. Elles n'ont autorisé ni chauffe, ni extrusion, ni CFS, ni
impression.

## Déroulement réalisé

1. Relire l'état sûr, les limites machine et le meilleur profil actuel actif.
2. Noter les limites visibles de la brosse et du réceptacle sans mouvement.
3. Référencer uniquement ce qui est nécessaire pour circuler, sous observation.
4. Se placer très au-dessus de la zone, puis approcher par checkpoints validés.
5. Déterminer à vitesse très faible le plan de premier contact à froid.
6. Revenir au-dessus de la zone, puis tester une trajectoire sèche et bornée.
7. Sortir par la direction sûre, parquer et relire l'état final.

Le premier checkpoint a pris en compte que le `G28` stock recharge
automatiquement `default` : il a remis aussitôt le `11 × 11` exact et commandé
une hauteur libre de `Z=50 mm`. Le premier validateur a confondu la position
G-code `50,00 mm` et la position physique compensée `50,23 mm`, puis a produit
un faux KO. Aucun mouvement n'a été rejoué. La validation corrigée en lecture
seule est verte. Thomas a confirmé `CHECKPOINT C OK` ; le mouvement ne sera pas
rejoué.

Le checkpoint D1 a ensuite approché à froid et à hauteur libre jusqu'à
`X81 Y280 Z50`, à `20 mm/s`. Ce point est encore `24,5 mm` avant le début Y de
la zone stock déclarée. La position G-code finale est exacte ; la position
physique compensée vaut `Z=50,23 mm`. Les chauffes sont à zéro, aucune route CFS
n'est engagée, les configurations n'ont pas changé et le `11 × 11` exact reste
actif. D1 est donc techniquement vert.

Thomas a confirmé `D1 OK`, sans signaler de bruit, contact, obstacle ou perte de
visibilité. D1 n'a pas été rejoué. Après un préflight frais, D2 a approché une
seule fois jusqu'à `X81 Y300 Z50` à `10 mm/s`, soit `4,5 mm` avant la zone Y
stock. L'état technique final reste froid, sûr et inchangé hors position.

Thomas a confirmé visuellement `D2 OK`. D2 n'a pas été rejoué. Après un
préflight frais, D3 a approché une seule fois jusqu'à `X81 Y303 Z50` à
`5 mm/s`, soit `1,5 mm` avant la zone Y stock. L'état technique final reste
froid, sûr et inchangé hors position.

Thomas a confirmé `D3 OK`. Deux longues captures sous conduite manuelle ont
ensuite fixé les zones utiles :

- grande brosse : quatre coins stables autour de `X66..99 / Y303..307 / Z2`,
  puis remontée sûre à `Z32` ;
- seconde brosse : carré autour de `X203..206 / Y303..305 / Z32`, avec entrée
  et sortie sûres à `X203 Y273 Z32`.

E1 a volontairement gardé trop de marge et a été rejeté humainement : il
n'aurait nettoyé aucune brosse. E2 a ensuite validé le balayage réel de la
grande brosse de `X99` à `X66`, à `Y305 / Z2`, à `5 mm/s`, avec retour sûr.
E3 a montré que la seconde brosse exige moins d'un millimètre de marge en Y.
E3-R2 a qualifié l'approche resserrée à `Y304,5` et E4 a finalement validé le
cycle exact demandé : aller-retour `X203..206` à `Y305`, décalage à `Y304`,
second aller-retour, puis sortie à `Y273`. Le verdict humain final est
`E4 OK`.

## Verdict

La gate est **OK** : les trajets retenus ont été observés sans collision,
contact inattendu, perte de visibilité, chauffe, extrusion, action CFS,
palpage, mesh ou modification Z. Le meilleur profil actuel `11 × 11` est resté
actif et les cibles thermiques sont à zéro.

Le prochain travail est la gate distincte
`G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1` : transformer ces coordonnées qualifiées
en recette versionnée, produire une purge visible dans le réceptacle, nettoyer
à chaud de façon bornée, puis lancer une seule référence Z avec buse propre et
relire l'état sûr final.
