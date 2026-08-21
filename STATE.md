# STATE

Last updated: 2026-08-22

## Current phase

**P4 — fondation V3 + PATHS-V1 retenue ; runtime Z/mesh installé et validé ;
état vide prêt pour calibration mais production volontairement bloquée**

The repository baseline, stock acquisition, complete Orca/G-code intake and
passive P1–P5/PETG trace are complete. Gate G3 is passed for offline design and
simulation only. No printer-behaviour deployment is authorised. The separate
`G4-SSH-KEY` access change and the observation-only V3 control foundation are
the deployed printer-side changes; neither changed print behaviour.

Thomas rejected `G4-ZSAFE-START-V1` before deployment. Its fixed `+0.27 mm`,
single `default` mesh and manual clean flow are not a production solution. The
remaining files are historical, marked `rejected_never_deploy`, and fail closed
if loaded accidentally.

The active target is `K1-CONTROL-V1`: one coherent, parameterised product with
a simple daily interface, a Mainsail expert view candidate, persistent accepted
Z calibration, meshes by plate/temperature, safe configurable start/clean/purge,
dynamic two-CFS temperature ownership and one versioned Orca contract. It is
being prepared by reversible slices. The complete offline prototype is now
green. V1 was authorised but stopped before mutation because the required
`logrotate` was absent. V2 reused the bounded stock syslog and reached a working
Mainsail through an SSH tunnel, then was rolled back because Mainsail `v2.18.2`
cannot satisfy the required Moonraker-account gate. V3 moves authentication to
nginx and changes no print behaviour. Les GO V3 exacts renouvelés ont permis de
corriger, avec rollback complet entre les KO, le transport stdin, les droits du
fichier et du dossier parent, puis la transition nginx de la boucle locale vers
le LAN. La capture finale `20260821-015722-g4-control-foundation-v3` est verte :
Moonraker reste sur `127.0.0.1:7125`, Mainsail authentifié écoute sur
`0.0.0.0:4409`, le compte a été vérifié par Thomas, les services Creality sont
intacts, Klipper est `standby`, les chauffes sont à zéro et les deux CFS `1.1.3`
sont connectés. Après ouverture du vrai tableau de bord, deux avertissements ont
prouvé que les racines `config` et `gcodes` dérivées du data path Moonraker sont
distinctes des chemins Creality actifs. La connexion fonctionne, mais
l'intégration du gestionnaire de fichiers reste incomplète. Une inspection
distante bornée et sans mutation a confirmé les deux dossiers Moonraker vides.
Le candidat séparé `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` a reçu son GO exact
renouvelé après revue et a été déployé sous la capture
`20260821-111001-g4-control-foundation-v3-paths-v1`. Les deux racines Moonraker
pointent maintenant vers les chemins Creality actifs, `config` est en lecture
seule via l'API et `gcodes` reste en lecture/écriture. Une validation indépendante
a confirmé l'absence d'avertissement, toute la pile verte et aucun changement du
comportement d'impression. L'acceptation durable et ses huit heures d'observation
commencent sur cet état final retenu.

## Confirmed facts

- Passive session `20260820-154056-p123` captured P1, P2, P3, P4, two P5
  attempts and one P1 PETG run. All jobs finished; the trace ended with nozzle
  and bed targets at zero.
- P4 proved that the `+0.27 mm` post-processor correction appears only after
  `START_PRINT`; startup purge and other earlier low operations remain
  unprotected.
- Live Z changes invoke `Z_OFFSET_APPLY_PROBE`, but the end-of-print path applies
  the exact inverse and prepares `0.000` for persistence. The current workflow
  therefore erases the correction it appeared to save.
- P1 PETG required a final visible correction of `+0.38 mm`, `+0.11 mm` above
  the file baseline, after briefly reaching `+0.40 mm`.
- P2 and P3 have the same 639 recorded settings and showed no reported physical
  difference despite separate versus assembled objects. One `+0.010 mm` live Z
  click occurred during P3, so the pair is not entirely untouched; it provides
  no evidence that object count alone explains the historical shifts.
- The second corrected P5 completed without a pause and followed nozzle targets
  `115 -> 220 -> 205 -> 220 -> 0 °C`. The first `220 °C` confirms the startup
  override; the second equals the requested target and cannot prove ownership.
