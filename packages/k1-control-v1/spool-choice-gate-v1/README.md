# Spool choice gate v1 — la page Bobines

Aucune impression ne part avant que Thomas ait raccordé, à la main, chaque
filament du fichier à une bobine du CFS. Décision : ADR-063. Récit et
preuves : `docs/78-le-choix-des-bobines-avant-le-depart-v1.md`.

## Pièces

| Fichier | Rôle | Installé en |
|---|---|---|
| `kctrl_print_gate.py` | prend la main sur `SDCARD_PRINT_FILE` à la connexion de Klipper, retient le fichier, publie filaments et bobines, commandes `KCTRL_GATE_CONFIRM`, `KCTRL_GATE_CANCEL`, `KCTRL_GATE` | `/usr/share/klipper/klippy/extras/kctrl_print_gate.py` |
| `www/bobines/` (`index.html`, `styles.css`, `app.js`, `logic.js`) | la page, servie par la passerelle K1 Control à côté de Mainsail | `/usr/data/k1-control-v1/current/www/bobines/` |
| `nginx-location.conf` | le bloc `location /bobines/` à ajouter dans le `server` de la passerelle | `/usr/data/k1-control-v1/state/nginx-active.conf` |
| `logic.test.mjs` | tests node de la partie pure de la page | — |

La section `[kctrl_print_gate]` est dans
`owned-start-print-v2/k1-control-owned-start-print-v2.cfg`, après
`[kctrl_tool_change]`. `START_PRINT` lit `confirmed_file` : quand la porte a
confirmé le fichier qu'elle démarre, la table CFS est prise telle quelle et
l'appariement automatique (ADR-062) ne tourne pas.

## Installation (machine à l'arrêt, `print_stats.state` = `standby`)

1. Sauvegarder `nginx-active.conf` et le `.cfg` de démarrage.
2. Copier `kctrl_print_gate.py` dans `extras/`, le `.cfg` dans
   `printer_data/config/`, `www/bobines/` dans `current/www/bobines/`, puis
   `chmod 755` le dossier et `chmod 644` ses fichiers (`cat >` en root crée
   en 600 : la passerelle répond 403).
3. Ajouter les deux blocs de `nginx-location.conf` (redirection `/bobines`
   et `location /bobines/`) avant `location /` dans `nginx-active.conf`,
   puis `/etc/init.d/S57k1_control_gateway reload`.
4. `/etc/init.d/S55klipper_service restart` (jamais `FIRMWARE_RESTART`
   pour un module Python).
5. Vérifier : `help` liste `KCTRL_GATE_CONFIRM` ; journal « wrapped
   SDCARD_PRINT_FILE » ; `http://192.168.1.64:4409/bobines/` répond.

## Retour arrière

Recopier les sauvegardes, supprimer `kctrl_print_gate.py` et son `.pyc`,
retirer le bloc `location /bobines/`, `S57k1_control_gateway reload`,
`S55klipper_service restart`.

## Tests

```
py -3.10 -m pytest -q tests/test_kctrl_print_gate_v1.py tests/test_bobines_page_v1.py
node --test packages/k1-control-v1/spool-choice-gate-v1/logic.test.mjs
```
