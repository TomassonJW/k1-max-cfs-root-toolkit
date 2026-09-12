# Spool choice gate v1 — le choix des bobines, dans Mainsail

Aucune impression ne part avant que Thomas ait raccordé, à la main, chaque
filament du fichier à une bobine du CFS. Le choix s'ouvre de lui-même dans
Mainsail, par-dessus l'écran, dès qu'un départ est retenu ; une fois tout
raccordé, « Lancer l'impression » fait partir le fichier et la fenêtre se
referme. Décision : ADR-063. Récit et preuves :
`docs/78-le-choix-des-bobines-avant-le-depart-v1.md`.

## Pièces

| Fichier | Rôle | Installé en |
|---|---|---|
| `kctrl_print_gate.py` | prend la main sur `SDCARD_PRINT_FILE` à la connexion de Klipper, retient le fichier, publie filaments et bobines, commandes `KCTRL_GATE_CONFIRM`, `KCTRL_GATE_CANCEL`, `KCTRL_GATE` | `/usr/share/klipper/klippy/extras/kctrl_print_gate.py` |
| `www/bobines/bobines.js`, `logic.js`, `styles.css` | l'interface, montée une fois par `mount(root, options)` | `/usr/data/k1-control-v1/current/www/bobines/` |
| `www/bobines/overlay.js` | la fenêtre dans Mainsail : shadow DOM, apparaît seule quand un départ attend, se replie en pastille, se ferme après le lancement | idem |
| `www/bobines/index.html`, `app.js` | la même interface en page seule, `/bobines/`, pour un téléphone ou Fluidd | idem |
| `mainsail_overlay_patch.py` | ajoute (ou retire, `--remove`) la balise `<script type="module" src="/bobines/overlay.js">` avant `</body>` de l'index de Mainsail, avec copie datée | lancé sur la machine |
| `nginx-location.conf` | les trois blocs à placer avant `location /` : redirection `/bobines`, `location /bobines/`, `location = /index.html` sans cache | `/usr/data/k1-control-v1/state/nginx-active.conf` |
| `logic.test.mjs` | tests node de la partie pure (règle d'affichage de la fenêtre comprise) | — |

La section `[kctrl_print_gate]` est dans
`owned-start-print-v2/k1-control-owned-start-print-v2.cfg`, après
`[kctrl_tool_change]`. `START_PRINT` lit `confirmed_file` : quand la porte a
confirmé le fichier qu'elle démarre, la table CFS est prise telle quelle et
l'appariement automatique (ADR-062) ne tourne pas.

## Ce que voit Thomas

1. Il lance un fichier depuis Mainsail (ou l'écran, ou Creality Print).
2. Klipper retient le départ sans rien chauffer ; en une seconde environ la
   fenêtre Bobines couvre Mainsail avec les filaments du fichier et les
   bobines du CFS.
3. Il touche un filament, puis sa bobine, jusqu'à ce que tout soit raccordé.
4. « Lancer l'impression » : la table CFS est écrite, le fichier part, la
   fenêtre dit « Impression lancée » puis se ferme ; Mainsail suit.
5. « Réduire », Échap ou un clic à côté mettent la fenêtre de côté pour ce
   fichier : une pastille reste en bas à droite pour la rouvrir. « Abandonner
   cette impression » (deux touches) laisse tomber le fichier, rien n'a
   chauffé.

## Installation (machine à l'arrêt, `print_stats.state` = `standby`)

1. Sauvegarder `nginx-active.conf` et le `.cfg` de démarrage.
2. Copier `kctrl_print_gate.py` dans `extras/`, le `.cfg` dans
   `printer_data/config/`, `www/bobines/` dans `current/www/bobines/`, puis
   `chmod 755` le dossier et `chmod 644` ses fichiers (`cat >` en root crée
   en 600 : la passerelle répond 403).
3. Ajouter les trois blocs de `nginx-location.conf` avant `location /` dans
   `nginx-active.conf`, tester (`nginx -t` avec le `-p` de la passerelle),
   puis `/etc/init.d/S57k1_control_gateway reload`.
4. `python3 mainsail_overlay_patch.py /usr/data/k1-control-v1/current/www/mainsail/index.html`
   (copie `index.html.bak-<date>` à côté). Une mise à jour de Mainsail qui
   réécrit son index retire la balise : relancer la commande.
5. `/etc/init.d/S55klipper_service restart` (jamais `FIRMWARE_RESTART`
   pour un module Python).
6. Vérifier : `help` liste `KCTRL_GATE_CONFIRM` ; journal « wrapped
   SDCARD_PRINT_FILE » ; `http://192.168.1.64:4409/` contient la balise ;
   `http://192.168.1.64:4409/bobines/overlay.js` répond 200 ; un départ
   ouvre la fenêtre dans Mainsail.

## Retour arrière

`python3 mainsail_overlay_patch.py --remove …/mainsail/index.html` (ou
recopier la copie datée), recopier les sauvegardes, supprimer
`kctrl_print_gate.py` et son `.pyc`, retirer les trois blocs nginx,
`S57k1_control_gateway reload`, `S55klipper_service restart`.

## Tests

```
py -3.10 -m pytest -q tests/test_kctrl_print_gate_v1.py tests/test_bobines_page_v1.py
node --test packages/k1-control-v1/spool-choice-gate-v1/logic.test.mjs
```