- Every file still receives stock PA `0.044` during startup before its own PA
  becomes active roughly three minutes later.

- The accepted design route is a strengthened stock stack before BTT Eddy or a
  full firmware replacement. It now means one coherent control product, not a
  fixed Z patch followed by unrelated settings. This authorises offline design,
  not deployment.
- The accepted Z rule is explicit: live changes belong to a calibration session;
  only `Enregistrer` creates the persistent record. It survives print end and
  reboot, but a new reference calibration invalidates it.
- Moonraker MIPS is pinned to embedded commit
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea`; Mainsail is pinned to `v2.18.2`.
  Their archives, security policy and paths are fixed, but memory and
  coexistence with the screen and two CFS still require the named G4.
- A bounded read-only capacity snapshot found about 209 MiB total RAM, 118 MiB
  available, Python 3.8.2, 4.2 GiB free on `/usr/data`, no Moonraker process and
  no listener on its usual port. No remote mutation occurred.
- A private, Git-ignored intake exists under
  `inventory/raw/user-inputs/20260820-full-system-audit/` for Orca exports,
  existing projects, G-codes, custom scripts, photos and recovery artefacts.
- The first private Orca and test-suite intake is complete: 24 baseline files
  and 13 test-suite files were copied locally and verified by SHA-256 without
  changing their sources. Raw files and manifests remain ignored by Git.
- Six candidate G-codes are now available offline. P2 and P3 have the same 639
  recorded settings, duration, material estimate and two-layer geometry, while
  differing as five separate objects versus one assembled object. They form the
  cleanest current object-structure comparison.
- Ironing is enabled on P1, P2 and P3. Because it is shared and occurs at the
  top surface, it does not invalidate their first-layer comparison; top-surface
  defects must nevertheless remain separate from Z observations.
- The supplied `P5-CFS-ONE-CHANGE` is not a one-change file: it contains eleven
  tool commands and ten automatic changes between PLA targets of 205 and 220
  degrees. It is deferred until a replacement G-code proves exactly one change.
- Every supplied G-code still inserts the temporary `+0.27 mm` correction after
  `START_PRINT`, so none protects a purge or low move executed inside that
  stock macro.
- BTT Eddy is not currently mandatory. Its closest K1 Max `2.3.5.34` + CFS
  integration documents beta Z-offset behaviour, repeated recalibration and
  build-plate risk; it remains a measured fallback if deterministic PR Touch
  still fails.
- Codex has standing authority to manage the complete Git and GitHub lifecycle of this repository, including pull-request fusion into `main`, without another `GO`; printer mutations remain controlled separately by G4.
- Passwordless root SSH is active through the local alias `k1max-root`. The alias selects one dedicated ECDSA P-256 key, refuses password fallback and passed two independent final connections.
- The machine runs Dropbear `2019.78`; Ed25519 public-key authentication is unavailable in this version, so the working key is ECDSA P-256.
- Passive session `20260819-215124-long` completed automatically after a normal long production print returned to standby. Codex performed no printer-side mutation.
- The stock startup applied pressure advance `0.044`; the print file then restored `0.03` at the first layer. The active value remained `0.03` through the automatic CFS refill and to the end.
- The CFS detected runout, selected another slot it classified as equivalent PLA and resumed automatically in about 2 minutes 54 seconds.
- At startup, the CFS reported that it could not read the purge-speed data and then used its fixed `220 °C` purge temperature despite first-layer and normal print targets of `190 °C` and `195 °C`; the compiled implementation prevents proving the exact causal link between those two events.
- During that equivalent-material refill, the temperature sequence was `195 -> 140 -> 220 -> 195 -> 220 °C`. The resumed print stayed at `220 °C` until Thomas manually restored `190 °C` at `23:04`.
- Visible Z homing origin remained `+0.27 mm` for the whole session; no live Z correction was reported.
- After completion and return to standby, the stock runtime briefly requested `150 °C` before returning the nozzle target to zero.
- Thomas judged the finished part broadly correct, with rough/granular ironing areas provisionally attributed to OrcaSlicer settings rather than the observed CFS temperature ownership.

- Target machine: older-generation Creality K1 Max.
- Printer firmware: `2.3.5.34`, Buildroot 2020.02.1, Linux 4.4.94 on MIPS.
- The manufacturing identity partition reports board `CR4CU220812S12`, structure version `0`.
- The startup selector therefore loads the S12 structure-0 stock configuration; the active header and version match it.
- `/etc/ota_info` still reports `CR4CU220812S11`; this is now classified as inconsistent OTA metadata, not the active configuration identity.
- Classic K1 CFS upgrade installed.
- Two CFS units are in use.
- Both CFS units show firmware `1.1.3` on the printer UI; no machine version file has yet confirmed it.
- Active configuration entry point: `/usr/data/printer_data/config/printer.cfg`.
- `printer.cfg` includes `sensorless.cfg`, `gcode_macro.cfg`, `printer_params.cfg` and `box.cfg`.
- `START_PRINT` invokes the CFS, homing, nozzle-cleaning and levelling chains after slicer input.
- `box.cfg` sets `Tn_extrude_temp` to `220`.
- The CFS `BOX_*` implementation is delivered as a compiled `box_wrapper` module; only its small Python loader is readable.
- `CXSAVE_CONFIG`, the principal `CX_*` startup helpers, `G28` and the PR Touch probing path have been captured and mapped from readable Python sources.
- `G28` invokes the PR Touch Z routine, which uses five measurements, selects the median and applies `self_z_offset` when establishing the Z origin.
- The active saved Z offset is `0.000`; one historical snapshot contains `-0.025` before later snapshots return to zero.
- `/usr/data` is persistent ext4 storage; Klipper logs currently account for about 1.6 GiB.
- OrcaSlicer is the usual slicer; Creality Print remains available.
- The Z-offset or Z-reference problem existed before the yellow bed springs were installed.
- The springs improved bed levelling but changed nothing about the Z problem.
- CFS filament changes can override intended nozzle temperatures.
- Startup and calibration sequences can be excessively long and opaque.
- Earlier G-code post-processing successfully removed a redundant tool command and applied a temporary ironing offset, proving that some slicer-side workarounds are useful but insufficient against later firmware macro overrides.
- Session `20260819-185157-g3-aba` completed A1, B and A2 without reboot and without a fourth print.
- B and A2 each exposed multiple Z-establishing phases around nozzle cleaning; A2 reached retry index 7 and contained large internal outliers before converging near the `0.21–0.26` group.
- The stock runtime injected pressure advance `0.044` during B and A2 even though both private G-codes request `0.03` after `START_PRINT`; the final active value was not observable in this capture.
- Thomas changed bed-screw tension between the trials and again around A2. This may have improved the layer but makes the geometry comparison non-qualified.
- A1, B and A2 all completed with broadly usable physical results after manual tuning.

## Reported but not yet verified from the machine

- Exact CFS firmware source and per-unit hardware revision.
- Physical board marking; software selection is S12 structure 0, but physical confirmation remains desirable before firmware recovery.
- Exact Klipper commit/version.
- Recovery image compatibility with this exact machine revision.
- Whether a long print followed by a differently configured or multi-object file triggers the large historical Z shift reported by Thomas.

## Completed

- `G4-ZSAFE-START-V1`, ADR-003 and their former gate are explicitly rejected;
  the historical macro now fails closed if loaded by mistake.
- The durable product need and target behaviour are recorded in
  `docs/10-systeme-pilotage-perenne.md` and ADR-004.
- Mainsail, Moonraker, Creality K1 Series Annex, Creality Helper Script, its CFS
  fork, KAMP and the available calibration approaches were compared against the
  exact captured stack in `docs/11-compatibilite-interfaces-et-calibration.md`.
- A machine-readable `K1-CONTROL-V1` contract now forbids a universal fixed Z,
  requires explicit persistence/invalidation, keys meshes by plate/temperature,
  fixes dynamic temperature ownership and guards every production hazard.
- Offline contract tests were added before any printer-side implementation.
- A dependency-free `K1 Control` web prototype and pure Python Z/mesh/temperature
  state engine now run only on synthetic data under `prototype/`.
- Desktop and narrow-screen browser checks passed. Live adjustment, explicit
  commit, simulated restart persistence and reference-calibration invalidation
  behaved as intended with no JavaScript error.
- The screen now talks to a loopback-only fake Moonraker that applies the Python
  state rules instead of changing browser state directly.
- The executable offline matrix passes all 17 required Z, mesh, sequence,
  temperature, two-CFS, Orca and rollback scenarios.
- The full Orca start/end/tool-change contract and expanded fixtures are ready;
  the active Orca profile and legacy `+0.27 mm` post-processor are unchanged.
- A local bundle containing the three pinned Moonraker/nginx/Mainsail archives
  was built and verified. Binary payloads remain temporary and outside Git.
- V1 had exact paths, first-login tunnel, backup, checksums, no-motion
  validation, resource gates and rollback, but its missing target dependency
  invalidated the package before deployment. V2 preserves these controls.
- The real V1 preflight confirmed standby, zero heater targets, S12 structure
  0, firmware `2.3.5.34`, about 117 MiB available RAM, 340 KiB swap in use,
  stock ports, T1/T2 connected on `1.1.3`, and all V1 targets absent.
- The same preflight proved that neither `logrotate` nor `/etc/logrotate.d`
  exists. V1 performed no mutation and is closed.
- V2 uses the existing `/sbin/syslogd -n` through `/dev/log`; BusyBox reports
  its default 200 KiB limit and one rotated backup. No logging dependency is
  installed.
- The exact V2 GO was received. Real attempts exposed Buildroot transport,
  nginx path, permission, Moonraker provider, service-stop and WebSocket-origin
  gaps. The corrected stack loaded the real Mainsail dashboard through a tunnel.
- Mainsail `v2.18.2` has no Moonraker account workflow. V2 could not remove
  loopback trust and still keep Mainsail working, so every attempt was rolled
  back and V2 is closed.
- Final post-rollback checks found `/usr/data/k1-control-v1` and both project
  services absent, ports `7125`/`4409` closed, stock ports `80`/`8080`/`9999`
  listening and all named Creality processes present.
- Thomas selected nginx authentication. Offline inspection proved the pinned
  MIPS binary contains `auth_basic` and `auth_basic_user_file`. V3 uses a
  masked local prompt, one salted SSHA record, HTTP `401/200` checks, private
  IPv4 source limits and strips credentials before proxying to Moonraker.
- Les GO V3 exacts ont autorisé les reprises après rollback. Les écarts stdin,
  droits du fichier, traversée du dossier parent et transition nginx vers le
  LAN ont été corrigés avec tests de non-régression.
- La capture finale `20260821-015722-g4-control-foundation-v3` a installé la
  fondation, créé et vérifié le compte, ouvert le LAN et obtenu `VALIDATE_OK`.
  Moonraker reste en boucle locale, Mainsail authentifié écoute sur `4409`, les
  ports Creality sont présents et le vrai tableau de bord est fonctionnel.
- Après pose, environ 103 Mio de RAM restent disponibles et la croissance swap
  mesurée est de 36 Kio. Klipper est `standby`, les chauffes sont à zéro, les
  axes ne sont pas homés et les deux CFS `1.1.3` sont connectés.
- La capture `20260821-111001-g4-control-foundation-v3-paths-v1` a aligné les
  racines Moonraker sur les chemins Creality par deux liens, rendu `config`
  accessible seulement en lecture via l'API, conservé `gcodes=rw` et obtenu
  `VALIDATE_PATHS_V1_OK` sans transmettre de G-code. Les avertissements ont
  disparu et seule l'instance Moonraker dédiée a été redémarrée.
- L'observation finale a couvert l'impression normale lancée manuellement à
  12:48. Thomas a confirmé qualité correcte, un seul PLA et aucune intervention.
  Le trou du premier observateur local, de 15:07 à 18:43, a été couvert
  séparément par le journal Klipper persistant : aucun arrêt Klipper/MCU, aucune
  perte de communication, aucune trace Python et aucune erreur interne.
- Le second observateur a atteint sa durée à 20:31:56 et fermé avec `exit_code=0`.
  La validation finale en lecture seule a obtenu `VALIDATE_PATHS_V1_OK` avec les
  axes encore référencés après la calibration manuelle. Le validateur distingue
  désormais correctement une simple vérification de santé d'un préflight de pose.
- Les sources exactes `save_variables.py`, `gcode_macro.py`, `delayed_gcode.py`
  et `bed_mesh.py` ont été copiées en lecture seule dans une capture privée et
  vérifiées par SHA-256.
- Le candidat hors imprimante Z/mesh existe maintenant sous
  `packages/k1-control-v1/z-mesh-runtime-v1/`. Il fournit état Z courant/précédent,
  session provisoire, invalidation, préchauffe, homing guidé, matrices 3–25,
  choix Lagrange/bicubique, commit mesh explicite et garde de mouvements bas.
  Son stockage original utilise validation, SHA-256, `fsync`, remplacement
  atomique et copie précédente. Il ne remplace pas `START_PRINT`, ne contient
  ni CFS, ni extrusion, ni mouvement bas et n'est pas installé.
- Thomas a envoyé le GO exact `G4-K1-CONTROL-Z-MESH-RUNTIME-V1`. Le premier
  préflight a échoué sans mutation parce que deux appels Python avec arguments
  n'indiquaient pas la lecture sur stdin. Le déployeur ajoute maintenant `-`
  avant ces arguments et un test dédié verrouille ce transport.
- Le second préflight en lecture seule est vert sous la capture privée
  `20260821-212431-g4-k1-control-z-mesh-runtime-v1` : `standby`, chauffes à
  zéro, fondation intacte, empreinte initiale conforme, cibles runtime absentes
  et deux CFS `1.1.3` connectés. Aucune copie, sauvegarde distante, inclusion,
  commande Klipper ou relance de service n'a été exécutée.
- Le GO exact renouvelé a ouvert la capture
  `20260821-213732-g4-k1-control-z-mesh-runtime-v1`. Le préflight et le backup
  étaient verts, puis l'état neuf a échoué car `integrity=empty` laissait
  `ready=0`. La garde sans mouvement n'a pas été appelée.
- Le rollback a retiré le runtime mais sa première validation a rencontré T1 en
  reconnexion et une normalisation d'espaces des blocs générés de `printer.cfg`.
  Une complétion bornée a restauré le backup exact sans nouveau restart. Le
  préflight final est vert : runtime absent, hash initial restauré, `standby`,
  axes non homés, chauffes à zéro, T1/T2 `1.1.3` et fondation intacte.
- Le restart a effacé le mesh transitoire `Base`; le profil persistant `default`
  est redevenu actif. Aucun mouvement, chauffe, extrusion, ordre CFS,
  calibration, impression, firmware restart ou reboot n'a été exécuté.
- Le candidat hors imprimante traite maintenant `empty` comme prêt pour une
  calibration mais fermé à la production, attend jusqu'à 60 secondes la
  stabilisation des deux CFS et restaure le backup exact après le restart de
  rollback. Son nouveau hash config est
  `3b0e5215d9bd58a343c57a681668ef1e466465980cceac3b1fd5944fec806f96`.
- Un nouveau GO exact a ouvert la capture
  `20260821-224828-g4-k1-control-z-mesh-runtime-v1`. Préflight et backup étaient
  verts. Après pose, le runtime restait à `ready=0` parce que le parseur exact de
  Creality tronque `K1_CONTROL_LOAD_STATE` en commande `K1` inconnue.
- La source `gcode.py` capturée confirme le découpage
  `([A-Z_]+|[A-Z*/])` : tous les points d'entrée avec un chiffre au milieu sont
  incompatibles. Le candidat emploie désormais `KCTRL_*` pour le runtime, le
  stockage, l'adaptateur et les contrats Orca. Un test rejoue ce parseur exact.
- Le rollback a retiré le runtime, mais un `CXSAVE_CONFIG` Creality tardif a de
  nouveau normalisé seulement les espaces de `bed_mesh default` et `auto_addr`.
  Une complétion bornée a restauré le backup exact sans restart. Le préflight
  final est vert : runtime absent, hash initial, `default`, `standby`, axes non
  homés, chauffes à zéro, deux CFS `1.1.3` et fondation intacte.
- Le rollback offline attend maintenant la reconnexion CFS et une fenêtre
  silencieuse avant sa dernière restauration, puis revérifie l'empreinte après
  trois secondes. Les nouveaux hashes sont
  `1590b918dcdfe70e801c0be40fee4f19ab6b1e2dfa93936975b88aed5d4b1c79`
  pour la configuration et
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`
  pour le module. La suite locale passe `98/98`; la validation en mémoire sur
  le Python/Jinja exact de la K1 obtient
  `K1_EXACT_RUNTIME_OK templates=17 commands=18`.
