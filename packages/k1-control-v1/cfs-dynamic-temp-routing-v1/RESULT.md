# Résultat — CFS Dynamic Temp Routing V1

Date : 2026-08-26
Statut : **OK hors imprimante ; propriétaire minimal choisi ; production fermée**

## Verdict

```text
architecture=minimal_separate_filament_owner
matrix=25/25
printer_transport=false
deployment_candidate=false
authorizes_printer_mutation=false
```

La base matière reste un filet statique. Une réaffirmation après `T` reste une
défense. L'interception de `get_material_target_temp` est refusée comme point de
pose : aucun point d'extension stable n'est prouvé dans le module Cython exact
et le chemin stock conserve sa géométrie.

Le contrat impose une cible avant le premier effet, une preuve de route fraîche
et non réutilisable, les températures distinctes de retrait, chargement et
purge, puis les six invariants inchangés. Toute incohérence coupe les deux
cibles et bloque la reprise.

## Preuves locales

- sélection d'architecture déterministe : une seule option couvre les six
  capacités requises ;
- simulateur : **25/25** scénarios attendus verts ;
- deux CFS, first/normal, refill, runout, pause/reprise, annulation et erreurs
  de route couverts ;
- aucun transport, script de pose ou température matière codée dans le moteur ;
- suite Python complète : **350 tests verts**, dont 3 ignorés déjà connus ;
- `git diff --check` : **vert** lors de la clôture locale.

## Limites

- protocole série minimal : non cartographié ;
- coexistence exclusive avec le propriétaire stock : non prouvée ;
- accusés capteur/cutter : non qualifiés par phase ;
- validation physique : non exécutée ;
- pose, restart, chauffe, mouvement, commande CFS, purge et impression : non
  exécutés.

Le vert de cette mission ferme la conception thermique hors ligne. Il n'ouvre
pas une pose et ne reprend pas `MESH-EDGE-DIAGNOSTIC-V1`.
