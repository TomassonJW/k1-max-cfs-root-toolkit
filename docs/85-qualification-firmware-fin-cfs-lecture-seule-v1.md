# 85 — Fin CFS après relève : qualification du firmware en lecture seule

21 septembre 2026. Autorisée par « ok go » après la préparation du document 84.
**Qualification à froid close : lien reprise/coupe établi, chronologie cutter
corrigée dans le candidat hors imprimante. Aucune installation ni action physique.**

## Résultat

Deux incertitudes du candidat sont levées par des preuves propres à cette K1 :

1. Le prédicat compilé `if_in_resume` lit et retourne
   `virtual_sdcard.do_resume_status`. La commande de coupe s'arrête si cette
   valeur est vraie. Les sources installées mettent ce drapeau à True à la
   reprise et le laissent ainsi jusqu'à la sortie du lecteur du fichier.
   Différer la fin permet donc de sortir de ce contexte sans forcer un champ
   interne du firmware. L'exécution physique différée complète reste à tester.
2. Le relâchement du cutter n'arrive pas nécessairement avant le retrait.
   Dans la récupération manuelle du 21, il arrive **après** le rembobinage.
   Le candidat de la PR 71 l'attendait trop tôt et aurait fermé ce parcours
   normal. La confirmation de coupe est maintenant exigée avant retrait ;
   le relâchement reste exigé, mais avant la finalisation stock.

Les trois défauts établis de l'incident initial restent : case T1A mémorisée
après relève vers B, coupe refusée en contexte de reprise, puis retrait/fin
poursuivis malgré le refus. Le correctif vise toujours la route CFS fraîche,
un unique retrait et l'arrêt thermique en cas d'erreur.

## Preuve de reprise dans le binaire exact

Firmware lu : `2.3.5.34`, architecture MIPS. Le fichier CFS installé a la même
empreinte que la capture historique du 26 août :
`af630c02ccdb51b57585114e5be2be7fcf91fdb10d88872eb6a0c65f048de777`.
Il n'a donc pas été téléchargé une seconde fois. **Ni import ni exécution du
binaire**, sur le PC comme sur la K1 : lecture statique des tables ELF et des
instructions de la copie locale.

La table de méthodes en `0x205080` associe `if_in_resume` au corps en
`0x102928..0x102e04`. Les tables de chaînes identifient `printer`,
`lookup_object`, `virtual_sdcard`, `do_resume_status`, `logging` et `info`.
La première lecture du drapeau sert au journal ; la seconde, en
`0x102bdc..0x102be8`, alimente le retour en `0x102c6c`. Le helper en
`0x2bd68` est une lecture d'attribut Python, avec repli sur `PyObject_GetAttr`.
La commande `cmd_cut_material`, en `0x0eb95c`, appelle ce prédicat et bifurque
vers le refus « In resume » lorsqu'il est vrai (`0x0ebb34..0x0ebc10`).
Cette interprétation a été relue avec les références de chaînes, la table des
méthodes et les instructions ; elle ne découle pas d'une simple recherche de
texte dans le binaire.

Recoupement des sources actuelles : `pause_resume.py:209` met le drapeau à
True ; `virtual_sdcard.py:1132` le remet à False à la sortie du lecteur.
`is_active()` dépend du timer de travail, remis à None juste après. La fin
candidate attend ces deux conditions et conserve les contrôles de pause et
d'identité du travail. Aucun de ces champs n'a été modifié pendant cet audit.