- Thomas a renouvelé une troisième fois le GO exact. La capture
  `20260822-004338-g4-k1-control-z-mesh-runtime-v1` a confirmé le préflight et
  le backup, puis chargé les objets `KCTRL_*`. `KCTRL_LOAD_STATE` s'est bien
  exécuté, mais la première affectation texte a échoué : le `shlex` Creality
  transforme `VALUE='empty'` en nom nu `empty`, refusé par `ast.literal_eval`.
- Le rollback automatique renforcé a retiré le runtime, attendu les deux CFS et
  la fenêtre silencieuse, restauré le backup exact et revérifié son empreinte.
  Le préflight final confirme runtime absent, `default`, `standby`, axes non
  homés, chauffes à zéro, deux CFS `1.1.3` et fondation intacte. Aucun mouvement,
  homing, chauffe, extrusion, ordre CFS, calibration, impression, firmware
  restart ou reboot n'a eu lieu.
- Les 24 affectations texte utilisent désormais un littéral protégé comme
  `VALUE='"empty"'`. Le déployeur conserve aussi un snapshot avant rollback si
  `ready` reste à zéro. Le hash courant de la configuration est
  `dd7fa02a8b7b9bd46850c90cf2a85afa71ce27cfa263c120ef4e9cca6b48c113` ; celui
  du module reste
  `696eabec936bd81300acb4e6882d141c1a9ce2494df3bd1f686ff4ee8cbb8ede`.
  La suite exécute 99 tests : 98 passent et le contrôle Jinja local ignoré est
  couvert par `K1_EXACT_RUNTIME_OK templates=17 commands=18 string_values=24`
  sur l'environnement exact de la K1.
