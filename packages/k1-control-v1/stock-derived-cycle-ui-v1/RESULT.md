# Résultat — interface du cycle stock dérivé V1

Statut : `INSTALLED_VALIDATED_STATIC_NO_PHYSICAL_TRIAL`.

Capture : `20260831-215849-g4-k1-control-stock-derived-cycle-ui-v1`.

## Preuves acquises

- backup exact de `index.html`, `app.js` et `styles.css` ;
- trois fichiers racine remplacés et relus avec leurs empreintes attendues ;
- sous-dossier `calibration/` inchangé ;
- aucun redémarrage de service ;
- aucun G-code, chauffage, mouvement, filament, CFS, palpage ou mesh ;
- `VALIDATE_STOCK_DERIVED_CYCLE_UI_V1_OK` obtenu pendant la pose ;
- seconde validation indépendante obtenue après la pose ;
- propriétaire d’activation toujours valide au repos.

## Limite restante

L’interface est installée, mais aucun bouton d’impression n’a été utilisé sur
la K1. Les références caméra `BIN_RELEASED_CLEAN`, `PRIME_OUTSIDE_BED` et
`FIRST_LAYER_GOOD` manquent encore. Le premier cycle physique doit donc rester
surveillé et servir à construire ces preuves avant toute autonomie complète.