L'analyse utilise temporairement [Capstone](https://www.capstone-engine.org/lang_python.html)
5.0.7 et [pyelftools](https://github.com/eliben/pyelftools) 0.33, installés dans
un dossier de travail local puis retirés. Aucune dépendance du projet ni de la
K1 n'est ajoutée. Les sources et désassemblages constructeur restent privés.

## Chronologie réelle du cutter

Fenêtre historique lue : 09:19:40–09:21:35, Europe/Paris. Recherche par 13
petits sondages de 64 Kio, puis une fenêtre de 16 Mio maximum, au repos et à
faible priorité ; pas de parcours intégral du journal de 361 Mo. Capture privée
`inventory/raw/20260921-cfs-end-cold-v1/recovery-window.txt`.

| Heure | Événement |
| --- | --- |
| 09:19:48,862 | Réception de `BOX_CUT_MATERIAL`. |
| 09:19:48,864 | `if_in_resume: False`. |
| 09:20:12,186 | Capteur cutter au contact. |
| 09:20:13,313 | Retour de coupe annoncé OK. |
| 09:20:13,322 | Coupe annoncée déclenchée. |
| 09:20:13,329 | La commande de coupe rend la main. |
| 09:20:13,430 | Début du retrait manuel `BOX_RETRUDE_MATERIAL`. |
| 09:21:27,876 | Le retrait rend la main. |
| 09:21:28,199 | Capteur cutter relâché, soit 323 ms après le retrait. |

La garde antérieure aurait attendu cinq secondes après 09:20:13,329, puis
refusé sans rembobiner. Ce scénario a d'abord été reproduit en échec, puis
passe avec les temps relatifs réels après correction. Une absence de
relâchement après retrait produit toujours `cutter_release_not_confirmed`,
coupe les chauffes et interdit `BOX_END`, sans deuxième tentative.

Limite : cette récupération utilisait le retrait stock sans TNN, lancé à la
main. Elle qualifie l'ordre des signaux, **pas** une exécution réelle de tout
le nouveau `END_PRINT` avec la route TNN explicite. La confirmation physique
du cycle complet reste distincte.

## Compatibilité observée et vérifiée sur le PC

Neuf sources/configurations ciblées ont été copiées vers le PC et leur
empreinte comparée à celle relevée sur la K1. Les contrôles suivants ne font
pas démarrer Klipper complet : les commandes physiques sont simulées.

- Le répartiteur G-code installé est identique à la capture déjà utilisée par
  les tests (`20d21ace…cde7`). Son enregistrement de commandes et le passage
  des paramètres sont vérifiés avec son véritable code.
- `klippy:connect` est exécuté avant `klippy:ready` dans `klippy.py:195/254` ;
  le renommage des macros a lieu à la connexion. L'enveloppe du candidat
  s'enregistre ensuite à l'état prêt. Son installation complète reste à valider.
- Les erreurs de commande sont relancées, mais certaines exceptions ordinaires
  sont absorbées par `gcode.py:214..226` après émission de `!!`. Le candidat
  détecte cette sortie et interdit le retrait ; les trois voies d'erreur sont
  testées avec le répartiteur réel.
- `invoke_cancel` émet `gcode:cancel` avant d'attendre le verrou. Le test réel
  vérifie l'ordre événement → coupure thermique → acquisition du verrou.
- `heaters.turn_off_all_heaters()` appelle directement `set_temp(0)` ; cette
  voie ne dépend pas de la file G-code. Le minuteur reste dépendant de la boucle
  Klipper et ne peut garantir l'arrêt immédiat d'un moteur CFS autonome.
- `CANCEL_PRINT_BASE` est bien l'alias de l'annulation de `pause_resume`.
  Son parcours SD ferme le fichier, met à jour l'historique et les données de
  reprise, et peut restaurer les facteurs de vitesse/débit. Ce parcours n'a
  pas été exécuté sur la K1 pendant l'audit.
- La fin stock conserve `BOX_END`, `BOX_END_PRINT` et le parc `END_PRINT_POINT`.
  Le candidat ne l'autorise qu'après tête vide et route libérée ; les effets
  compilés stock ne sont pas remplacés par une simulation dans la machine.

L'aide GET expose START/END/CANCEL, `CANCEL_PRINT_BASE` et `END_PRINT_NO_M84`.
Elle n'expose pas les deux primitives BOX demandées : le code confirme que
cette aide ne contient que les commandes documentées, pas tout le registre.
Cela n'est donc pas une preuve d'absence. Le module `kctrl_end` est absent des
objets chargés : le candidat n'est toujours pas installé.

## Vérifications, fichiers et absence d'effet

- Tests du candidat : **72/72**, dont six tests facultatifs utilisant le
  répartiteur privé exact ; ils sont ignorés sur un poste sans cette capture.
- Suite locale : **1 538 réussis, 2 échecs préexistants, 2 échecs attendus,
  55 sous-tests réussis**. Les deux échecs sont ceux documentés au document 84 ;
  aucune exclusion ni modification de leurs attentes.
- **16 empreintes identiques avant/après**, dont le binaire, les sources de
  reprise/chauffe/interprétation et les configurations installées.
- État final : `cancelled`, aucune pause, consignes buse/plateau zéro, axes
  libérés, capteur de tête vide et aucune route engagée dans les deux CFS.
- Aucun G-code envoyé, aucune chauffe, aucun mouvement, aucun fichier distant
  remplacé, aucun redémarrage. L'observation n'est pas une preuve caméra.
- Fichiers modifiés : `kctrl_end.py`, ses tests, contrat candidat, README,
  ADR-069, STATE et HANDOFF. Nouveau rapport et
  [manifeste nettoyé](../inventory/redacted/20260921-cfs-end-cold-v1/qualification.json).

Deux lectures partielles sont conservées : le premier filtre cherchait un
appel `send_event` alors que le démarrage utilise des boucles de callbacks ;
la première requête de capteur encodée avec `%20` renvoyait un objet vide.
Les lectures corrigées ferment ces deux ambiguïtés, sans effet machine.
Les captures brutes, identifiants machine, scripts privés et fichiers
constructeur restent dans `inventory/raw`, hors Git.

## Prochaine étape

Le prédicat de reprise et l'ordre des signaux ne sont plus des inconnues à
réauditer. La prochaine préparation utile est de **raccorder l'état de fin à
l'interface et construire le paquet de pose/retour arrière**, toujours avant
activation : afficher « fin en cours » et « fin incomplète » même lorsque
`print_stats` annonce déjà le fichier terminé ; épingler les fichiers,
empreintes, sauvegardes, ordre de chargement et critères de validation à froid.

Une pose désactivée puis un essai physique borné auront leurs preuves propres.
La séquence complète après relève réelle, avec route TNN explicite, caméra et
arrêt thermique observé, n'est pas encore validée. Ne pas activer par simple
changement de configuration. Le défaut de fin installé reste présent.

Modèle conseillé pour la préparation UI et du paquet : **GPT-5.6 Sol / high**,
les interfaces à traiter étant désormais identifiées. Option économique pour
la seule partie affichage : **Sol / medium** ; garder le raisonnement high
pour la pose, les erreurs et le retour arrière. Pas besoin d'un modèle plus
puissant pour répéter la collecte close.
