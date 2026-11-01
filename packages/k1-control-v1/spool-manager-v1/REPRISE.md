# Reprise : gestion des bobines

Passation du 1er novembre 2026 pour la session qui reprend la mission
« gestion des bobines » (document 102, ADR-075). Ce dossier remplace le
contexte de la session précédente : tout ce qu'il faut pour finir est ici.
À fondre dans `HANDOFF.md` puis à supprimer au merge de la PR de la mission.

Thomas veut de la vitesse : écrire `spools.js` d'un bloc depuis la section 5,
le tester, pousser. Ne pas relire en boucle ce que ce dossier décrit déjà ;
ouvrir un fichier du dépôt seulement pour un détail qui manque ici.

## 1. État

- Branche `claude/spool-manager-ui-1471c8`, suite de `feat/spool-manager-v1` (partie de `main` à 373f262), poussée ; PR brouillon #95 vers `main`, CI verte.
- Fait, testé et poussé :
  - ADR-075 acceptée par Thomas : la bibliothèque vit dans K1 Control, sur la K1 (c4e2bc2) ;
  - lot A : stockage atomique de la bibliothèque, du journal et des points de reprise (bee8cee) ;
  - lot B : catalogue des bobines vides tiré de SpoolmanDB, licence MIT (59fe398) ;
  - lots C à E : fiches, calculateur, stock, correspondance CFS (00acbb4) ;
  - lot G : décompte de ce que chaque bobine donne pendant une impression (ab0281f) ; une bobine sans puce que le CFS ne sait pas identifier compte comme présente (6c23f8d, f960eaa) ;
  - lot F : bibliothèque servie par Moonraker, synchronisation CFS (dedd3fa), document 102 aligné sur le code (4d1be19) ;
  - lot H : la fenêtre de départ montre le reste de chaque bobine (5c41acf) ;
  - lot I, première moitié : logique pure de la fenêtre et ses 24 tests (6e74438) ;
  - lot I, seconde moitié : fenêtre `spools.js`, CSS, chargement par `overlay.js`, 11 tests d'interface sur un faux DOM, contrôle de chaque route contre le composant, étape CI « Spool manager logic » (4312d27) ;
  - lot J : labo hors imprimante et rendu vérifié sur le vrai Mainsail en lecture seule (e6b2db9, 1f80609, bc8cab8, 15fe072, 701fbb3), section 12 ;
  - lot K : paquet de pose `spool-manager-install-v1` (1165513, 15bb85b), relevé et préflight verts sur la K1 au repos le 1er novembre à 19:34, sans rien écrire, section 9.
- Pas commencé : la pose, L et la clôture (section 9).
- Rien de ce module n'est posé sur la K1. Aucune écriture, pose ni G-code n'a été faite pour cette mission ; seuls le relevé et le préflight du lot K l'ont lue, au repos.
- Derniers résultats, le 1er novembre après 15bb85b : suite complète 2957 passés, 6 ignorés, 2 désélectionnés, 2 xfail, 41 sous-tests, dont 125 pour `tests/test_spool_manager_install_v1.py` ; `node --test` : `mesh_editor_ui.test.mjs` 7/7, `logic.test.mjs` 43/43, `spools-logic.test.mjs` 35/35.
- Pilotage : synchronisé avec `main` le 1er novembre (8846197), conflits de `HANDOFF.md` et `STATE.md` résolus en gardant tout `main`. Depuis, `main` a reçu les PR #96 et #94 : resynchroniser avant le merge.

## 2. Règles machine de la mission

- File du verrou `VERROU-K1.md` : point 6 = pose de la fin V5 par la session purge, Thomas présent, quand il le décide ; point 7 = la pose de ce module. Prendre le verrou avant toute écriture, pose ou G-code. Les lectures seules au repos restent libres. Ce fichier n'est pas dans le dépôt : demander son chemin à la session purge.
- Jamais de pose, de redémarrage de Klipper ou de service pendant une impression, même en pause (règle du 24 septembre). Revérifier le repos juste avant l'arrêt.
- Écrire une bobine au CFS est un G-code : rien avant la pose qualifiée et le verrou.
- Accès : alias SSH `k1max-root`, scripts passés par stdin (`sh -s` ou `python3 -`), ni bash ni sftp sur la machine, copie par `cat | ssh`. Pages statiques en 755/644 (un `cat >` en root crée du 600 et nginx répond 403). Jamais `tail -n` sur `klippy.log`. Retirer `sn` et `uuid` de toute lecture.
- La pose redémarre seulement le Moonraker dédié. Budget : Moonraker ≤ 45 Mio, ≥ 70 Mio libres, croissance du swap ≤ 8 Mio. Le relevé reste léger et ne tourne que page visible.
- Dépôt public : aucune adresse, aucun identifiant de session, numéro de série ni contenu de la base matériau Creality dans Git. Fixtures synthétiques seulement. La synchronisation du 1er novembre a retiré l'adresse privée que portaient l'ancien README de `spool-choice-gate-v1` et `logic.test.mjs` : ne jamais la recopier. `inventory/raw/` est privé.

## 3. Fichiers

| Chemin | Rôle |
| --- | --- |
| `docs/102-gestion-des-bobines-plan-v1.md` | plan, contrat d'interface, lots |
| `packages/k1-control-v1/spool-manager-v1/kctrl_spools_model.py` | modèle : actions, validations, messages |
| `.../spool-manager-v1/kctrl_spools.py` | composant Moonraker : points d'accès |
| `.../spool-manager-v1/kctrl_spools_store.py` | stockage atomique et copies de secours |
| `.../spool-manager-v1/kctrl_spools_counter.py` | décompte pendant l'impression |
| `.../spool-manager-v1/calculator-vectors.json` | vecteurs du calculateur, partagés Python et JS |
| `.../spool-manager-v1/build_tares.py` | construit `tares.json` depuis SpoolmanDB |
| `.../spool-manager-v1/lab/material_database.synthetic.json` | base matériau synthétique (tests, labo) |
| `packages/k1-control-v1/spool-choice-gate-v1/www/bobines/` | `overlay.js`, `bobines.js` (fenêtre de départ), `spools.js` (gestionnaire), `logic.js`, `spools-logic.js`, `styles.css`, `tares.json`, `LICENSE-SpoolmanDB.txt`, `package.json` (`"type":"module"`) |
| `.../spool-choice-gate-v1/mainsail_overlay_patch.py` | ajoute `<script type="module" src="/bobines/overlay.js"></script>` avec le marqueur `<!-- k1-control: bobines -->` |
| `.../spool-choice-gate-v1/spools-logic.test.mjs` | 35 tests : 24 de la logique, 11 de la fenêtre sur un faux DOM |
| `tests/test_bobines_page_v1.py` | contrôles des pages : `PAGE_FILES`, pas d'`http`, liens relatifs, TAP node |
| `tests/test_kctrl_spools_{model,store,counter,moonraker,tares,py38}_v1.py` | tests Python du module |
| `packages/k1-control-v1/end-after-refill-install-disabled-v1/frozen/www/bobines/` | copies gelées de `bobines.js`, `logic.js`, `overlay.js` (voir section 11) |
| `packages/k1-control-v1/gateway-private-lan-no-auth-v1/nginx.conf` | passerelle du port 4409 |
| `.github/workflows/tests.yml` | CI : job Python 3.10, job Node 22 |

## 4. Ce que la K1 sert

### Points d'accès, sous `/machine/k1_control/spools/`

Moonraker enveloppe chaque réponse dans `{"result": …}` ; une erreur arrive
dans `payload.error.message`. `_guard` : ModelError donne 409 avec le texte du
modèle, StoreError donne 500 « enregistrement impossible : %s ».

GET :

- `status` : `payload.result` = `_public()`.
- `materials` : `{materials:[{brand,density,diameter,id,name,type}] triés, error}`.
- `journal?limit=1..200` : `result.entries`, du plus récent au plus ancien, `t` en secondes ; limite fausse : 400 « limite mal formée ».
- `planned?file=` : `{file, planned, note}` ; sans fichier : 400 « fichier attendu ».
- `export` : `{format:"kctrl_spools.export", schema, exported (s), library, journal (≤ 10000)}` ; dans `library`, `spools`, `filaments` et `empty_spools` sont des dicts par id ; stockage verrouillé : 409 « export impossible : %s ».

POST `action`, corps `{action, params, revision}`, réponse `result.result` et `result.status` :

- 400 « action attendue » ou « paramètres attendus » ; 503 « bibliothèque en lecture seule : %s ».
- Révision facultative ; booléen ou non entier : 400 « révision mal formée » ; écart : 409 « la bibliothèque a changé entre-temps : la fenêtre se met à jour, refais l'action ».

POST `import`, corps `{document, revision}`, réponse `{"result": {"revision"}, "status": _public()}` :

- Refus dans l'ordre : impression ou job ouvert, 409 « import refusé pendant une impression » ; stockage verrouillé, 409 « import refusé : %s » ; puis la révision.
- Marche en lecture seule ; un import réussi lève `read_only`. Les écritures CFS en attente ne sont pas reprises.
- Erreurs du modèle : « fichier d'export des bobines K1 Control attendu », « export d'une version plus récente de K1 Control : mettre à jour d'abord », « export sans bibliothèque », « export incohérent : %s ».

POST `cfs-write`, corps `{slot, revision}` :

1. emplacement pas une chaîne : 400 « emplacement attendu » ;
2. bibliothèque inscriptible, puis révision ;
3. Klipper non connecté : 503 « Klipper non connecté : écriture au CFS impossible » ;
4. résultats d'écriture non enregistrés : enregistrés d'abord ;
5. impression ou job ouvert : mise en attente ; sinon lecture de l'état de repos ; illisible : 503 « état de la K1 illisible : écriture refusée » ; `PRINTING_NOW` : mise en attente ; autre problème : 409 « écriture refusée : %s » ; sinon écriture.

- En attente : `{slot, queued:true, written:false, result:"en_attente", detail:"sera envoyé au CFS à la fin de l'impression"}`.
- Écrite : `{slot, queued:false, written: result=="ok", result ∈ ok/erreur/ecart, detail}` ; erreur : « pas de réponse de Klipper en 30 s » ou « refusé par Klipper : %s » ; ecart : « le CFS montre autre chose après l'écriture ».
- Pire cas d'environ 53 s : délai client de 65 s. Statuts 0, 502 et 504 = issue inconnue ; un 503 est un refus net.

### Démarrage

`read_only` vaut « démarrage impossible : %s », « stockage verrouillé : %s »
ou « bibliothèque incohérente : %s ». `store` =
`{"source":"", "revision":0, "fallback":False, "damaged":[{file, reason}], "fresh":False, "quarantined":"", "locked":""}` ;
`fresh` est aussi vrai au tout premier démarrage.