- Thomas a renouvelé le GO exact pour la capture
  `20260822-011022-g4-k1-control-z-mesh-runtime-v1`. Le préflight frais, le
  backup et la pose sont verts : `DEPLOY_Z_MESH_RUNTIME_V1_OK`.
- La garde `KCTRL_PRODUCTION_ASSERT_ARMED` a refusé l'état vide comme prévu et
  la comparaison avant/après confirme qu'aucune position, origine Z ou cible de
  chauffe n'a changé.
- Un `CXSAVE_CONFIG` différé a ensuite normalisé uniquement l'indentation des
  blocs générés `bed_mesh default` et `auto_addr`. Le diff complet ne contient
  aucun changement de valeur, section ou inclusion, et la comparaison
  normalisée obtient `PRINTER_CFG_NORMALIZED_EQUIVALENCE_OK`.
- Le validateur épingle l'empreinte immédiatement posée et l'unique empreinte
  normalisée observée, tout en exigeant toujours une inclusion et les hashes
  exacts des deux fichiers runtime. La validation indépendante obtient
  `VALIDATE_Z_MESH_RUNTIME_V1_OK`.
- État final retenu : `standby`, axes non homés, chauffes à zéro, `default`,
  deux CFS `1.1.3`, fondation intacte, `ready=1`, `integrity=empty`,
  `accepted_z_valid=0`, `block_reason=no_accepted_z` et `low_moves_armed=0`.
  Le runtime est installé mais ne peut pas encore armer un travail de production.
