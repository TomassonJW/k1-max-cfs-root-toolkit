# Propriétaire CFS direct — installation désactivée V1

Ce paquet prépare la première pose réellement installable du propriétaire CFS
direct choisi par ADR-036. Il ne touche pas encore à la K1 : la configuration
livrée fixe `enabled: false` et le manifeste garde l'autorité de pose fermée.

Dans cet état, le composant :

- se charge dans Klipper ;
- publie un état lisible ;
- ne prend pas l'objet `serial_485` ;
- ne remplace aucune commande stock ;
- refuse réassociation, chargement et retrait avant même de lire leurs arguments ;
- exécute un autotest désactivé sans trame, chauffe ni mouvement.

La future activation est déjà bornée dans le code, mais n'est pas autorisée par
ce paquet. Au démarrage avec `enabled: true`, les dix-neuf entrées stock connues
sont remplacées par un refus ou constatées absentes. Le préflight exige ensuite
`auto_refill = 0`, aucune commande stock active et les CFS `T1/T2` connectés.

## Validation locale

```powershell
& 'C:\Program Files\Python310\python.exe' packages\k1-control-v1\cfs-direct-owner-install-disabled-v1\run_scenarios.py
& 'C:\Program Files\Python310\python.exe' packages\k1-control-v1\cfs-direct-owner-install-disabled-v1\verify_candidate.py
.\scripts\deploy-k1-control-cfs-direct-owner-install-disabled-v1.ps1 -Action Plan
```

La pose, le restart Klipper et toute connexion K1 restent une action distincte.
La gate physique de chargement/retrait restera encore séparée après la pose.
Le backend Moonraker du cycle intégré n'est pas encore abonné à ce nouvel objet
Klipper : ses effets restent donc désactivés après cette seule pose.
