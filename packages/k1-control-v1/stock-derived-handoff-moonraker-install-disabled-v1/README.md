# Stock-derived handoff + Moonraker install-disabled V1

Ce paquet raccorde la géométrie pré-insertion de R4 au moteur de cycle CFS
dérivé des séquences stock, sans activer le moindre effet.

La pose prévue ajoute deux composants Klipper désactivés, le cœur pur de
l'orchestrateur et un composant Moonraker lui aussi désactivé. Les trois portes
d'effet sont immuables dans cette révision : modifier seulement un fichier de
configuration ne permet pas de les activer.

Le handoff n'accepte que le contexte actuellement qualifié : XYZ terminés sans
filament, mesh `k1_p001_t055_r001_n11x11`, Z `-0,04`, plateau `55 °C`, buse de
palpation `140 °C`, première couche `190 °C`, deux CFS connectés, aucune route
engagée et remplacement stock coupé. Il consomme ensuite le jeton R4 sans
chauffer, bouger, palper, recalculer le mesh ou envoyer une trame CFS.

Le cœur conserve le roulement entre bobines strictement identiques : un seul
spare approuvé, identité complète identique, pause et contexte préservés, puis
confirmation caméra avant reprise. Une correspondance approximative ou
plusieurs candidats ferment la route.

## Commandes locales

```powershell
python packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\run_scenarios.py
python packages\k1-control-v1\stock-derived-handoff-moonraker-install-disabled-v1\verify_candidate.py
pwsh -File scripts\deploy-k1-control-stock-derived-handoff-moonraker-install-disabled-v1.ps1 -Action Plan
```

La pose froide ne constitue ni une activation, ni une validation physique, ni
une autorisation de production.