- La suite finale exécute 100 tests : 99 passent et le seul contrôle Jinja
  local ignoré reste couvert sur le Python/Jinja exact de la K1.

- Complete-system audit, A/B/C comparison, safety invariant, input contract and
  time-bounded roadmap documented in
  `docs/08-audit-systeme-complet-et-trajectoire.md`.
- ADR-002 proposes an analyser-first strengthened stock route and defines the
  later BTT Eddy decision gate.
- Private intake folders and exact deposition instructions created and verified
  as ignored by Git.
- Public repository created.
- Scope, strategy and safety boundary documented.
- Agent rules, gates, roadmap and acquisition protocol prepared.
- Public/private data separation defined.
- Notion project branch created separately as the long-form personal register.
- Gate G1 passed and target identity confirmed.
- Read-only acquisition `20260819-1627-k1max-stock` completed.
- Raw material retained under ignored local storage.
- Redacted manifest, service map, mount map, checksums, include graph, macro index and findings produced.
- Gate G2 passed with explicit limitations.
- Follow-up read-only acquisition `20260819-1726-k1max-targeted-sources` completed.
- S11/S12 runtime configuration identity resolved as S12 structure 0.
- Readable CX, persistence, homing and PR Touch sources mapped; compiled CFS boundary recorded.
- Comparable A1/B/A2 trace protocol completed with fixed conditions, Q1–Q5 qualification and a custom-installation decision matrix.
- Private session, event timeline and comparison templates added under `experiments/g3/`.
- Bounded execution prompt prepared and used; all physical actions were performed by Thomas.
- Private G3 files A/B compared locally: 637 slicer settings and all 34 non-motion control commands are identical.
- Both files apply Z protection `+0.27 mm` and pressure advance `0.03` after `START_PRINT`; B changes only the Y dimension from `200` to `201 mm` and the resulting movements.
- The stock bed check selects four near-corner points randomly, measures each three times and can regenerate and save the mesh when at least two corners exceed its tolerance.
- A1/B/A2 is now the selected first physical sequence; reboot and multi-filament CFS tests are deferred.
- A1/B/A2 session report and cleaned event summary produced. Q1 passed, Q2–Q4 did not pass and Q5 is inconclusive.
- `G4-SSH-KEY` prepared, approved, deployed and validated without any service restart.
- Final `/root/.ssh/authorized_keys` state: one active ECDSA key, root ownership, mode `600`, final recorded SHA-256 `eae61f0314dbcdfaa9a02a42352592e3b175a5d35a0d501cb909b365697eb6af`.
- Local SSH configuration was backed up before adding the tested `k1max-root` alias.
- Read-only production observer added and validated with a six-second subscription probe: one persistent Klipper connection, three state samples, no repeated query traffic and no socket-close errors inside the capture.
- Long production capture `20260819-215124-long` completed with 6,748 state records and an automatic observer shutdown after standby.
- Cleaned findings, event summary and sanitisation report produced for the long capture; raw evidence remains local and ignored.
- Final pressure advance ownership measured: startup `0.044`, then file-requested `0.03` active through the CFS refill and print end.
- Equivalent-PLA CFS refill temperature override measured and confirmed: stock resume returned to `220 °C` instead of preserving the prior print temperature.
- Exact live copies of `printer.cfg`, `gcode_macro.cfg` and `box.cfg` were
  retrieved read-only and matched their recorded SHA-256 hashes.