### `_public()`

- `version`, `revision`, `read_only`, `store`.
- `materials` `{count, error}`.
- `klippy` `{connected, cfs_ready, printing}` ; `printing` = impression ou job ouvert.
- `counter` `{restored, refused (bool), live}`.
- `slots`, `slots_error`, `attention` (chaînes), `spools` (vues : champs plus `label`, `remaining`, `low`).
- `empty_spools` (dict), `filaments` (dict), `unassigned`, `prints`, `settings`, `pending_cfs` (par emplacement).
- `counting_verified`, `unsaved_writes` (emplacements triés), `reports_waiting` (entier).

Détail des champs :

- `counter.live` = `{period: null | {kind ("job"|"rest"), id, file, start, notes[]}, route: null (inconnue) | "" (rien d'engagé) | slot, spools:[{slot, spool (peut être ""), mm}], waiting_mm}`. Une note s'affiche par `typeof note === "string" ? note : note.text`.
- `unassigned` : 50 au plus, `{id:"S%03d", job, slot, mm, on, reason}`.
- `prints` : 20 au plus, du plus ancien au plus récent, `{job, file, start, end, outcome, per_spool:[{spool,slot,mm,g,m}], unassigned:[ids], planned:[{mm,g}], notes:[≤10], assigned?:[{segment,spool,mm,g}]}`.
- `pending_cfs[slot]` = `{spool, material, colour, on}`.
- `settings` par défaut `{"cut_loss_mm":0.0,"low_g":100.0}`.
- `remaining` = `{net_g, exhausted, shown:{g, percent, m}, gross_g}`.

### Vues d'emplacement

`{slot, observed:{connected, present, material ("0" + id à 5 chiffres | ""), colour (6 hex majuscules), chip (0..100 | None), type}, spool (id | ""), pending, last_write, candidates, plan, status}`.

- `status` ∈ hors_ligne, en_attente_cfs, inconnue, vide, attendue, ok, a_verifier. Les emplacements connectés sont toujours listés.
- `plan` = `{slot, spool, material: "0"+id | None, colour | None, impact:{gained, lost, partners}}`.
- `last_write` = `{spool, material, colour, result ∈ ok/ecart/erreur/annulee, detail, read, on}`.

### Validations du modèle

- "" pour un champ à choix (`spool_material`, `state`, `kind`, `source`) est une erreur.
- "" ou None pour un nombre veut dire « inchangé » : le client refuse lui-même un nombre obligatoire vidé.
- "" pour un texte est une vraie valeur.
- Messages : « %s manquant », « %s : %d caractères au plus », « %s : nombre attendu », « %s : entre %s et %s », « %s : %r inconnu », « %s introuvable : %r », « emplacement : T1A à T4D attendu, reçu %r », « couleur manquante », « couleur : six chiffres hexadécimaux attendus, reçu %r », « champ inconnu : %s ».

### Actions du modèle

Bobines vides :

- `create_empty_spool` : manufacturer, name, spool_material, tare_g (> 0, ≤ 2000), nominal_net_g (> 0, ≤ 10000), source ∈ spoolmandb/pesee/manuel, catalogue, notes ; erreurs « référence SpoolmanDB manquante », « déjà dans la bibliothèque : %s » ; rend `{id}`.
- `edit_empty_spool` `{id + champs}` : une tare changée passe la source à manuel ; rend `{id, changed}`.
- `weigh_empty_spool` `{id, tare_g}` : source pesee.
- `delete_empty_spool` : refus « bobine vide utilisée par %s ».

Fiches :

- `create_filament`, `edit_filament`, `delete_filament` : manufacturer, name, material (mis en majuscules), colour (obligatoire à la création), diameter_mm (1.0..3.5, défaut 1.75), density (0.5..8.0), creality_id, notes.
- Erreurs : « fiche identique déjà présente : %s », « fiche utilisée par %s », « choisir la fiche matériau Creality : aucune ne correspond à %s %s », « fiche matériau Creality %s inconnue de la K1 », « la fiche Creality %s est du %s, pas du %s : … », « densité inconnue pour %s : la saisir ».
- create rend `{id}` ; edit rend `{id, changed}`.

Bobines :

- `create_spool` : filament, empty_spool, initial_net_g, basis_kind (neuve/pesee/estimation), value_g, state (stock/a_ranger/cfs), slot (cfs seulement), place, notes. Avec pesee, `value_g` est le poids **brut** et demande la bobine vide. Erreurs « net initial manquant : le donner ou choisir la bobine vide », « emplacement donné pour une bobine hors du CFS ». Rend `{id}`.
- `edit_spool` : id, filament, empty_spool ("" la retire), initial_net_g, notes. Erreurs « cette bobine a un reste pesé : la bobine vide donne sa tare », « net initial de %s g sous l'estimation actuelle de %s g ».
- `set_remaining` `{id, kind, value_g}` rend `{id, net_g}` ; avec kind neuve, pas de value_g.
- `put_in_cfs` `{id, slot}` : erreurs « déjà au CFS en %s : la retirer d'abord », « archivée : la remettre en stock d'abord » ; l'ancienne bobine de l'emplacement passe à a_ranger.
- Changements d'état : `remove_from_cfs {id}`, `store {id, place}`, `finish {id}`, `discard {id}`, `restore {id}`.
- `adopt_cfs` `{slot}` rend `{id, filament}`.

Consommations et réglages :

- `assign_segment` `{segment, spool}` rend `{id, g}` ; `dismiss_segment` `{segment}`.
- `settings` `{cut_loss_mm 0..200, low_g 0..5000}` rend `{changed}`.

### Enregistrements

- Ids : bobine `B%03d`, fiche `F%03d`, bobine vide `V%03d`.
- Tous les temps (created, updated, basis.on, last_gap.on, weighed_on, pending.on, last_write.on, exported) sont `context.now`, en secondes. `weighed_on` vaut 0 sauf source pesée.
- `basis` = `{kind, value_g, on}` ; `last_gap` = `{g, counted_g, previous, on}`.

### `tares.json` (suivi dans `www/bobines/`)

`{format:"kctrl_spools.tares", source:"SpoolmanDB", commit, license:"MIT", copyright:"Copyright (c) 2024 Donkie", entries:[196]}` ;
chaque entrée = `{key:"Maker|net|tare|spool_material", lines:[{density,material,name}], manufacturer, net_g, spool_material, tare_g}`.

### Contrat d'interface du document 102

- Un bouton « Bobines » sur la barre du haut de Mainsail, avec un badge.
- La fenêtre s'ouvre sous le bouton, plein écran sur téléphone ; Échap ou un clic dehors la ferme.
- Onglets : CFS, Stock, Bobines vides, Journal.
- Aucune écriture au CFS pendant une impression, même en pause : elle attend la fin, puis une relecture la confirme.
- L'effet sur les paires de recharge s'affiche avant d'écrire ; « à vérifier » se règle en un clic.
- Un reste lu sur une puce est marqué « puce ».

### Mainsail et empilement

- Mainsail v2.18.2 (Vue 2, Vuetify 2) derrière nginx sur le port 4409, sans authentification ; `/bobines/` est servi avec `Cache-Control "no-store" always`.
- Barre du haut, relevée au lot J : `header.topbar.v-app-bar`, 48 px, fixe, couche 8 ; elle contient l'icône de navigation, le logo, `.v-toolbar__title`, le sélecteur d'imprimante, un espace, des boutons et des menus. Le bouton large « Sauvegarde de la configuration » y apparaît tant qu'une sauvegarde est en attente sur la K1 (c'est le cas au 1er novembre). Sous 1264 px, le tiroir de navigation devient temporaire avec un voile `.v-overlay` en couche 7.
- `overlay.js` est un module : `import("./spools.js")` se résout à côté de lui.
- Couches : barre z 8 ; bouton dans la barre z 9 (couche de la barre + 1) ; bouton rond z 6, sous le voile du tiroir tant qu'il est ouvert ; fenêtre z 2147482000 ; toast z 2147482001 ; fenêtre de départ et sa pastille z 2147483000, son mode dans `#kctrl-bobines` `dataset.mode` ("hidden", "choice", "launched", "ending", "minimised").
- nginx : ligne 16 `client_max_body_size 100m`, ligne 75 `1024m`, ligne 79 `proxy_read_timeout 900s`. Vérifier au lot K que ce délai couvre `/machine/` : le défaut de 60 s est sous les 65 s de `cfs-write`.

## 5. Conception de `www/bobines/spools.js`

### Règles du fichier

Un seul Write. LF seulement. Pas de tiret cadratin ni demi-cadratin, le
tiret simple seulement, y compris dans les textes affichés. Pas de `http://`
ni `https://`. Pas de `src="` ni `href="` littéral : poser `link.href = url`.
Un SVG sans `xmlns`.

### En-tête

```js
// The spool manager inside Mainsail (document 102, lot I): a « Bobines »
// button over Mainsail's top bar and the window it opens, to keep the spools,
// their fiches and their empty spools, and to see what the CFS holds.
//
// overlay.js loads this module on its own, after the start window: an error
// here leaves the start window intact. It never changes Mainsail's page: the
// button and the window live in their own shadow root, laid over the top bar,
// and fall back to the top-right corner when the bar is not where expected.
//
// Everything comes from /machine/k1_control/spools/ and every change goes
// back as one action the K1 checks again. Nothing is written to the CFS
// during a print, even paused: the K1 keeps the write for the end.
```

### Ce qu'exportent `logic.js` et `spools-logic.js`

`logic.js` : `normaliseHex` (l. 15, rend "RRGGBB" ou ""), `colourName`
(l. 47, « couleur inconnue » ou un nom), `isLight` (l. 76),
`figure(value, decimals=1)` (l. 256 : virgule décimale, pas de zéros de fin,
"" si non fini, mais `figure(null)` rend "0"), `gramsLabel` (l. 265,
`figure(v, |v| < 10 ? 1 : 0)`, sans unité), `shortName(path)` (l. 424, le nom
de fichier).

`spools-logic.js` :

