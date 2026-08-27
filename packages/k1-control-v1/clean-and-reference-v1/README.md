# CLEAN-AND-REFERENCE-V1

Deuxième exigence physique du Goal 3.

Statut : **nettoyage automatique clos KO ; les deux essais fonctionnels ne sont
pas convaincants ; le nettoyage manuel par Thomas devient la règle canonique**.

Le cycle V1 était trop lent, est resté dans la brosse du bac pendant le
refroidissement et a recollé le filament retiré sur la buse. Thomas a dû
nettoyer la buse à la main. La géométrie historique du bac reste une
observation, mais cette brosse n'est plus une candidate fonctionnelle.

Le cycle V3 est une seule action surveillée sur la grande brosse du plateau,
qualifiée à `X66..99 / Y303..307`, avec le contact corrigé à `Z2,5` :

1. vérifier l'état sûr, les axes référencés, le profil `11 × 11` exact et les
   configurations ;
2. chauffer à `220 °C` au parc sûr `X81 Y280 Z35` ;
3. descendre prudemment jusqu'à `Z2,5` ;
4. effectuer huit allers-retours réellement diagonaux à `F12000` ;
5. couper les chauffes et remonter immédiatement de `Z2,5` à `Z7,5` à `F3000` ;
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

Le V2 à `F6000` a paru encore trop lent et trop rectiligne. Le V3 rejoint
l'exemple officiel Klipper : huit balayages à `F12000`. Son chemin alterne les
deux diagonales à l'intérieur de la brosse, sans utiliser la brosse du bac.

Sources examinées :

- https://github.com/Klipper3d/klipper/blob/master/docs/Command_Templates.md
- https://github.com/ZaiZu2/Voron-V2.4-config/blob/main/nozzle_scrub.cfg
- https://github.com/Open-Elegoo-Community/klipper-nozzle-clean-macro
- https://github.com/Fisheye3D/Formbot-Troodon-v2-Klipper-/blob/master/macros.cfg

Pour recréer du filament à nettoyer, le chargement, la petite purge et le
retrait restent manuels via l'interface stock tant que le chemin CFS n'est pas
qualifié. Le second nettoyage attend ensuite le GO explicite de Thomas.

Le V2 est conservé comme preuve technique, mais il n'est pas jugeable : la buse
avait déjà été nettoyée à la main et aucun chargement, petite purge et retrait
ne l'avait précédé. Thomas a ensuite fait cette préparation manuellement. Le V3
a exécuté les huit allers-retours diagonaux à `F12000`, coupé la chauffe,
remonté de `5 mm` et quitté la brosse. L'état final est `X81 Y280 Z35`, buse à
`141,07 °C`, cibles zéro, configurations exactes et profil `11 × 11` inchangé.
Thomas a jugé le résultat non convaincant et a fermé cette voie. Aucun V4 ni
référence finale automatique ne sera lancé depuis cette gate. Thomas nettoie
désormais la buse à la main avant toute référence Z ou impression sensible.