- The production G-code contains no `M104`/`M109` request for `220 °C`; the CFS
  module and its generic PLA database own that value.
- The static `G4-CFS-TEMP-PLA` candidate was rejected by Thomas before
  deployment because it hard-coded Geeetech PLA and `190/195 °C`.
- Its deployable patch, helper, OrcaSlicer contract, deployment procedure and
  dedicated test were removed from `main`; the rejected ADR remains as history.
- The accepted requirement is dynamic: G-code or Thomas owns the temperature
  during a print, equivalent refill preserves the active target, and intentional
  material changes receive the next tool's target from G-code.

## Next safe action

Préparer la gate séparée de première calibration : paramètres explicites de
plaque, température, matrice et interpolation, séquence chauffe/nettoyage/homing,
acceptation Z volontaire et critères de rollback. La calibration impliquera des
mouvements, de la chauffe et une écriture d'état ; elle exige donc une nouvelle
revue et un nouveau GO nommé. Le runtime déjà installé ne doit pas être reposé.

The Orca cutover remains a later atomic gate. This runtime slice intentionally
keeps the active Orca profile, `START_PRINT` and the legacy `+0.27 mm`
post-processor unchanged.

Thomas explicitly rejected further sacrificial print campaigns on 2026-08-21.
The V3 + PATHS-V1 observation remains useful coexistence evidence but no longer
blocks offline product construction. Codex still must not transmit G-code or
mutate the printer without the later exact named G4 approval.