- Constantes : DIAMETER, SLOT_NAMES, NAME_LIMIT (80), NOTES_LIMIT (500), VALUE_MAX_G (15000), NEARLY_EMPTY_G (20), REMAINING_FIELDS, GROSS_WITHOUT_TARE, STATE_LABELS, STATE_ORDER, BASIS_LABELS, TARE_SOURCE_LABELS `{spoolmandb:"SpoolmanDB", pesee:"pesée", manuel:"saisie"}`, SPOOL_MATERIALS `["plastique","carton","métal","inconnue"]`, OUTCOME_LABELS, WRITE_RESULTS (avec annulee), SETTING_LABELS, SLOT_STATUS, SCOPES `{rangees:{text,states}, actives, archivees}`.
- Calcul : roundHalfAway(value, digits=0), gramsPerMetre(density, diameter), grossBelowTare(grossG, tareG), netOfGross(grossG, tareG), percentOf(netG, initialG), netOfPercent(percent, initialG), lengthOf(netG, gpm), netOfLength(metres, gpm), gramsOfMm(mm, gpm), shown(netG, initialG, gpm).
- Textes et nombres : colourKey(text), fold(text), searchKey(text), suggestCrealityId(manufacturer, material, name, materials), parseNumber(text) (null si vide, NaN si faux).
- Reste : remainingFrom(field, text, context{tare, initial, gpm}) rend `{values:{gross, net, percent, metres}, basis | null, error}` ; remainingFields(remaining).
- Libellés : slotStatus(view) rend `{text, tone}`, idLabel(ident), ficheName(fiche), ficheLine(fiche), emptySpoolName(record), emptySpoolLine(record), remainingText(remaining), nearlyEmpty(remaining), whereText(spool), impactText(impact), planText(plan, materials).
- Base matériau : materialRecord(materials, ident) (ident = id à 5 chiffres sans le 0 de tête), materialsOfType(materials, type), materialTypes(materials) ; `materials` peut être un dict ou un tableau.
- Stock : units(views), filterStock(spools, fiches, filter), stockFacets(spools, fiches, scope) rend `{materials, colours:[{key, name}], places}`, candidateSpools(view, spools), placeableSpools(spools, fiches), usersOf(spools, key, value) (rend des libellés).
- Catalogue et journal : searchTares(entries, query, limit=30) (requête vide : les 30 premières), tareLines(entry), journalText(entry, names{spools, filaments, empty}), journalTone(entry), touches(entry, ident).

### Imports (retirer à la fin ce qui ne sert pas)

- De `logic.js` : colourName, figure, gramsLabel, isLight, normaliseHex, shortName.
- De `spools-logic.js` : NAME_LIMIT, NOTES_LIMIT, OUTCOME_LABELS, SCOPES, SPOOL_MATERIALS, TARE_SOURCE_LABELS, WRITE_RESULTS, candidateSpools, colourKey, emptySpoolLine, emptySpoolName, ficheLine, ficheName, filterStock, gramsOfMm, gramsPerMetre, idLabel, impactText, journalText, journalTone, materialRecord, materialTypes, materialsOfType, nearlyEmpty, parseNumber, placeableSpools, planText, remainingFields, remainingFrom, remainingText, searchTares, slotStatus, stockFacets, suggestCrealityId, tareLines, touches, units, usersOf, whereText.

### Constantes

```js
const API = "/machine/k1_control/spools/";
const TARES = new URL("./tares.json", import.meta.url).href;
const TICK_MS = 1000, OPEN_MS = 5000, CLOSED_MS = 30000, JOURNAL_MS = 30000, JOURNAL_LIMIT = 200, MATERIALS_RETRY_MS = 30000;
const TIMEOUTS = { status: 8000, materials: 8000, journal: 8000, action: 15000, write: 65000, export: 20000, import: 20000, tares: 15000 };
const UNSURE = [0, 502, 504];
const CHANGED = /a changé entre-temps/;
const CHANGED_TEXT = "La bibliothèque a changé entre-temps : vérifie puis refais l'action.";
const EXPORT_FORMAT = "kctrl_spools.export";
const TABS = [["cfs", "CFS"], ["stock", "Stock"], ["vides", "Bobines vides"], ["journal", "Journal"]];
const BARS = ["header.v-app-bar", "header.topbar", ".v-app-bar"];
const CONTROLS = "button, a[href], [role=button], .v-btn";
const TITLES = ".v-toolbar__title, h1, h2";
const START_OPEN = ["choice", "ending", "launched"];
const LINKED = [["gross", "Poids brut (g)", "pesé avec la bobine"], ["net", "Net (g)", "filament seul"], ["percent", "Pourcentage", "du net neuf"], ["metres", "Longueur (m)", ""]];
const FIELD_LABELS = { initial_net_g: "Net neuf", tare_g: "Tare", nominal_net_g: "Net nominal", diameter_mm: "Diamètre", density: "Densité", low_g: "Seuil bobine basse", cut_loss_mm: "Perte à la coupe" };
const SECTIONS = { slot: ["slot"], spool: ["remaining", "identity", "where", "end"], "new-spool": ["fiche", "spool", "rest", "where", "create"], fiche: ["fiche"], empty: ["empty"], settings: ["settings", "backup"] };
const BOOLEAN_PROPS = ["checked", "selected", "disabled", "hidden", "multiple", "readOnly"];
const ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor">'
  + '<circle cx="12" cy="12" r="9.5" stroke-width="1.6"/><circle cx="12" cy="12" r="6" stroke-width="4" opacity=".45"/>'
  + '<circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></svg>';
```

### Aides de module

- `failure(message, status)` : une Error qui porte `.status`.
- `cleanError`, recopié tel quel de `bobines.js` (avec `swatch`, plus bas).
- `metres(mm)` : null, "" ou non fini donne "? m", sinon `figure(mm/1000)+" m"`.
- `grams(v)` : null, "" ou non fini donne "? g", sinon `gramsLabel(v)+" g"`.
- `capital(t)` ; `sentence(t)` = capital(trim), plus « . » sauf fin en `.!?…`.
- `plural(n, one, many)`.
- `joinFr` donne « A, B et C » ; `usersText(labels)` : plus de 4 libellés donne « 3 premiers et N autres », sinon joinFr.
- `isoDay(ms)` donne AAAA-MM-JJ.
- `dateLabel(sec)` : fr-FR {day numeric, month short, hour, minute} ; "" si sec ≤ 0 ou non fini ; repli ISO dans un catch. `dayLabel(sec)` : jour, mois court, année.
- `signed(g)` = (g > 0 ? "+" : "") + gramsLabel(g) + " g".

À recopier tels quels de `bobines.js` :

```js
  function swatch(hex, extra) {
    const value = normaliseHex(hex);
    const classes = ["swatch"];
    if (extra) classes.push(extra);
    if (!value) classes.push("is-none");
    else if (isLight(value)) classes.push("is-light");
    return h("span", {
      class: classes.join(" "),
      style: value ? "background:#" + value : "",
      title: value ? colourName(value) + " #" + value : "sans couleur",
      "aria-hidden": "true",
    });
  }
  function cleanError(text) {
    const found = /'message':\s*'((?:[^'\\]|\\.)*)'/.exec(text) || /"message":\s*"((?:[^"\\]|\\.)*)"/.exec(text);
    let message = found ? found[1] : text;
    message = message.replace(/^Error:\s*/i, "").replace(/\\n/g, " ").trim();
    return message || "erreur inconnue";
  }
```

(`swatch` appelle `h`, donc il vit dans `mountManager` ; `cleanError` au niveau du module.)

### `start()` (exportée)

```js
export function start() {
  if (typeof document === "undefined" || document.getElementById("kctrl-spools")) return null;
  const host = document.createElement("div");
  host.id = "kctrl-spools";
  // Hidden until its styles are in: no unstyled button over Mainsail's bar.
  host.hidden = true;
  const shadow = host.attachShadow({ mode: "open" });
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = new URL("./styles.css", import.meta.url).href;
  let api = null;
  stylesheet.addEventListener("load", () => { host.hidden = false; if (api) api.place(); });
  stylesheet.addEventListener("error", () => console.warn("K1 Control: styles des bobines introuvables"));
  shadow.append(stylesheet);
  document.body.append(host);
  api = mountManager(shadow, { host });
  return api;
}
```

### `export function mountManager(root, options)`

Mise en place :

- `settings = options || {}` ; `host = settings.host || root.host || null`.
- `clock = settings.now || (() => Date.now())` ; `ask = settings.confirm || ((t) => window.confirm(t))`.
- L'objet `app`, déclaré avant tout appel de `h()` :

```js
{ status:null, installed:true, seen:false, online:false, error:"", reading:null, statusAt:0, statusEpoch:0,
  materials:null, materialsCount:-1, materialsError:"", materialsLoading:false, materialsAt:0,
  tares:null, taresError:"", taresLoading:false, tareQuery:"",
  journal:null, journalRevision:-1, journalKey:"", journalAt:0, journalError:"", journalLoading:false,
  open:false, tab:"cfs", sheet:null, busy:"", form:"compact",
  filters:{scope:"rangees",text:"",material:"",colour:"",place:""}, journalFilter:"", showFiches:false,
  choices:{}, signature:"", toastTimer:0, fullWidth:0, placed:"", refs:{}, resetScroll:false }
```

`h()` et `fill()` :

```js
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    let value = null;
    for (const [key, item] of Object.entries(attrs || {})) {
      if (item == null || item === false) continue;
      if (key === "class") node.className = item;
      else if (key === "style") node.style.cssText = item;
      else if (key === "ref") { app.refs[item] = node; node.dataset.ref = item; }
      else if (key === "dataset") Object.assign(node.dataset, item);
      else if (key === "value") value = item;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), item);
      else if (BOOLEAN_PROPS.includes(key)) node[key] = Boolean(item);
      else node.setAttribute(key, String(item));
    }
    for (const child of children.flat(Infinity)) {
      if (child == null || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    // After the children: a select only takes the value of an option it holds.
    if (value !== null) node.value = String(value);
    return node;
  }
  function fill(node, ...items) { node.replaceChildren(...items.flat(Infinity).filter((i) => i != null && i !== false)); }
```

Éléments :

- `badge` = span.spools-badge (hidden) ; `icon` = span.spools-icon (aria-hidden), innerHTML ICON.
- `launch` = `button.spools-launch` : type button, aria-haspopup dialog, aria-expanded "false", aria-controls spools-panel, hidden ; onclick `app.open ? close(true) : open()` ; contient icon, span.spools-label « Bobines » et badge.
- head = header.spools-head ; banners = div.spools-banners ; tabs = nav.spools-tabs (role tablist, aria-label « Vues des bobines ») ; body = div.spools-body.
- `panel` = `div.spools.spools-panel#spools-panel` (role dialog, aria-labelledby spools-title, tabindex "-1", hidden) avec head, banners, tabs, body.
- `toastBox` = div.toast.is-spools (role status, hidden).
- Puis `root.append(launch, panel, toastBox)`.

Écouteurs (tous retirés par `stop()`) :

