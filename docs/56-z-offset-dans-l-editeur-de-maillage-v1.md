# 56 — Le Z accepté se tape dans l'éditeur de maillage

Date : 2026-09-02
Statut : posé, déployé, chaîne complète prouvée sur la machine pendant une
impression en cours

## 1. Ce qui manquait

Le Z accepté appartient au profil de maillage, pas à la machine :
`START_PRINT` lit `z_<profil>` et refuse de démarrer sans lui. Il n'était
écrivable que par la console, avec `KCTRL_Z_SAVE`.

Conséquence pratique, vécue deux fois : le réglage trouvé à l'œil pendant une
première couche — le Z que l'on descend depuis Fluidd en regardant la matière
s'écraser — n'existait que le temps de l'impression. Il fallait le recopier à
la main, ou il était perdu et la fois suivante repartait sur l'ancienne valeur.

## 2. Ce qui a été posé

Dans la barre de l'éditeur de maillage, à côté du profil :

| Élément | Rôle |
|---|---|
| `Z du profil` | La valeur enregistrée pour le profil affiché, modifiable au clavier |
| `reprendre <valeur>` | Recopie dans le champ le décalage Z **en vigueur** sur la machine, sans rien écrire |
| `Enregistrer Z` | Écrit, actif seulement si la valeur tapée diffère de celle enregistrée |

Le champ passe en jaune tant que la valeur tapée n'est pas écrite, en rouge si
elle sort de la plage. Entrée enregistre, Échap revient à la valeur stockée.

Deux routes ajoutées au serveur de l'éditeur : `/api/state` porte désormais
`live_z`, le décalage appliqué à l'instant ; `POST /api/z` écrit.

## 3. Qui écrit

`KCTRL_Z_SAVE`, et personne d'autre. Le serveur ne calcule rien et n'écrit
aucun fichier : il refuse ce qui est manifestement faux — profil inconnu de
Klipper, valeur hors de ±2 mm, valeur illisible — puis passe la main à la
macro, qui revérifie tout et répond. Ce que la page affiche après
enregistrement est la phrase de la macro, pas une phrase inventée par la page.

Le nom du profil part dans une commande G-code : seuls les noms que Klipper
détient déjà comme profils peuvent voyager, donc rien ne peut être glissé dans
un nom.

## 4. Preuves faites sur la machine

Le 2 septembre, **pendant l'impression de `_CORPS_PLA_2h37m.gcode`**, sans la
perturber :

| Question | Preuve |
|---|---|
| L'état porte les deux valeurs | `{"z_offsets": {"k1_p001_t055_r001_n11x11": 0.04}, "live_z": -0.0}` |
| `live_z` est bien celui en vigueur | `homing_origin` de Klipper : `-1.7e-18`, soit le 0 que Thomas avait remis à la main |
| Une valeur hors plage est refusée avant tout envoi | `400 {"error": "Z 40.0000 hors de la plage -2..2 mm"}` |
| Un profil inconnu est refusé avant tout envoi | `400 {"error": "profil inconnu: inconnu"}` |
| Le refus de la macro remonte lisiblement | `503 {"error": "... K1 Control: PROFILE is required and cannot be the default mesh"}` |
| L'écriture aboutit vraiment | `{"messages": ["// K1 Control: Z 0.0400 saved for k1_p001_t055_r001_n11x11"], "saved": 0.04}` puis `z_k1_p001_t055_r001_n11x11 = 0.04` dans `k1-control-saved-vars.cfg` |

L'écriture de preuve a réenregistré **la valeur déjà en place**, 0.04 : la
chaîne entière est vérifiée sans que rien ne bouge pour l'impression en cours
ni pour la suivante.

## 5. Un défaut corrigé en chemin

Le refus d'une macro porte un vrai saut de ligne à l'intérieur de son enveloppe
JSON, que `json.loads` strict rejette. L'opérateur recevait alors l'enveloppe
entière — `{"code":"key165", "msg": ...}`, valeurs comprises — au lieu de la
phrase. Corrigé (`strict=False`) ; le même désenveloppage sert à
l'enregistrement du maillage, qui en profite.

Un refus n'est plus non plus annoncé comme un « corps illisible » : cette phrase
décrivait le navigateur alors que le problème était la valeur.

## 5 bis. Le même piège, de l'autre côté, découvert le soir

Le saut de ligne écrit tel quel n'a pas été corrigé partout : la phrase ajoutée
à `app.mjs` pour annoncer que le Z s'applique au prochain démarrage en portait
deux. Un module dont la syntaxe est invalide n'est jamais exécuté par le
navigateur : la page s'affichait, complète et vide, arrêtée sur
« Chargement… ». Le serveur, lui, répondait `200` — la vérification faite à
`curl` ne pouvait pas le voir.

Corrigé, redéployé, page rechargée : `11 × 11` points affichés, surface
dessinée, `Z du profil` à `0.040`.

La CI était verte pendant tout ce temps. Le seul test front visait l'éditeur
hors ligne ; la page servie par l'imprimante n'était couverte par rien. Une
garde a été ajoutée à `tests/mesh_editor_ui.test.mjs` : `node --check` sur
`app.mjs`, prouvée en réintroduisant la faute, qui fait tomber la suite.

## 6. Ce qui reste vrai

Enregistrer un Z ne déplace rien tout de suite. La valeur est lue par
`START_PRINT` au démarrage suivant, et la page le dit.

Le serveur de l'éditeur ne survit toujours pas à un redémarrage de
l'imprimante ; relance dans HANDOFF.