Do not remove or disable the current Orca `+0.27 mm` post-processor. Its
retirement remains atomic with the later proven machine/Orca replacement.

## Not authorised yet

- Helper Script installation.
- `G4-K1-CONTROL-FOUNDATION-V1` forever: preflight KO, never deployed, name closed.
- `G4-K1-CONTROL-FOUNDATION-V2` forever: real attempts rolled back, name closed.
- Any reinstall, correction or extension of the completed
  `G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` package.
- Any other Mainsail, Fluidd, Moonraker or `K1 Control` installation/change.
- Toute nouvelle pose, correction ou suppression du runtime
  `G4-K1-CONTROL-Z-MESH-RUNTIME-V1` désormais installé.
- Toute commande de calibration Z/mesh, chauffe ou homing du runtime avant une
  gate séparée explicitement approuvée.
- BTT Eddy preparation, installation, firmware or calibration.
- Firmware downgrade or replacement.
- Any SSH write other than the completed `G4-SSH-KEY` deployment.
- Service restart or reboot initiated by an agent.
- Macro or configuration modification.
- Z, mesh, temperature or CFS tuning.
- Any static material-specific CFS temperature candidate.
- Any import or change of Orca fields on the workstation profile.
- `G4-ZSAFE-START-V1` forever: this rejected name cannot receive a GO.
- Any future `K1-CONTROL-V1` deployment until a new exact G4 package exists and
  receives its own explicit approval.