- keydown Escape, fenêtre ouverte : ignoré quand `document.getElementById("kctrl-bobines")?.dataset.mode` est dans START_OPEN ; sinon close(true).
- pointerdown (capture), fenêtre ouverte : `path = event.composedPath?.() || []` ; rester ouvert si le chemin contient host (ou panel ou launch sans host) ; sinon close(false).
- visibilitychange lance tick ; resize de window lance schedulePlace.
- `watch(bar)` : rien si bar === watched ; débrancher l'ancien observateur ; si MutationObserver existe, observer la barre avec {childList, subtree, characterData, attributes, attributeFilter:["style","class"]} et appeler schedulePlace.
- `schedulePlace` : un drapeau `placing`, regroupé par requestAnimationFrame, sinon setTimeout 0.

Cycle de vie :

- `open()` : rien si déjà ouverte ou pas installée ; ouvrir, montrer la fenêtre, aria-expanded "true", remettre placed et signature à vide ; place() ; render() ; focus du panel ({preventScroll:true}) dans un try ; refresh() ; loadMaterials() ; loadJournal(true) si l'onglet est Journal.
- `close(focusLaunch)` : seulement si ouverte ; cacher, aria-expanded "false", renderLaunch() ; focus du bouton (dans un try) si demandé ; la fiche ouverte est gardée.
- `tick()` : rien si document.hidden ; place() ; refresh() si `!app.reading && clock() - app.statusAt >= (app.open ? OPEN_MS : CLOSED_MS)` ; si ouverte sur Journal avec un journal chargé, pas en cours de lecture, et `clock() - journalAt >= JOURNAL_MS` : loadJournal(true).
- `stop()` : clearInterval, retirer les écouteurs, débrancher l'observateur, clearTimeout(toastTimer).
- Démarrage : `refresh(); const timer = setInterval(tick, settings.tickMs || TICK_MS); return { open, close, refresh, place, render, stop, state: app };`

`call()` :

```js
  async function call(method, path, body, timeout) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const limit = timeout || 8000;
    const timer = setTimeout(() => controller && controller.abort(), limit);
    let response;
    try {
      try {
        response = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined, signal: controller ? controller.signal : undefined, cache: "no-store" });
      } catch (error) {
        throw failure(controller && controller.signal.aborted ? "pas de réponse en " + Math.round(limit / 1000) + " s" : "K1 injoignable", 0);
      }
      let payload = null;
      try { payload = await response.json(); } catch (_) { payload = null; }
      if (!response.ok) {
        const message = payload && payload.error && payload.error.message ? String(payload.error.message) : "HTTP " + response.status;
        throw failure(cleanError(message), response.status);
      }
      // An answer that cannot be read leaves the outcome unknown, like no answer.
      if (payload == null) throw failure("réponse illisible", 0);
      return payload;
    } finally { clearTimeout(timer); }
  }
```

Lecture, fusion, règlement :

```js
  function refresh() { if (!app.reading) app.reading = read().finally(() => { app.reading = null; }); return app.reading; }
  async function reread() { try { await app.reading; } catch (_) {} return refresh(); }
  async function read() {
    const epoch = app.statusEpoch;
    try {
      const payload = await call("GET", API + "status", null, TIMEOUTS.status);
      if (app.statusEpoch === epoch) accept(payload.result, null);
      app.installed = true; app.online = true; app.error = "";
    } catch (error) {
      if (error.status === 404) { app.installed = false; app.status = null; app.seen = false; close(false); }
      else { app.online = false; app.error = error.message; }
    }
    app.statusAt = clock();
    render();
    if (app.open && app.status) {
      loadMaterials();
      if (app.tab === "journal" && app.status.revision !== app.journalRevision) loadJournal(true);
    }
  }
  function accept(result, ownSheet) {
    if (!result || !Array.isArray(result.slots) || !Array.isArray(result.spools)) throw failure("réponse illisible", 0);
    app.status = result; app.seen = true;
    let sheet = app.sheet;
    if (sheet && sheet !== ownSheet) {
      const before = sheet;
      while (sheet && !merge(sheet)) sheet = sheet.back;
      app.sheet = sheet;
      if (sheet !== before) toast("Ce que tu regardais a été supprimé entre-temps.");
    }
  }
  function merge(sheet) {
    const latest = app.status.revision;
    if (sheet.revision === latest || sheet.merged === latest) return true;
    if (!alive(sheet)) return false;
    sheet.merged = latest;
    if (sheet.creating) { sheet.revision = latest; sheet.version += 1; return true; }
    const fresh = draftOf(sheet.kind, sheet.key);
    let conflict = false;
    for (const [key, value] of Object.entries(fresh)) {
      if (!sheet.touched.has(key)) { sheet.draft[key] = value; sheet.base[key] = value; delete sheet.conflicts[key]; }
      else if (value === sheet.base[key]) delete sheet.conflicts[key];
      else { sheet.conflicts[key] = value; conflict = true; }
    }
    sheet.stale = conflict;
    if (!conflict) sheet.revision = latest;
    sheet.version += 1;
    return true;
  }
  function settle(sheet, keys) {
    const saved = new Set(keys || []);
    if (!sheet.creating) {
      const fresh = draftOf(sheet.kind, sheet.key);
      for (const [key, value] of Object.entries(fresh)) {
        if (saved.has(key) || !sheet.touched.has(key)) { sheet.draft[key] = value; sheet.touched.delete(key); delete sheet.conflicts[key]; }
        else if (value !== sheet.base[key]) sheet.conflicts[key] = value;
        sheet.base[key] = value;
      }
      if (saved.has("remaining")) sheet.typed = null;
    }
    sheet.revision = app.status.revision; sheet.merged = sheet.revision; sheet.stale = false; sheet.error = null; sheet.version += 1;
  }
  function rebase(sheet) {
    if (!sheet.creating) {
      const fresh = draftOf(sheet.kind, sheet.key);
      for (const [key, value] of Object.entries(fresh)) {
        if (!sheet.touched.has(key)) { sheet.draft[key] = value; delete sheet.conflicts[key]; }
        else if (key !== "remaining" && sheet.draft[key] === value) { sheet.touched.delete(key); delete sheet.conflicts[key]; }
        else if (value !== sheet.base[key]) sheet.conflicts[key] = value;
        sheet.base[key] = value;
      }
    }
    sheet.revision = app.status.revision; sheet.merged = sheet.revision; sheet.stale = false; sheet.version += 1;
  }
  function isDirty(sheet) {
    if (sheet.typed && String(sheet.typed.text).trim()) return true;
    if (sheet.creating) return sheet.touched.size > 0;
    for (const key of sheet.touched) if (key !== "remaining" && sheet.draft[key] !== sheet.base[key]) return true;
    return false;
  }
  function setDraft(sheet, key, value) {
    sheet.draft[key] = value;
    if (!sheet.creating && value === sheet.base[key]) sheet.touched.delete(key); else sheet.touched.add(key);
  }
```

- `alive(sheet)` : bobine, son id est dans status.spools ; fiche ou bobine vide avec une clé, la clé est dans filaments ou empty_spools ; sinon vrai.
- `draftOf(kind, key)`, avec `num(v, d)` = (v == null || v === "") ? "" : figure(v, d) :
  - spool : `{remaining: JSON.stringify(spool.remaining || null), filament || "", empty_spool || "", initial_net_g: num(, 2), notes || "", place || ""}` ;
  - fiche : `{manufacturer, name, material, colour: colourKey(colour || ""), diameter_mm: num(, 2), density: num(, 3), creality_id || "", notes || ""}` ;
  - empty : `{manufacturer, name, spool_material || "inconnue", tare_g: num(, 2), nominal_net_g: num(, 2), notes || ""}` ;
  - settings : `{low_g: num(, 1), cut_loss_mm: num(, 1)}` ;
  - autre cas, ou enregistrement absent : {}.
- `makeSheet(kind, key, extra)` : creating = kind === "new-spool" || ((fiche ou empty) && !key). draft = extra.draft s'il est donné ; nouvelle fiche `{manufacturer:"",name:"",material:"",colour:"",diameter_mm:"1,75",density:"",creality_id:"",notes:""}` ; nouvelle bobine vide `{manufacturer:"",name:"",spool_material:"inconnue",tare_g:"",nominal_net_g:"1000",notes:"",catalogue:"",catalogue_tare:"",weighed:false}` ; sinon draftOf. Rend `{kind, key: key || "", draft, base: {...draft}, touched: new Set(), typed: null, revision, merged, stale: false, error: null, conflicts: {}, version: 0, back: null, creating, picked: Boolean(key)}`.
- `openSheet(sheet, stacked)` : empilée, back = app.sheet ; sinon rien si leaveSheet() refuse ; poser app.sheet et resetScroll ; loadTares() pour une nouvelle bobine vide ; render().
- `goBack()` : si la fiche est modifiée, demander « Abandonner la saisie en cours ? » ; remonter au-delà des fiches qui ne fusionnent plus ; resetScroll, render.
- `leaveSheet()` : parcourt la chaîne ; une fiche modifiée pose la même question ; sinon vrai.

`send()` :

```js
  async function send(path, body, opts) {
    const options = opts || {};
    if (app.busy || !app.status) return null;
    const sheet = app.sheet;
    const section = options.section || "";
    if (sheet && sheet.stale) { rebase(sheet); sheet.error = { section, text: CHANGED_TEXT }; render(); return null; }
    const focus = rememberFocus();
    app.busy = options.busy || path;
    if (sheet) sheet.error = null;
    render();
    const revision = sheet ? sheet.revision : app.status.revision;
    try {
      const reply = await call("POST", API + path, Object.assign({}, body, { revision }), options.timeout || TIMEOUTS.action);
      const answer = reply && reply.result;
      if (!answer || !answer.status) throw failure("réponse illisible", 0);
      app.statusEpoch += 1;
      if (options.leave) { if (app.sheet === sheet) app.sheet = sheet ? sheet.back : null; accept(answer.status, null); }
      else { accept(answer.status, sheet); if (sheet) settle(sheet, options.keys); }
      app.online = true; app.error = ""; app.statusAt = clock();
      return { result: answer.result };
    } catch (error) {
      const message = error.message || "erreur inconnue";
      if (error.status === 409 && CHANGED.test(message)) {
        await reread();
        if (sheet && app.sheet === sheet) { rebase(sheet); sheet.error = { section, text: CHANGED_TEXT }; } else toast(CHANGED_TEXT);
      } else if (UNSURE.includes(error.status)) {
        report(options.unsure || capital(message) + " : la fenêtre se met à jour, vérifie avant de refaire l'action.", section, sheet);
        refresh();
      } else report(sentence(message), section, sheet);
      return null;
    } finally { app.busy = ""; render(); restoreFocus(focus); }
  }
```

