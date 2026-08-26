# CFS Boundary Guard V1

Statut : candidat hors imprimante ; production fermée.

Ce paquet transforme les six états critiques d'une frontière CFS en gardes
vérifiables : cible buse, cible plateau, Z accepté, origine Z, mesh et homing.
Il ne se connecte pas à la K1, n'envoie aucun G-code et ne corrige jamais un Z
à l'aveugle.

Le passage réel du 26 août est volontairement refusé : la cible buse passe de
`190` à `220 °C` et un `G28 X Y` apparaît dans la frontière CFS. Le plateau est
resté à `0 °C` pendant ce passage. Deux essais directs ont d'abord visé une
ancienne adresse DHCP ; la connexion canonique a ensuite requalifié l'état sûr
persistant. Cela ne recrée pas le Z transitoire pendant l'incident : le champ Z
de cette fixture ne constitue donc pas une nouvelle preuve physique.

## Ce que signifie un résultat vert

`pass_offline_trace_only` signifie seulement que la trace fournie respecte le
contrat. Cela n'autorise ni pose, ni chauffe, ni mouvement, ni purge, ni
impression. Une future primitive devra encore être observée pendant toute sa
durée sur la vraie machine.

La fixture `safe-phase.json` est synthétique. Elle teste les invariants ; elle
ne prétend pas que la primitive stock montrée accepte une température dynamique.

## Exécution locale

```powershell
python packages/k1-control-v1/cfs-boundary-guard-v1/evaluate_trace.py `
  packages/k1-control-v1/cfs-boundary-guard-v1/contract.json `
  packages/k1-control-v1/cfs-boundary-guard-v1/fixtures/safe-phase.json
```

Le code retour vaut `0` pour une trace conforme, `1` pour une primitive
refusée et `2` pour une preuve incomplète ou invalide.