## Current blockers

- A complete Orca printer-config bundle has not yet been exported; the exact
  user profiles, current Z post-processor and representative projects/G-codes
  are nevertheless captured individually and verified.
- The PETG G-code has no matching `P1-PETG.3mf` in the intake.
- Recovery artefacts and procedure have not been matched locally to the exact revision.
- The core `BOX_*` state machine is compiled and its readable source is not present on the machine.
- The literal registration of `ACCURATE_HOME_Z` was not found in readable Python, although the underlying `G28` and PR Touch path is mapped.
- Parts of `ACCURATE_HOME_Z` remain non-observable, although pressure advance ownership is now measured.
- The corrected P5 cannot distinguish temperature ownership after its change
  because both the second filament and the stock CFS request `220 °C`.
- The large historical Z shifts have not been reproduced, although the late
  application and end-of-print erasure mechanisms are now directly proven.
- Long-run memory headroom and per-service use still need proof; the one-shot
  read-only capture confirms only the baseline.
- The exact Creality Klipper commit is unknown; the newly captured exact
  `bed_mesh.py` remains the implementation authority for the mesh adapter.
- The captured `save_variables.py` was rejected for final persistence because it
  rewrites directly. The original atomic store has deployer integration and
  exact-target in-memory import proof; its first real write and rollback remain
  gated.
- Persistent named mesh commit is now mapped exactly: save the deterministic
  profile, remove `K1_TRANSIENT`, then `SAVE_CONFIG`, which restarts Klipper.
  The installer and rollback still need offline proof.
- Every reference-changing Creality calibration path must be detected or
  wrapped so that an old accepted Z cannot survive a real recalibration.
- The compiled `BOX_*` owner may contain a late temperature write that no macro
  can intercept. The complete matrix decides whether a small replacement owner
  is required.
- The pinned Moonraker/Mainsail package and its file-manager roots completed the
  retained coexistence observation and the final read-only validation.
- A manual Mainsail calibration created an active `Base` mesh with the captured
  `6 x 6` Lagrange configuration over `5–295 mm`. It was not written to
  `printer.cfg` and is therefore transient; only `default` remains persistent.
- The real `K1 Control` adapter and offline Z/mesh guards exist. START_PRINT,
  Orca and CFS integration remain intentionally absent until their atomic
  contracts and rollback are complete.

## Exit condition for this phase

P3 has reached its exit condition. The P4 foundation slice is installed,
observed and retained. The three failed Z/mesh attempts are completely rolled
back. The corrected runtime is now installed and independently validated; its
empty state remains fail-closed until a separately authorised calibration.