- `report(text, section, sheet)` : si sheet === app.sheet, `sheet.error = {section, text}` et version++ ; sinon toast(text).
- `act(action, params, opts)` = `send("action", {action, params: clean(params)}, opts)` ; clean retire undefined et null, garde "".
- `rememberFocus()` : lit `root.activeElement` ; null si rien ou le bouton ; sinon `{ref, start, end}`, sélection lue dans un try.
- `restoreFocus(state)` : un nœud existant et actif trouvé par ref reçoit focus({preventScroll:true}) et setSelectionRange, dans un try ; sinon focus du panel.
- `fail(sheet, section, text)` : pose sheet.error, rerender, rend false. `rerender(sheet)` : version++ puis render().

Chargeurs :

- `loadMaterials` : seulement ouverte, pas déjà en cours et avec un status ; rien si chargée et `status.materials.count` inchangé ; rien après une erreur de moins de 30 s ; GET materials, tableau exigé ; pose materials, materialsCount, materialsError.
- `loadJournal(force)` : GET `journal?limit=200` ; pose journal et journalRevision ; `journalKey = len + ":" + JSON.stringify(entries[0] || null)`.
- `loadTares` : GET TARES (15 s) ; `entries` doit être un tableau, sinon « catalogue illisible ».

`render()` et placement :

- `render()` : renderLaunch() toujours ; fermée, remettre la signature à vide et s'arrêter. Signature = JSON de : tab ; la fiche en [kind, key, version, error, revision, stale, conflicts] ; busy ; statusKey(status) (counter réduit à {restored, refused, period: Boolean}) ; installed ; online ; error ; longueur et erreur de materials ; longueur, erreur et chargement de tares ; journalKey, journalError, journalRevision ; `{...filters, text: ""}` ; journalFilter ; showFiches ; choices. Même signature : renderLive() seulement. Sinon : garder le focus et le défilement (0 si resetScroll) ; refs = {} ; remplir head, banners, tabs, body ; rendre le défilement ; renderStockList() ; renderTareList() ; renderLive() ; restoreFocus. Taper ne déclenche jamais de render.
- `renderLaunch()` : hidden = !(installed && seen) ; le badge porte le nombre de points d'attention, caché à 0 ; classes is-compact, has-badge, is-open, is-offline ; title « K1 injoignable », ou attention.join("\n"), ou « Gestion des bobines » ; aria-label « Bobines, N point(s) à voir » ou « Bobines ».
- `place()` :
  1. rien si le bouton est caché ;
  2. mesurer fullWidth une fois, en forme complète ;
  3. `findBar()` : la première correspondance de BARS de hauteur 32 à 120, largeur > 0 et bas > 0 ; puis watch(bar) ;
  4. avec une barre : half = left + width/2 ; edge = min(right - 8, le left - 8 des contrôles de taille non nulle à gauche ≥ half) ; controlsStart = max(left + 8, le right + 8 des contrôles de la moitié gauche) ; titleStart = max(controlsStart, le right + 8 des titres de la moitié gauche) ; room = edge - titleStart ; middle = top + (height - 36)/2 ; forme complète si room ≥ (fullWidth || 120) ; sinon compacte si room ≥ 44 ou edge - controlsStart ≥ 44 (à middle, right = max(8, largeur de fenêtre - edge)) ; sinon compacte sous la barre (top = bottom + 8, right 16) ;
  5. sans barre : compacte à top 72, right 16 ;
  6. arrondir ; clé = form:top:right ; rien si inchangée ;
  7. sinon `launch.style.cssText = "top:Xpx;right:Ypx"` et `panel.style.cssText = "--spools-top:" + (top + 44) + "px;--spools-right:" + max(16, right) + "px"`.

### Rendu, textes exacts

En-tête :

- h2#spools-title « Bobines » ; p.spools-summary « N au CFS · N en stock · N à ranger » (parties non nulles seulement), ou « Aucune bobine pour l'instant », ou « Aucune bobine active ».
- Actions : la puce d'état, btn « Réglages » (ghost, nav, ouvre la fiche des réglages), btn « Fermer » (title « Fermer (Échap) »).
- Puce `span.status.is-<ton>` avec un point, par priorité : hors ligne avec erreur, offline « injoignable » ; pas de status, idle « lecture… » ; Klipper non connecté, offline « Klipper déconnecté » ; read_only, paused « lecture seule » ; impression, printing « impression en cours » ; sinon idle « à jour ». `klippy()` se replie sur {connected:false, cfs_ready:false, printing:false}.

Bandeaux (`p.spools-banner.is-<ton>`, role alert pour danger) :

- Hors ligne avec un status (danger) : « K1 injoignable » + (" : " + erreur, sauf si l'erreur est « K1 injoignable ») + « . Nouvelle tentative dans quelques secondes. »
- read_only (warn) : sentence(« Lecture seule : » + ro), plus « L'export reste possible, et l'import d'un export valide remplace la bibliothèque. » si le stockage n'est pas verrouillé.
- Impression (accent) : « Impression en cours : tout reste consultable, le stock et les pesées restent modifiables. Les écritures au CFS partiront à la fin de l'impression ; l'import attend. »
- Klipper non connecté (warn) : « Klipper non connecté : le CFS n'est pas lu, ses emplacements peuvent être anciens. »
- slots_error (danger) : sentence(slots_error).
- materials.error (warn) : « Base matériau de la K1 illisible : <e> : les nouvelles fiches attendent qu'elle se relise. »
- unsaved_writes (warn) : « Résultat d'écriture au CFS pas encore enregistré pour <joinFr> : nouvel essai automatique. »
- reports_waiting (warn) : « N rapport(s) d'impression en attente d'enregistrement : nouvel essai automatique. »
- counter.refused (warn) : « Décompte repris à zéro au démarrage : l'état enregistré n'était pas utilisable. »
- store.fallback (warn) : « Bibliothèque reprise depuis la copie de secours <source> : la copie principale était abîmée ou absente. »
- fresh avec damaged (danger) : « Aucune copie intacte de la bibliothèque : elle repart vide. »
- quarantined (faint) : « Copies abîmées mises de côté dans <q>. »

Onglets : `button.spools-tab(.is-active)`, role tab, aria-selected, ref
tab-<clé> ; l'onglet CFS porte `span.spools-count` avec le nombre de points
d'attention. `chooseTab(key)` : respecter leaveSheet ; fermer la fiche ;
resetScroll ; sur Journal, loadJournal(true).

États du corps : pas installée, « Gestion des bobines absente de la K1. » ;
pas de status, sentence(« K1 injoignable : e ») ou spinner « Lecture de la
bibliothèque… » ; fiche ouverte, renderSheet ; sinon l'onglet. Aides :
`pane(title, count, ...children)` = section.pane.spools-pane avec h3 ;
`box(...)` = pareil sans titre.

Onglet CFS :

1. Pane « Consommations à attribuer » (avec compte) : note « Filament compté sans bobine connue : choisis la bobine qui l'a fourni. » ; lignes metres(mm) + " en " + slot, puis reason · dateLabel(on) ; select `choices["segment:" + id]` avec « Choisir la bobine… » ; « Attribuer » lance assign_segment, toast « B-001 : X g comptés. » ; « Ignorer » demande « Ignorer cette consommation ? Elle ne sera comptée sur aucune bobine. », lance dismiss_segment, toast « Consommation ignorée. »
2. Pane « Les emplacements du CFS » : un seul `div.spool-grid` ; par unité, `p.unit-label` « CFS » + n puis ses cartes ; vide : « Aucune unité CFS lue. » ou « Klipper non connecté : CFS non lu. »
3. `slotCard` : `button.spool`, ref slot-<slot>, ouvre la fiche d'emplacement. Classes is-empty (vide, hors_ligne), is-unknown (inconnue), is-check (a_verifier, attendue). Dans l'ordre : badge « puce N % » ; slot-name ; grande pastille (couleur de la fiche, sinon couleur lue) ; mini pastille `spools-seen` si les deux couleurs diffèrent ; kind : la matière, ou « matériau inconnu », « hors ligne », « vide » ; « B-001 · fiche » et remainingText (épuisée is-warn, basse is-low) ; note d'état.
4. Pane « Décompte » avec div.spools-live, ref live.
5. Sans counting_verified : « Décompte pas encore vérifié par une pesée : pèse une bobine après une impression pour le confirmer. »

`renderLive` : « Impression en cours » + " : " + shortName(file), ou « Hors
impression » ; par bobine « T1A · B-001 : 3,2 m · 9,6 g » ou « bobine
inconnue » ; waiting_mm > 0 : « X m pas encore attribués à une bobine » ;
route null « Filament engagé : inconnu », "" « Aucun filament engagé », sinon
« Filament engagé : T1A » ; les notes de période ; rien compté : « Aucun
filament compté pour l'instant. »

Onglet Stock :

- Filtres : recherche (ref stock-text, placeholder « Chercher : marque, couleur, lieu, numéro… ») qui n'appelle que renderStockList ; selects portée (SCOPES), « toutes matières », « toutes couleurs », « tous lieux » (seulement s'il y a des lieux) ; changer de portée remet les autres filtres à zéro ; « Nouvelle bobine » (primary, nav).
- `renderStockList` (ref stock-list), textes vides : « Aucune bobine ne correspond. », « Aucune bobine terminée ou jetée. », « Aucune bobine active : « Nouvelle bobine » en crée une. », « Aucune bobine en stock : « Nouvelle bobine » en crée une. »
- Lignes `button.spools-row`, ref row-<id> : mini pastille, spoolLabel, sous-ligne ficheLine · whereText, spools-remain.
- `renderFiches` : bascule « ▸/▾ Fiches filament (N) » (aria-expanded) et « Nouvelle fiche » ; lignes avec les utilisateurs ou « inutilisée » ; vide « Aucune fiche : elles se créent avec la première bobine. »

Onglet Bobines vides : pane « Bobines vides » (compte), note « Le poids à
vide de chaque type de bobine : il retire la tare d'une pesée. », « Nouveau
type » ; lignes avec utilisateurs ou « inutilisée » ; vide « Aucun type de
bobine vide : « Nouveau type » en ajoute un, depuis le catalogue SpoolmanDB
ou à la main. »

Onglet Journal :

