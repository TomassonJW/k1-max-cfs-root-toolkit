# CLEAN-AND-REFERENCE-V1

Deuxième exigence physique du Goal 3.

Statut : **le premier cycle chaud est KO ; la brosse du bac est condamnée pour
le nettoyage automatique ; le préflight V2 sur la brosse du plateau est vert
et le second essai attend la préparation manuelle puis le GO humain**.

Le cycle V1 était trop lent, est resté dans la brosse du bac pendant le
refroidissement et a recollé le filament retiré sur la buse. Thomas a dû
nettoyer la buse à la main. La géométrie historique du bac reste une
observation, mais cette brosse n'est plus une candidate fonctionnelle.

Le cycle V2 est une seule action surveillée sur la grande brosse du plateau,
qualifiée à `X66..99 / Y303..307 / Z2` :

1. vérifier l'état sûr, les axes référencés, le profil `11 × 11` exact et les
   configurations ;
2. chauffer à `220 °C` au parc sûr `X81 Y280 Z35` ;
3. descendre prudemment jusqu'à `Z2` ;
4. effectuer six allers-retours à `F6000` entre `Y303,5` et `Y306` ;
5. couper les chauffes et remonter immédiatement de `Z2` à `Z7` à `F3000` ;
6. sortir immédiatement à `X81 Y280 Z35`, puis attendre hors brosse que la
   buse soit au plus à `142 °C` ;
7. seulement après confirmation visuelle de la buse propre, rétablir la fenêtre
   de référence `140/55 °C`, lancer une seule fois `ACCURATE_G28`, recharger le
   meilleur profil actuel `11 × 11`, remettre les chauffes à zéro
   et relire l'état final.

Tout frottement pendant le refroidissement, toute fin de cycle au contact et
toute utilisation automatique de la brosse du bac sont interdits. Toute
réponse humaine négative coupe les chauffes et ferme la suite. Aucun checkpoint
physique n'est rejoué automatiquement.

Deux lectures live montrent les deux CFS connectés, aucune route engagée et les
codes matière actuels des huit slots. Elles ne peuvent pas identifier le
segment déjà présent dans la tête. L'historique retenu contient en outre un
marqueur de chargement postérieur au retrait historique T1A ; T1A/`000001` ne
peut donc pas être promu en identité actuelle par déduction.

`F6000` est un premier essai borné : l'exemple officiel Klipper utilise huit
balayages à `F12000`, et une recette Voron courante utilise sept allers-retours
à `F12000` avec une remontée immédiate de `7 mm`. Le candidat K1 reste à la
moitié de ces vitesses publiées, mais vingt fois au-dessus du contact lent
local précédemment qualifié à `F300`.

Sources examinées :

- https://github.com/Klipper3d/klipper/blob/master/docs/Command_Templates.md
- https://github.com/ZaiZu2/Voron-V2.4-config/blob/main/nozzle_scrub.cfg
- https://github.com/Open-Elegoo-Community/klipper-nozzle-clean-macro
- https://github.com/Fisheye3D/Formbot-Troodon-v2-Klipper-/blob/master/macros.cfg

Pour recréer du filament à nettoyer, le chargement, la petite purge et le
retrait restent manuels via l'interface stock tant que le chemin CFS n'est pas
qualifié. Le second nettoyage attend ensuite le GO explicite de Thomas.

Le préflight V2 frais est vert sans G-code, mouvement ni chauffe : K1 en
`standby`, cibles zéro, tête à `X203 Y273 Z35`, configurations exactes et
profil `11 × 11` actif inchangé.
