# Procédure candidate G4-CFS-TEMP-PLA

## État

Préparée localement le 2026-08-20. **Non autorisée et non déployée.**

Elle ne pourra être exécutée qu'après l'accord explicite de Thomas pour le nom
exact `G4-CFS-TEMP-PLA`, imprimante au repos.

## Fichiers concernés sur la machine

- `/usr/data/printer_data/config/printer.cfg`
- `/usr/data/printer_data/config/gcode_macro.cfg`
- `/usr/data/printer_data/config/box.cfg`
- nouveau : `/usr/data/printer_data/config/cfs_temperature_contract.cfg`

Empreintes exigées avant modification :

| Fichier | SHA-256 attendu |
|---|---|
| `printer.cfg` | `272640237e20659cf01f3268ed4cb0282b098c3d613e94bf84a3b80caac3c3b0` |
| `gcode_macro.cfg` | `864fedde88fbb345c220ae5658f7b04779b3981bd78d68eda6fa63c59c79a04f` |
| `box.cfg` | `e7a6b26df58a9fa8e49d3af6845f5a0937a790c8ef494b96ec72fd7392abc7a7` |

Une seule différence arrête la procédure. Aucun ajustement automatique du patch
sur un fichier inconnu n'est permis.

Le patch utilise volontairement des fragments sans lignes de contexte et doit
être appliqué avec l'option `--unidiff-zero`. Cette forme évite de republier des
lignes constructeur inutiles. Elle n'est sûre ici que parce que les trois
empreintes exactes sont contrôlées avant toute application.

## Sauvegarde avant changement

Le futur script de déploiement devra :

1. confirmer l'état `standby` et des cibles de chauffe à zéro ;
2. recalculer les trois empreintes ci-dessus ;
3. créer un dossier horodaté sous `/usr/data/printer_data/config-backups/` ;
4. y copier les trois fichiers avec conservation des droits ;
5. calculer et rapatrier localement le manifeste SHA-256 de la sauvegarde ;
6. préparer les quatre nouveaux fichiers sous des noms temporaires ;
7. vérifier leur contenu avant remplacement ;
8. remplacer les fichiers un par un, sans redémarrer tant que les quatre ne sont
   pas présents et vérifiés.

Le script lui-même n'est volontairement pas fourni avant le G4 nommé : écrire,
copier, recharger ou redémarrer la machine reste interdit à ce stade.

## Validation prévue

### Validation sans chauffe

Après installation et redémarrage contrôlé de Klipper :

- service actif et aucune erreur de configuration ;
- `HELP` montre les macros `CFS_TEMP_CONTRACT*` ;
- le fichier actif contient `Tn_extrude_temp: 195` une seule fois ;
- les quatre fichiers actifs correspondent aux empreintes locales préparées ;
- imprimante toujours au repos, chauffes à zéro.

### Validation physique minimale

Un seul travail utile avec le Geeetech PLA connu :

- G-code de départ contenant le contrat exact `190/195` ;
- deux emplacements CFS réellement chargés avec le même Geeetech PLA et déclarés
  PLA ;
- surveillance humaine de la première couche ;
- si un remplacement automatique utile survient, capture passive de la reprise ;
- aucune cible à `220 °C` ;
- purge CFS à `195 °C`, première couche à `190 °C`, impression à `195 °C` ;
- après remplacement équivalent, cible finale identique à la cible mémorisée ;
- pression d'avance observée mais non modifiée par ce lot.

## Critères d'arrêt

Arrêt et retour arrière immédiat si :

- une empreinte initiale diffère ;
- Klipper refuse la configuration ;
- le CFS ou l'écran n'est plus disponible ;
- une température à `220 °C` apparaît ;
- le contrat accepte un fichier autre que `GEEETECH_PLA 190/195` ;
- un comportement Z, déplacement, coupe ou chargement diffère de la référence ;
- Thomas doit corriger manuellement autre chose que son Z déjà connu.

## Retour arrière

1. arrêter le travail si une impression a démarré ;
2. laisser refroidir et revenir à l'état de repos ;
3. restaurer les trois fichiers depuis le dossier de sauvegarde vérifié ;
4. retirer uniquement `cfs_temperature_contract.cfg` ;
5. redémarrer Klipper de façon contrôlée ;
6. vérifier les trois empreintes d'origine, l'écran, les deux CFS et les cibles à
   zéro ;
7. conserver les journaux locaux pour expliquer l'échec.

Le retour arrière ne réécrit pas le firmware et ne touche pas aux données des
bobines.
