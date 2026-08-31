# Cycle de production intégré V1 — clos KO sur le propriétaire CFS stock

Le run réel du 31 août 2026 a été arrêté sans retry. La primitive stock de
chargement a repris la température à `220 °C`, référencé X/Y, vidé le mesh actif
et n'a pas engagé `T1A`. Les cibles ont été remises à zéro, le `11 × 11` a été
restauré et K1 Control est désormais en mode `offline`, effets désactivés.

Ce paquet est la première fondation qui vise le parcours utilisateur complet,
et non une nouvelle sous-gate isolée. Il applique ADR-035 : retrait éventuel,
attente du nettoyage manuel, références avant insertion, rechargement du
`11 × 11`, chargement `T1A`, purge unique, impression et fin avec retrait.

## Ce qui est maintenant construit

Le cœur pur `cycle.py` valide l'ordre, les températures, les preuves et
l'unicité des effets. `orchestrator.py` enchaîne le parcours sans retry.
`moonraker_component.py` fournit les routes K1 Control, la sélection explicite
du fichier et le lancement Virtual SD. La page `www/` devient l'entrée simple
depuis le bouton K1 Control déjà présent dans Mainsail.

Le fichier n'est jamais choisi implicitement. K1 Control lit la liste
Moonraker, puis `job_contract.py` exige un G-code Orca mono-matière `PLA`, un
plateau à `55 °C`, les températures publiées dans les métadonnées et exactement
les deux lignes atomiques :

- démarrage Orca : `KCTRL_CYCLE_JOB_ASSERT_V1` ;
- fin Orca : `KCTRL_CYCLE_END_V1`.

L'ancien `START_PRINT`, `END_PRINT`, `T0`, tout homing, toute calibration de
mesh et tout offset Z dans le fichier sont refusés avant la première chauffe.

Les quatre primitives CFS ciblées ne sont plus appelables par ce paquet. Le
chargement stock a confirmé la prise de contrôle thermique et géométrique déjà
documentée ; coupe et retrait restent non qualifiés :

- `BOX_EXTRUDE_MATERIAL TNN=T1A` ;
- `BOX_EXTRUDER_EXTRUDE TNN=T1A` ;
- `BOX_CUT_MATERIAL` ;
- `BOX_RETRUDE_MATERIAL`.

## Parcours utilisateur

1. ouvrir K1 Control depuis Mainsail ;
2. choisir le fichier Orca contrôlé puis cliquer `Préparer l’impression` ;
3. nettoyer la buse lorsque K1 Control a fini le retrait, puis cliquer une fois
   `Buse propre — Continuer` ;
4. K1 Control fait X/Y, un Z précis à `140/55 °C`, recharge sans le mesurer le
   `11 × 11`, charge `T1A`, purge une fois, attend le verdict caméra puis lance
   le modèle ;
5. le G-code de fin relève et descend le plateau, retire et rembobine `T1A`,
   gare la tête, coupe les chauffes et ventilateurs, puis libère les moteurs.

Le verdict caméra n'ajoute aucun clic utilisateur : pendant la première gate,
Codex l'envoie après lecture de l'image fraîche. L'automatisation visuelle de
production ne pourra être promue qu'après avoir acquis les références réelles
de purge et de bonne première couche lors de ce même run.

## État de pose

La fondation UI, le composant et les macros ont été posés, mais la gate réelle
est close KO avant chargement, purge et impression. Le composant installé est
confiné avec `authority_mode: offline` et `effects_enabled: false`. La suite ne
peut pas être un nouvel essai intégré : il faut d'abord remplacer les effets CFS
stock par un propriétaire borné réellement contrôlable, ou accepter une
frontière humaine explicite pour le bouton officiel.
