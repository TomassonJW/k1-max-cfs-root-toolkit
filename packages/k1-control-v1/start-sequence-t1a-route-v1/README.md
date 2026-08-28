# START-SEQUENCE-T1A-ROUTE-V1

Cette gate restaure une seule route `T1A` avant le premier essai physique du
propriétaire de démarrage. Elle ne lance aucune impression et ne rend aucune
commande CFS appelable par K1 Control.

L'observateur vérifie d'abord une K1 au repos, froide, sans route engagée, avec
le `11 × 11`, le Z accepté `−0,04 mm`, le propriétaire de démarrage en phase
`idle` et les fichiers installés exacts. Thomas demande ensuite **une seule
fois** le chargement de `T1A` depuis l'interface stock pendant la capture.

La gate passe seulement si une unique transition `[] -> [T1A]` est observée,
si aucun mouvement XYZ ou départ d'impression n'a lieu et si l'état final est
froid, sans commande CFS et sans dérive de configuration, mesh ou Z.

Si l'effet est incertain, le chargement n'est jamais relancé. Si une cible de
chauffe reste active, la gate s'arrête et demande une coupure thermique sûre
séparée avant toute autre action.

## Commandes

Vérification locale du candidat :

```powershell
python.exe packages\k1-control-v1\start-sequence-t1a-route-v1\verify_candidate.py
```

Capture réelle, uniquement avec Thomas devant la K1 :

```powershell
.\packages\k1-control-v1\start-sequence-t1a-route-v1\capture_route_gate.ps1 `
  -CaptureId <identifiant-unique> `
  -DurationSeconds 300
```

Préflight frais sans effet :

```powershell
.\packages\k1-control-v1\start-sequence-t1a-route-v1\capture_route_gate.ps1 `
  -CaptureId <identifiant-unique> `
  -PreflightOnly
```

Le programme de capture ne produit aucun G-code. L'unique effet physique vient
du bouton stock actionné par Thomas pendant l'observation.