- « Dernières impressions » (5 dernières, la plus récente d'abord) : shortName · OUTCOME_LABELS · date ; « B-001 en T1A : X m · Y g » ; « B-001 (attribué après) : … » ; « Prévu par le G-code : X m · Y g » ; « N consommation(s) à attribuer » ; les notes ; vide « Aucune impression comptée pour l'instant. »
- « Journal » : select de filtre avec « toutes les bobines » ; « Journal illisible : e » ou spinner « Lecture du journal… » ; « Journal pas relu : e » ; « Rien au journal pour cette bobine. » ou « Journal vide. » ; `ol.spools-journal` de li.is-<ton> avec heure et journalText, filtré par touches().

Fiches (panneaux de détail) :

- Tête : « ‹ Retour » (ref sheet-back) et le titre : « Emplacement T1A », « B-001 · fiche », « Nouvelle bobine » (+ « en T1A »), « Fiche <nom> » ou « Nouvelle fiche filament », « Bobine vide <nom> » ou « Nouveau type de bobine vide », « Réglages et sauvegarde ».
- Bandeau de conflit : « Modifié entre-temps sur la K1 : vérifie les champs signalés avant d'enregistrer. »
- sectionError montre les erreurs dont la section est "" ou absente de SECTIONS[kind] (p.spools-error, role alert). conflictHint : « modifié entre-temps sur la K1 » + " : " + la valeur.

Fiche d'emplacement :

- Vue absente : « Emplacement T1A non lu : l'unité CFS ne répond pas. »
- Note d'état, puis comparaison en deux colonnes : « Le CFS montre » (« unité hors ligne », « aucune bobine », ou l'identité : marque et nom, « fiche Creality id » ou « bobine non identifiée » ; le type ; nom de couleur #hex ou « couleur illisible » ; « puce : N % ») et « La bibliothèque » (la bobine, ou « rien (écriture en attente) », ou « aucune bobine ici »).
- Dernière écriture pas ok : « Dernière écriture : WRITE_RESULTS · detail · date » (faint pour annulee).
- a_verifier : « Le CFS et la bibliothèque ne disent pas la même chose. Choisis qui a raison : » ; choix « Écrire dans le CFS : planText (impactText). » + writeButton ; choix « Garder ce que montre le CFS : la bibliothèque prend la matière et la couleur lues par le CFS. » + « Garder le CFS » (adopt_cfs, toast « T1A : la bibliothèque suit maintenant le CFS. ») ; « Ou c'est une autre bobine : » + placeRow ; « Retirer du CFS ».
- inconnue : « Le CFS voit une bobine que la bibliothèque ne connaît pas. » + lignes candidates « C'est elle » + placeRow.
- attendue : « La bibliothèque attend B-001 ici, mais le CFS ne voit pas de bobine. » + « Ouvrir la bobine » + « Retirer du CFS ».
- vide : « Emplacement vide. » + placeRow.
- en_attente_cfs : « Écriture au CFS en attente pour B-001 : <identText>. » + (en impression « Elle partira à la fin de l'impression. », sinon « Écrire maintenant ») + Ouvrir, Retirer.
- hors_ligne : « L'unité CFS N n'est pas connectée : rien à faire tant qu'elle ne répond pas. »
- ok : « Le CFS et la bibliothèque sont d'accord. » + Ouvrir + Retirer.
- `writeButton` : ref cfs-write ; désactivé si occupé, lecture seule ou Klipper non connecté ; en cours, spinner « Écriture au CFS… » ; libellé « Programmer l'écriture » en impression, sinon « Écrire dans le CFS ».
- `cfsWrite(slot)` : `send("cfs-write", {slot}, {busy: "cfs-write", timeout: TIMEOUTS.write, section: "slot", unsure: slot + " : pas de réponse, l'écriture a peut-être eu lieu ; la fenêtre se met à jour."})` ; queued : toast slot + " : " + detail + "." ; written : « T1A : écrit dans le CFS et relu. » ; sinon report du libellé WRITE_RESULTS · detail.
- `placeRow` : select `choices["slot:" + slot]` « Une bobine du stock… » + « Mettre ici », ou « Aucune bobine en stock à mettre ici. » ; toujours « Nouvelle bobine ici ».
- `putInCfs` : si l'emplacement attend une autre bobine, confirmer « T1A attend déjà B-002 : elle passera « à ranger ». Continuer ? » ; put_in_cfs (keys []) ; toast « B-001 mise en T1A. » ou « B-001 mise en T1A : à vérifier, ouvre l'emplacement pour écrire le CFS. »
- `removeFromCfs` : toast « B-001 retirée du CFS : à ranger. »

Fiche de bobine (absente : « Bobine introuvable. ») :

- En-tête : pastille, libellé, « ficheLine · whereText », le reste ; ligne de base « Pesée à X g brut le D, puis décompte des impressions. », « Estimée à X g net le D, … » ou « Neuve à X g net le D, … » ; « Dernière pesée : écart de +12 g avec le décompte. » ; « puce du CFS : N % ».
- « Ce qui reste » : note « Remplis un seul champ : les autres suivent. Un poids brut est une pesée, le reste une estimation. » ; quatre champs liés (ref rest-<clé>, LINKED) ; brut désactivé sans tare, indice « choisir la bobine vide pour peser » ou « tare : X g » ; aperçu (ref rest-preview) « Sera enregistré : pesée, X g brut, soit N g net. » ou « Sera enregistré : estimation, X g net. » ; « Enregistrer le reste » (sans saisie : « Remplis d'abord un des champs. ») lance set_remaining (keys ["remaining"]), toast « B-001 : reste enregistré, X g net. » ; « Bobine neuve » confirme « Repartir du net initial de X g ? Le décompte repart de zéro. », toast « B-001 : repartie neuve, X g net. »
- `typeRemaining` : pose sheet.typed et met à jour les autres champs et l'aperçu **sans render**.
- `restContext` : tare de la bobine vide enregistrée (nouvelle bobine : celle du brouillon), net initial (lu, sinon le nominal), gpm.
- « Fiche et bobine vide » : choix de la fiche + « Modifier la fiche » ou « Nouvelle fiche » (empilées) ; choix de la bobine vide avec « aucune (tare inconnue) », indice « sans elle, une pesée ne peut pas retirer la tare », « Nouveau type » ; Net neuf (g) ; Notes ; Enregistrer lance edit_spool avec les seules clés changées (empty_spool "" gardé), toast « B-001 : enregistrée. » ou « Rien n'a changé. »
- « Où elle est » : au CFS, « Au CFS en T1A. » + Retirer + « Voir l'emplacement » ; archivée, « Terminée/Jetée le D. » + « Remettre en stock » (toast « B-001 remise en stock. ») ; stock ou à ranger, « À ranger : sortie du CFS, pas encore rangée. » ou « En stock : lieu. », champ Lieu avec datalist#spools-places et placeholder « étagère, boîte, sac… », Ranger ou Déplacer lance store (keys ["place"]), toast « B-001 rangée : lieu. » ou « B-001 déplacée : lieu. », select « Emplacement du CFS » (« T1A · vide », « T1C · B-002 (sera remplacée) », « T1B · bobine non enregistrée ») + « Mettre au CFS » ; sans emplacement : « Aucun emplacement du CFS lu : Klipper ou les unités ne répondent pas. »
- « Fin de vie » : archivée, « Archivée : elle reste dans l'historique. » ; sinon « Terminée » (primary si nearlyEmpty) et « Jetée », après « Marquer B-001 terminée ? Elle sort du CFS et du stock ; « Remettre en stock » la fait revenir. », toast « B-001 terminée. » ou « B-001 jetée. » ; « Voir son historique » ouvre le Journal filtré sur cette bobine.

Nouvelle bobine :

- `newSpoolSheet(slot)` : pré-remplit depuis l'observation de l'emplacement (seenId = material.slice(1), la couleur, materialRecord) ; choisit une fiche qui correspond (même creality_id et même couleur) ; ignore la marque si elle répond à /generic|g[ée]n[ée]rique/i ; brouillon fiche_mode existing/new, fiche, manufacturer, name, material, colour, diameter_mm "1,75", density, creality_id, empty_spool, initial_net_g, rest_mode "neuve", state cfs/stock, slot, place, notes ; picked = Boolean(seenId).
- Sections : « Filament » (segmenté « Une fiche existante » / « Nouvelle fiche », puis le choix ou ficheFields) ; « Bobine vide » (type et « Net initial (g) », indice « vide : le net nominal de la bobine vide » ou « le filament seul, bobine neuve ») ; « Ce qui reste » (segmenté « Neuve » / « Entamée ») ; « Où elle va » (segmenté « Au CFS » / « En stock » / « À ranger » ; choix d'emplacement avec l'alerte « B-002 est attendue en T1C : elle passera « à ranger ». » ; le lieu) ; Notes ; « Créer la bobine ».
- `createSpool` : valider avant tout POST (« Choisir une fiche filament. », « Net initial : nombre attendu. », « Net initial manquant : le donner ou choisir la bobine vide. », « Bobine entamée : remplis un des champs du reste, ou choisis « Neuve ». », « Choisir l'emplacement du CFS. ») ; slot envoyé pour cfs seulement ; confirmer si l'emplacement attend une autre bobine ; nouvelle fiche : create_filament d'abord, et en cas de succès fiche_mode passe à existing avec le nouvel id ; puis create_spool (leave) ; toasts « B-007 créée en T1A. » (+ « : à vérifier, ouvre l'emplacement pour écrire le CFS »), « B-007 créée, en stock. », « B-007 créée, à ranger. »

`ficheFields` :

- Fabricant, Nom (placeholder « gamme, finition… »), les deux appellent suggest.
- Matière : select de materialTypes (onchange materialChanged), sinon champ « PLA, PETG… ».
- Couleur : colourRow avec un sélecteur type=color (ref f-colour-picker), un champ hex (ref f-colour, RRGGBB) et le nom (ref f-colour-name, « à choisir »).
- Diamètre (mm) ; Densité (g/cm³), indice « vide : celle de la fiche Creality ».
- « Fiche matériau Creality » : select ref f-creality_id de materialsOfType ; en choisir une pose picked ; indice « le CFS reconnaît la bobine par cette fiche » ; sans base : « Base matériau de la K1 pas encore lue. »
- `suggest` : rien si picked ; suggestCrealityId, puis valeur posée directement sur le select. `materialChanged` : efface un creality_id qui ne correspond plus et remet picked à faux.

`ficheParamsOf` : « Fabricant manquant. », « Matière manquante :
choisis-la. » (mise en majuscules), « Couleur : six chiffres hexadécimaux
attendus. », « Couleur manquante : choisis-la. » ; nombres par readNumbers ;
creality_id envoyé seulement s'il n'est pas vide ; notes seulement sur la
fiche filament elle-même.

`readNumbers(sheet, params, keys, numeric, section, required)` : rien si
inchangé ; vide et obligatoire : « <Libellé> : valeur attendue. » ; NaN :
« <Libellé> : nombre attendu. » (libellés de FIELD_LABELS).

Fiche filament (absente : « Fiche introuvable. ») : note « Utilisée par … :
un changement de matière ou de couleur les met « à vérifier » au CFS. » ;
« Créer la fiche » ou « Enregistrer » ; « Supprimer » si inutilisée (confirmer,
toast « Fiche supprimée. »). Après une création, la fiche d'en dessous reçoit
le nouvel id : « Fiche créée : clique « Enregistrer » pour la donner à
B-001. » ou « Fiche créée. » Après une modification, nommer les emplacements
devenus a_verifier : « T1A est maintenant à vérifier : ouvre-le pour écrire
le CFS. » ou « T1A et T2B sont maintenant à vérifier : ouvre-les pour écrire
le CFS. » ; sinon « Fiche enregistrée. »

Bobine vide (absente : « Bobine vide introuvable. ») :

- Pane catalogue « Depuis le catalogue SpoolmanDB » (création) : recherche ref tare-query, liste ref tare-list ; « Catalogue illisible : e. La saisie à la main reste possible. » ; spinner « Lecture du catalogue… » ; « N types de bobines connus : tape une marque pour chercher. » ; « Rien dans le catalogue : remplis le type à la main ci-dessous. » ; lignes « Maker · X g net · matière · tare Y g » avec « Choisir », ou « déjà ajoutée (V-00x) ».
- `pickTare` : remplit les champs, nom « Bobine <net> g <matière> », toast « Type rempli depuis le catalogue : vérifie puis « Ajouter ce type ». »
- Pane « Ou à la main » (création) ou « Le type » : Fabricant ; Nom (« Bobine 1 kg plastique… ») ; Matière de la bobine ; Tare (g), indice à la création « poids de la bobine vide », en modification « tare pesée sur ta balance : « Enregistrer comme pesée » ; sinon elle devient « saisie » » ; Net nominal (g), indice « le filament d'une bobine neuve » ; case « Je l'ai pesée moi-même » (création) ; Notes.
- Source : « Source : pesée le D. », « Source : catalogue SpoolmanDB. » ou « Source : saisie. » ; note « Utilisée par … : changer la tare recalcule leur reste. »
- Boutons « Ajouter ce type » ou « Enregistrer », « Enregistrer comme pesée » (weigh_empty_spool, toast « Tare pesée enregistrée. »), « Supprimer » (toast « Bobine vide supprimée. »).
- Source à la création : pesee si cochée ; spoolmandb (+ catalogue) si la tare est celle du catalogue ; sinon manuel.
- Toasts : « Type ajouté : clique « Enregistrer » pour le donner à B-001. », « Type ajouté. », « Tare changée : le reste de <utilisateurs> est recalculé. », « Bobine vide enregistrée. »

Réglages et sauvegarde :

- « Réglages » : « Seuil bobine basse (g) », indice « sous ce reste net, la bobine est signalée basse » ; « Perte à la coupe (mm) », indice « longueur coupée à chaque changement de filament, comptée sur la bobine dont elle vient (0 : ignorée) » ; toasts « Réglages enregistrés. » ou « Rien n'a changé. »
- « Sauvegarde » : note « L'export garde toute la bibliothèque et son journal dans un fichier ; l'import d'un export remplace la bibliothèque. »
  - « Exporter » : GET export, contrôle du format ; Blob nommé `bobines-AAAA-MM-JJ.json`, téléchargé par `<a download>` avec `link.href` ; révoquer l'URL après 30 s ; toast « Export enregistré : nom. » ; erreur « Export impossible : … ».
  - « Importer un export… » : champ fichier caché (ref import-file) ; mauvais fichier « Ce fichier n'est pas un export des bobines K1 Control. » ; confirmer « Remplacer toute la bibliothèque par cet export du <date> (N bobines, N fiches, N bobines vides) ? Les écritures au CFS en attente ne sont pas reprises. » ; send import (20 s) ; toast « Bibliothèque importée. »
  - Notes « L'import attend la fin de l'impression. » et « Stockage verrouillé : export et import attendent. »
- « À propos » (dl) : Version, Révision, Contenu, Base matériau, Copie lue (« aucune (bibliothèque neuve) »), Décompte (« repris au démarrage », « parti de zéro au démarrage » ou « démarré à zéro »).

### Aides génériques

- `field(text, control, {hint, conflict, extra, wide})` : `div.spools-field(.is-wide)` ; un contrôle natif est enveloppé dans `label.spools-field-label` + span.spools-label-text. **Jamais la classe `spools-label` pour un champ** : elle appartient au bouton.
- input ; numberInput (inputmode decimal, maxlength 12) ; textArea (rows 3, NOTES_LIMIT) ; choice (select ref f-<clé>, onchange setDraft + rerender) ; selectBox (une valeur courante absente est ajoutée comme option) ; segmented (aria-pressed, ref seg-<clé>-<valeur>).
- `btn(text, onClick, {primary, danger, ghost, disabled, ref, title, nav, busy})` : toujours `.btn.is-small` ; un bouton nav n'est désactivé que par opts.disabled ; les autres le sont si occupé ou lecture seule ; spinner quand busy correspond.
- Recherches : spoolById, ficheOf, emptyOf, slotView, ficheGpm, ficheOptionsList, emptyOptionsList, emptyHint, knownPlaces, placesList, spoolLabel = idLabel + " · " + ficheName.
- `toast(msg, ok)` : classes "toast is-spools" (+ is-ok) ; caché après 4 s (ok) ou 8 s.

## 6. CSS à ajouter à `styles.css`

`styles.css` fait 780 lignes ; ajouter après le dernier bloc
(`@media (prefers-reduced-motion: reduce)`) un bloc
`/* spool manager (spools.js) */`.

Existant à réutiliser : jetons sur `:root, :host` (thème sombre : --bg,
--panel, --panel-2, --line, --line-strong, --ink, --ink-soft, --ink-faint,
--accent / -soft, --ok / -soft, --warn / -soft, --danger / -soft, --radius
16px, --radius-sm 10px, --shadow, --mono) ; `[hidden]{display:none
!important}` ; `.status` avec `.dot` et is-idle, is-choice, is-printing,
is-paused, is-offline ; `.pane` avec `h3 .count` ; `.swatch` (is-light,
is-none, is-big 64, is-mini 20) ; `.note` (is-ok, is-warn, is-accent,
is-faint) ; `.spool-grid` (4 colonnes, 2 sous 560px) et `.unit-label`
(grid-column 1/-1) ; carte `.spool` (`.slot-name`, `.kind`, `.remain` is-low
/ is-warn, `.badge` ; is-empty en pointillé, opacité .6, curseur default ;
is-unknown bord warn, curseur not-allowed) ; `.btn` (sans couleur) avec
is-primary, is-danger, is-small, is-ghost ; `.empty` ; `.toast` (fixe, bas
24, **aspect erreur par défaut**, z 10) et `.toast.is-ok` ; `.spinner`. La
typographie est posée sur `.bobines` : **la fenêtre pose sa propre police et
sa couleur**.

À ajouter :

```css
:where(.spools, .spools-launch) :is(button, input, select, textarea) { font-family: inherit; color: inherit; }
:where(.spools) :is(h2, h3, h4, p, ul, ol, dl, dd) { margin: 0; }
:where(.spools) :is(ul, ol) { padding: 0; list-style: none; }
```

- `.spools-launch` : fixe à top 72 / right 16, z 6, inline-flex, gap 8, hauteur 36, rayon pilule, fond panel-2, bord line-strong ; police `600 14px/1 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` ; états hover, focus-visible, is-open (accent-soft), is-compact (largeur 36, libellé caché), is-offline (icône en danger) ; badge fond warn, texte #1a1206, 18 px, absolu à -4/-4 en compact.
- `.spools-panel` : fixe à `var(--spools-top,56px)` / `var(--spools-right,16px)`, z 2147482000, flex colonne ; largeur `min(760px, calc(100vw - 32px))` ; max-height `calc(100vh - var(--spools-top) - 16px)`, puis la même en dvh ; fond, bord, rayon, ombre ; police `14px/1.45 system-ui…`.
- Blocs : head ; banners (tons warn, danger, accent, faint) ; tabs (actif avec bord bas accent ; compte en pilule warn) ; body (overflow auto, overscroll contain, padding 16, grid gap 14) ; pane-head ; list ; rows (hover ; is-static) ; remain (tabular-nums ; is-low / is-warn).
- Cartes : `.spools .spool` 14px, largeur 100% ; is-empty et is-unknown : curseur pointer, opacité .75 ; is-check : bord warn ; card-id 12px ; pastille seen absolue à top 8 / right 8.
- Contrôles et formulaires : live ; filters ; search (flex 1 1 220px) ; champs (focus outline accent ; disabled .5 ; textarea verticale) ; toggle ; liste du journal (heure en mono) ; cartes d'impression ; sheet-head ; compare (2 colonnes) ; side ; ident ; choice (pointillé) ; actions, place, inline (flex wrap, align end) ; hero ; linked (4 colonnes) ; form (2 colonnes, case pleine largeur) ; field, label-text, hint, conflict (warn), error (danger-soft) ; ligne couleur, sélecteur 40×36, hex en mono 9ch ; segmenté et segment actif ; check ; tares (max-height 320, défilement) ; about (dl en grille).
- `.toast.is-spools` : z 2147482001, max-width min(560px, calc(100vw - 32px)).
- `@media (max-width:640px)` : fenêtre plein écran (top/right 0, 100vw, 100vh puis 100dvh, sans rayon ni bord) ; compare et form en 1 colonne ; linked en 2.
- `@media (prefers-reduced-motion: reduce)` : pas de transitions.

## 7. Tests d'interface à ajouter à `spools-logic.test.mjs`

En tête du fichier actuel :

```js
// node --test packages/k1-control-v1/spool-choice-gate-v1/spools-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as logic from "./www/bobines/spools-logic.js";
import { colourName } from "./www/bobines/logic.js";
const VECTORS = JSON.parse(readFileSync(new URL("../spool-manager-v1/calculator-vectors.json", import.meta.url), "utf8"));
const MODEL = readFileSync(new URL("../spool-manager-v1/kctrl_spools_model.py", import.meta.url), "utf8").replace(/"\s*\n\s*"/g, "");
const PLA = logic.gramsPerMetre(1.24, 1.75);
const CONTEXT = { tare: 180, initial: 1000, gpm: PLA };
```

Les tests ajoutés peuvent porter leur propre
`import { mountManager } from "./www/bobines/spools.js";` : les imports ES
sont remontés.

Faux DOM :

- FakeElement : textContent (le setter remplace les enfants), innerHTML, append (re-parente), replaceChildren, setAttribute (pose id), écouteurs ; `dispatch` avec composedPath et preventDefault ; click si actif ; focus ; getBoundingClientRect depuis `rect` ; attachShadow (host, activeElement) ; `all()` et `find()` pour les tests ; `globalThis.Node = FakeElement`.
- Faux document : getElementById("kctrl-bobines") rend `start` ; querySelectorAll("header.v-app-bar") rend [bar] ; le querySelectorAll de la barre rend `controls` ou `titles` ; `fire(type, event)`.
- window {innerWidth:1280, confirm} ; setInterval capture `dom.tick` ; setTimeout ne tourne jamais ; requestAnimationFrame synchrone ; pas de MutationObserver ; patcher seulement URL.createObjectURL et revokeObjectURL (ne jamais remplacer URL) ; rendre les globals après chaque test ; vider par `for (let i=0;i<10;i++) await new Promise((r)=>setImmediate(r));`.
- `fakeFetch(routes)` : retire le préfixe d'API et la requête, note les appels ; routes « MÉTHODE chemin » avec [status, payload] ou une fonction.

Fixture synthétique (jamais celle de la fenêtre de départ, jamais une adresse privée) :

- revision 3, connecté ;
- T1A ok, B001, "001001", FF0000, PLA ; T1B vide ; T1C a_verifier, B002, puce 80, plan "001001" 0000FF ; T1D inconnue, candidats ["B003"] ;
- attention : 2 lignes ;
- B001 avec remaining {net_g 800, shown {g 800, percent 80, m 268.3}, gross_g 1050} ; B002 au CFS ; B003 en stock, lieu « Étagère » ;
- F001 et F002 (1.24 / 1.75) ; V001 (tare 250, nominal 1000).

Tests prioritaires :

1. Le bouton reste caché jusqu'à la première réponse, puis montre le badge "2".
2. Un 404 le cache.
3. Un enregistrement des réglages poste `{action:"settings",params:{low_g:50},revision:3}` et prend la révision 4.
4. Un 409 « a changé entre-temps » relit le status, garde le brouillon et montre CHANGED_TEXT.
5. cfs-write poste `{slot:"T1C",revision:3}` ; une réponse en attente affiche le détail en toast.
6. Relevé : aucun page cachée ; 30 s fenêtre fermée ; 5 s ouverte.
7. Échap est ignoré en mode de départ "choice" et ferme en "hidden".
8. En impression, le bandeau s'affiche et l'import est désactivé ; en lecture seule sans verrou, l'import reste actif.
9. edit_spool garde `empty_spool:""` ; un « Net neuf » vidé donne « Net neuf : valeur attendue. » sans POST.
10. Une nouvelle bobine poste create_filament puis create_spool, sans slot pour le stock.
11. Placement : complet avec de la place, compact à l'étroit, rond en bas à droite quand la barre est pleine, 8 px au-dessus de la pastille de départ quand elle est affichée.

## 8. Lot I, seconde moitié : fait (4312d27)

Fait dans l'ordre prévu le 1er novembre. Écarts au plan : `overlay.js` charge `spools.js` juste après `document.body.append(host)`, dans un `import()` à part avec son `.catch` ; les tests de page vérifient en plus que chaque route de la fenêtre existe dans le composant avec la même méthode.

## 9. Après le lot I

- **Lot J, labo** : fait, section 12.
- **Lot K, paquet de pose** : fait (1165513, 15bb85b), `packages/k1-control-v1/spool-manager-install-v1/` et son `README.md`. Section `[kctrl_spools]`, bloc de la passerelle avec `proxy_read_timeout` pour `/machine/`, pages en 755/644, sans `__pycache__`, sauvegarde et retour arrière exacts, 125 tests. Relevé (`deploy.py survey`) et préflight verts sur la K1 au repos le 1er novembre à 19:33 et 19:34 : 12 fichiers, 16 fichiers épinglés, 49 fiches matériau lues, 95,8 Mo libres, rien écrit ; reçus dans `inventory/raw/20261101-spool-manager-install-v1/`, hors Git. Les préflights et retours arrière des cinq paquets qui épinglent les anciennes pages (`end-after-refill-install-disabled-v1`, `end-overlap-v2`, `end-rewind-confirm-v3`, `end-separated-v1`, `retained-start-v1`) se fermeront après la pose.
- **Pose** : après le point 6 de la file (fin V5, session purge), relire `VERROU-K1.md` (dossier de notes partagé des sessions, hors dépôt) et prendre le verrou. Refaire `python packages/k1-control-v1/spool-manager-install-v1/deploy.py survey` : si la fin V5 a changé une page ou un fichier épinglé, recopier les empreintes dans `SURVEY` et `PAGES_BEFORE` de `build_manifest.py`, reconstruire le manifeste et relancer les 125 tests. Puis `preflight`, repos revérifié juste avant, Thomas présent, `install` puis `validate` ; se retirer du verrou et prévenir les sessions. Seul le Moonraker dédié redémarre.
- **Lot L** : qualification avec Thomas dans le vrai Mainsail (ouvrir, éditer, peser, écrire au CFS au repos, une impression comptée).
- **Clôture** : synchro avec `main`, mise à jour de `STATE`, `HANDOFF` et des autres fichiers de pilotage (ce dossier y est fondu puis supprimé), PR #95 sortie du brouillon, CI verte, merge, suppression des branches distantes `feat/spool-manager-v1` et `claude/spool-manager-ui-1471c8`.

## 10. CI locale

```
python -m pytest -q $IGN --deselect "tests/test_job_lifecycle_offline_v1.py::JobLifecycleOfflineV1Tests::test_all_canonical_scenarios_are_implemented_once" --deselect "tests/test_cfs_direct_owner_offline_v1.py::test_unload_requires_head_sensor_to_clear" -p no:cacheprovider
```

`$IGN` = `--ignore=tests/<nom>.py` pour : test_best_current_mesh_restore_v1,
test_cfs_cutter_purge_integrated_r2_offline_v1,
test_cfs_owner_exclusion_guard_live_effect_v1,
test_cfs_owner_exclusion_guard_live_read_only_v1,
test_cfs_owner_observability_live_read_only_v2,
test_cfs_s12_owner_preflight_v1,
test_cfs_stock_derived_cycle_owner_install_disabled_v1,
test_cfs_stock_unload_guard_adapter_live_read_only_v1,
test_cfs_stock_unload_guard_live_preflight_v1,
test_k1_control_clean_motion_v1, test_k1_control_robust_mesh_activation_v1,
test_k1_read_only_qualification_v1, test_long_checkpoint_job_v1,
test_start_sequence_owner_physical_keep_correct_t1a_v1,
test_start_sequence_owner_safety_r2,
test_z_thermal_stabilization_diagnostic_v1.

Node : `node --test packages/k1-control-v1/spool-choice-gate-v1/logic.test.mjs`
et `node --test packages/k1-control-v1/spool-choice-gate-v1/spools-logic.test.mjs`.

## 11. Pièges connus

- Poste Windows : Python 3.10.6, node 22. Toujours se placer à la racine du worktree ; vérifier zéro CR (`grep -c $'\r'`) dans chaque fichier écrit ; pytest avec un seul `-q`.
- Git : `git add --` un nouveau fichier avant `git commit --only` ; jamais `git add -A` ni `git add .` ; avant chaque commit, diff relu, `git diff --cached --check` et recherche de secrets dans le delta (adresse IP, jeton, mot de passe).
- Pages : aucun `http://` ou `https://` dans le JS, un SVG sans `xmlns`, aucun `href="` ni `src="` littéral.
- Copies gelées : `tests/test_cfs_end_install_package_v1.py::test_frozen_payloads_and_additive_include` refuse toute dérive d'un fichier épinglé (`build_package.py`, « payload drift »). Le paquet `end-after-refill-install-disabled-v1` lit désormais `frozen/www/bobines/` pour `bobines.js`, `logic.js` et `overlay.js` (5c41acf). Si un autre test casse après le changement d'`overlay.js` ou de `styles.css`, geler l'ancienne copie et pointer le manifeste dessus de la même façon.
- `figure(null)` rend "0" : passer par `metres()` et `grams()` pour les valeurs absentes.
- Un nombre "" ou None vaut « inchangé » côté modèle : le client refuse lui-même un nombre obligatoire vidé.
- La classe `spools-label` est réservée au libellé du bouton.
- Relevé du 1er novembre : `www/bobines/package.json` n'est pas sur la K1, donc jamais épinglé ; `klippy_connection.py` est sous `components/` dans le Moonraker v0.9.3 ; `moonraker.conf` est en 600, mode gardé ; la passerelle en service est exactement le `nginx.conf` de `gateway-private-lan-no-auth-v1`, ce que vérifie le test du manifeste.
- `deploy.py` refuse localement, sans rien envoyer, un `remote_install.py` dont l'empreinte diffère du manifeste : reconstruire le manifeste après chaque changement de l'installateur.

## 12. Lot J : fait (1er novembre)

- Labo `lab/lab_server.py` : le vrai composant `kctrl_spools` sur un faux Moonraker, K1 au repos, deux CFS en ligne, base matériau synthétique, 200 bobines entre CFS, stock et archives ; écoute sur 127.0.0.1 seulement. Une impression jouée de 1000 mm décompte 3,03 g sur la bonne bobine. Mémoire mesurée sur le PC à 200 bobines : 425 Kio gardés, 574 Kio au pic d'un export (`test_spools_lab_v1.py`), à remesurer sur la K1 à la pose.
- `--mainsail` relaie le vrai Mainsail en lecture seule (adresse dans `K1_GATEWAY`, jamais dans le dépôt) ; les routes `/machine/k1_control/spools/` restent servies par le labo et aucune écriture ne part vers la K1.
- Rendu vérifié sur la vraie barre à 1920, 1280, 768 px (bouton dans la barre, couche 9, élément du dessus à son centre), à 1024 px avec la sauvegarde de configuration en attente et à 375 px (bouton rond en bas à droite). Fenêtre ouverte : pleine page sur téléphone sans défilement horizontal, 760 px alignés sur le bouton au bureau. Relevé : une seule instance, 5 s fenêtre ouverte. Dans le labo à 375 px, barre pleine : le bouton rond passe 8 px au-dessus de la pastille de départ, sans la chevaucher.
- Zéro erreur console venant du module. Deux erreurs de Mainsail vues à travers le relais, non vérifiées sur le port 4409 : enregistrement du service worker et `net::ERR_NO_BUFFER_SPACE` sur le flux caméra.
- Corrigé en route : onglets écrasés par une longue liste et largeur téléphone (e6b2db9) ; bouton dessiné sous la vraie barre, couche 8 (bc8cab8) ; bouton rond sous la pastille de départ (15fe072) ; pastille collée au bord gauche sur téléphone (701fbb3).
- Limite connue : sur téléphone, le bouton rond peut couvrir le bord d'une carte (« +0.05 » de l'offset Z, page en haut) ; un défilement le dégage.
- Captures envoyées à Thomas : bureau, téléphone, bouton rond, bouton au-dessus de la pastille.
