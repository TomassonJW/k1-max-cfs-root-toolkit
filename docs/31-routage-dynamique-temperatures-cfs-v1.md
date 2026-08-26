# Routage dynamique des températures CFS V1

Date : 2026-08-26
Statut : **conception et simulation closes hors imprimante ; aucun transport K1 ;
aucune validation physique ; production fermée**

## Résultat court

La cible thermique doit être portée par un ticket de phase avant le premier
effet filament. Ce ticket lie le travail, la phase, l'opération, l'outil logique,
une route CFS/slot fraîche, la cible de buse, la cible séparée du plateau et les
six invariants d'ADR-017.

La seule architecture qui couvre ce contrat est un propriétaire filament
minimal séparé : `minimal_separate_filament_owner`. La mission ne l'a pas relié
à la K1. Elle fournit seulement son contrat, son simulateur et les conditions
qui devront être satisfaites avant de préparer un paquet installable.

## Où la température stock est résolue

La capture privée exacte reste
`inventory/raw/20260826-cfs-box-wrapper-read-only-audit-v1`. Elle n'a pas été
rejouée et le binaire n'a pas été chargé.

Les chaînes du module MIPS montrent :

- `BoxAction.get_material_target_temp` aux offsets de chaîne `0x1da2cc` et
  `0x1da2e8` ;
- `get_flush_temp` juste avant dans la table des méthodes ;
- le marqueur `get next material temp: %d` à `0x1e3a5c` ;
- `nozzle_temperature`, `M104` et `M109` dans la même surface compilée ;
- Cython `0.29.32` et la source générée déclarée
  `klippy/extras/box_wrapper.c`.

La fenêtre d'incident donne l'ordre observable suivant :

1. ligne privée 7925 : type matière du slot `000001` ;
2. lignes 7927–7929 : vitesse matière puis échec du repli de vitesse ;
3. ligne 7932 : `get next material temp: 220` ;
4. ligne 7933 : `flush_temp: 220` ;
5. ligne 7967 : cible réelle de buse à `220 °C` ;
6. ligne 9058 : la purge conserve pourtant son paramètre `190`.

Le point de résolution se trouve donc dans `BoxAction`, après lecture du type
matière et avant la première cible thermique observée du chargement. Cela ne
constitue pas un point d'extension qualifié : le code source lisible est absent,
le type Cython n'offre aucun point d'extension documenté, et le même chemin
stock a déjà pris la géométrie avant la purge.

## Comparaison des quatre voies

| Voie | Avant le premier effet | First/normal et transitions | Plateau séparé | Géométrie séparée | Verdict |
|---|---:|---:|---:|---:|---|
| base matière statique | oui pour un seul palier | non | non | non | filet de sécurité seulement |
| `M104` après `T` | non | oui dans le G-code suivant | oui | non | défense tardive seulement |
| interception de `get_material_target_temp` | potentiellement | potentiellement | oui | non | refusée sans point d'extension stable |
| propriétaire filament minimal séparé | oui par contrat | oui | oui | oui | conception retenue |

La base matière n'est pas supprimée. Elle reste l'inventaire et un garde-fou
statique, mais elle ne peut pas devenir le propriétaire dynamique d'un travail.
Une réaffirmation après outil reste utile pour détecter ou bloquer une dérive ;
elle ne transforme jamais une purge antérieure fausse en succès.

## Ticket thermique de phase

Chaque frontière reçoit une valeur immuable contenant au minimum :

- `job_id` et version du contrat ;
- phase `first_layer` ou `normal` ;
- opération : maintien, chargement, retrait, purge, refill, runout ou réamorçage ;
- outil logique, sans `T0` physique supposé ;
- preuve de route unique, CFS, slot, matière et révision de mapping ;
- cible de buse de la phase ;
- cible de plateau active, séparée ;
- snapshot du Z accepté, de l'origine Z, du mesh et des axes référencés.

Une preuve de route est consommable une fois. Une reconnexion CFS invalide la
révision courante. Une route absente, périmée, réutilisée ou liée à une autre
matière arrête avant le premier effet filament.

## Règles par chemin

### Première couche et régime normal

`NOZZLE_FIRST` et `BED_FIRST` sont distincts de `NOZZLE_NORMAL` et
`BED_NORMAL`. Le passage à la phase normale vient du contrat du travail. La
base CFS ne remplace aucune de ces quatre valeurs.

### Filament déjà engagé

Le bon filament reste engagé : aucune coupe ni aucun retrait. Une petite purge
de preuve reçoit la cible active et une route fraîche. Le débit visible reste
obligatoire.

### Chargement initial

Le chargement reçoit la cible de l'outil entrant pour la phase courante avant
toute avance. Le plateau conserve sa cible. La réussite exige ensuite une preuve
de débit ; un capteur de présence seul ne suffit pas.

### Changement de matière

Le contrat fournit trois valeurs indépendantes : retrait de l'ancien,
chargement du nouveau et purge de transition. La purge doit rester dans les
bounds déclarées des deux matières. Après la purge, le contrat réapplique la
cible du nouveau segment ; aucune valeur n'est déduite d'une constante machine.

### Refill et runout équivalent

La dernière cible explicite du G-code ou de Thomas est conservée. Un slot
qualifié équivalent peut se trouver sur l'autre CFS, mais il reçoit une nouvelle
preuve de route. Une reconnexion ou une équivalence inconnue bloque.

### Pause et reprise

Une pause normale ne lance aucune frontière CFS. Une reprise simple restaure le
snapshot courant. Le réamorçage est une action distincte et volontaire, avec
son propre ticket et sa purge visible.

### Annulation et dérive

Une annulation met les deux cibles à zéro et ferme la reprise. Une cible cachée,
une commande thermique CFS, une commande de géométrie, une différence Z/mesh,
un débit absent ou un ticket invalide fait de même. Le Z n'est jamais restauré
à l'aveugle.

## Simulation déterministe

Le paquet
`packages/k1-control-v1/cfs-dynamic-temp-routing-v1/` contient 25 scénarios :

- chargement sur CFS1 et CFS2 ;
- filament déjà engagé ;
- première couche puis régime normal ;
- transition aller et retour entre deux matières et deux CFS ;
- refill avec cible opérateur et runout inter-CFS ;
- pause/reprise avec ou sans réamorçage ;
- annulation ;
- cible cachée avant effet et correction tardive ;
- commande buse ou plateau du CFS ;
- dérive géométrique ;
- route absente, périmée, réutilisée ou incohérente ;
- température de transition manquante ou hors bornes ;
- preuve de débit ou snapshot incomplet ;
- valeur de base matière différente mais non consommée comme cible dynamique.

La matrice obtient `25/25`. Le simulateur utilise seulement la bibliothèque
standard et ne possède aucun transport réseau, SSH, série, G-code ou K1.

## Suite du protocole

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PROTOCOL-V1` a ensuite cartographié les
captures privées sans connexion K1 et s'est fermé en **KO borné**. Deux adresses
sont visibles pour les requêtes d'état, mais la seule route d'effet observée
est `T1A`, adresse 1, slot A. Les trames de retrait, coupe et purge isolés, les
slots B/C/D, les effets sur le second CFS, l'intégrité de trame et l'exclusion
du propriétaire stock restent non prouvés.

La liste appelable est donc vide et aucun transport ou paquet de pose n'est
préparé. Une branche de preuve ultérieure exigera une autorité fraîche avant
toute connexion ou action physique. `MESH-EDGE-DIAGNOSTIC-V1` et la production
restent fermés.

Voir `docs/32-protocole-proprietaire-filament-minimal-cfs-v1.md` et ADR-021.
