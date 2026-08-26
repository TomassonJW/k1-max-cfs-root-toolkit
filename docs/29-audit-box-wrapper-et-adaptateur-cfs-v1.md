# Audit `box_wrapper` et adaptateur CFS V1

Date : 2026-08-26
Statut : audit en lecture seule clos ; adaptateur fermé hors imprimante ;
production fermée

## Résultat court

Le `220 °C` n'est pas venu de la consigne `TEMP=190` de la purge. Le chemin de
chargement a lu la température matière stock, annoncé `get next material temp:
220`, calculé `flush_temp: 220` puis porté la cible réelle de buse à `220 °C`.
La purge de 10 mm a ensuite encore affiché son paramètre `temp: 190.0`, alors
que la cible réelle était déjà et restait à `220 °C`.

Le même chemin a aussi exécuté sa propre géométrie : état X non référencé,
déplacement XY et `FORCE_MOVE` de Z. Le problème est donc bien une prise de
contrôle simultanée de la température et du positionnement, pas seulement une
mauvaise hauteur de plateau.

## Preuve exacte et privée

La capture privée est
`inventory/raw/20260826-cfs-box-wrapper-read-only-audit-v1`. Elle contient le
préfixe complet et immuable du journal au moment de la collecte, sa fenêtre
exacte de 12 800 lignes, le binaire et ses chaînes. Elle reste ignorée par Git.

| Élément | Preuve |
|---|---|
| binaire | 2 071 412 octets, SHA-256 `af630c02…de777` |
| format | ELF 32 bits, little-endian, MIPS, objet partagé |
| journal capturé | préfixe exact de 208 733 957 octets |
| fenêtre incident | lignes absolues 846405 à 859204 |
| écriture K1 | aucune |
| G-code, chauffe, mouvement, CFS, restart pendant l'audit | aucun |

L'empreinte du binaire correspond au manifeste historique du dépôt. Le module
n'a jamais été importé, chargé ou exécuté sur le PC : seule sa structure et ses
chaînes lisibles ont été examinées.

## Chronologie déterministe

Les numéros ci-dessous sont ceux de la fenêtre privée nettoyée localement :

1. ligne 4599 : script reçu avec `M104/M109 S190`, puis les trois commandes
   CFS et `BOX_MATERIAL_FLUSH ... TEMP=190` ;
2. lignes 6857–6861 : `x_axes is NULL`, déplacement XY puis `FORCE_MOVE` Z ;
3. lignes 7932–7933 : température matière et `flush_temp` calculées à `220` ;
4. ligne 7967 : cible réelle de buse `220`, cible plateau `0` ;
5. ligne 9058 : la purge de 10 mm conserve pourtant `temp: 190.0` ;
6. ligne 9466 : position Y réelle `305`, position sûre interne `291,5` ;
7. ligne 9676 : fin du script ;
8. ligne 9722 : coupure explicite des chauffes ;
9. ligne 11888 : rechargement ultérieur du profil robuste.

Cette chronologie prouve que le paramètre visible de la purge ne possède pas la
cible thermique. Elle prouve aussi que les effets dangereux arrivent dans le
chemin de chargement avant la trace distinctive de la purge de 10 mm.

## Ce que montre le binaire

Les chaînes du binaire exact exposent les trois commandes considérées, la clé
`Tn_extrude_temp`, les messages de calcul à `flush_temp`, plusieurs commandes
`M109/M104`, `G28 X Y`, `safe_pos_y`, `extrude_pos_z` et `BED_MESH_CLEAR`.

Cela suffit à confirmer que le module possède une surface thermique et
géométrique large. Cela ne reconstitue pas tout son graphe d'appels : le module
Cython est compilé et dépouillé de ses symboles de débogage. L'absence de chaîne
`M140`, `M190` ou de commande Z explicite n'est donc pas une preuve d'absence
d'effet plateau ou Z. Les six invariants restent obligatoires.

## Verdict par primitive

| Primitive | Verdict | Motif |
|---|---|---|
| `BOX_EXTRUDE_MATERIAL` | refusée | propriétaire thermique et géométrique observé |
| `BOX_EXTRUDER_EXTRUDE` | non qualifiée | pas de frontière d'état isolée dans ce script |
| `BOX_MATERIAL_FLUSH` | non qualifiée | paramètre 190 visible, mais cible 220 déjà active et appel non isolé |

Il n'existe donc aujourd'hui aucune primitive stock autorisée pour l'adaptateur.
Qualifier « non observé » comme « sûr » serait une erreur.

## Adaptateur étroit préparé

`packages/k1-control-v1/cfs-box-wrapper-audit-v1/adapter-contract.json` fixe un
adaptateur fermé :

- capture des six invariants avant toute phase ;
- géométrie entièrement préparée par K1 Control avant la frontière CFS ;
- cibles buse et plateau explicites, stabilisées et surveillées ;
- appel uniquement d'une primitive qualifiée séparément ;
- preuve de débit visible et invariants identiques avant sortie ;
- arrêt thermique avec deux cibles à zéro ;
- arrêt géométrique sans restauration Z à l'aveugle.

La position froide `X=185,5 / Y=305 / Z=30 mm` reste une candidate confirmée
visuellement par Thomas, pas une autorisation de mouvement. La liste des
primitives appelables est vide et `deployment_candidate=false`.

## Décision et prochaine gate

Le correctif « appeler les primitives stock puis remettre 190 » est définitivement
refusé. Le remplacement complet de `box_wrapper` reste également refusé à ce
stade : sa surface couvre les deux CFS, les capteurs, le refill et les reprises.

La prochaine mission sûre est hors imprimante : préparer un propriétaire
filament minimal séparé à partir du protocole série déjà observé, ou obtenir une
preuve isolée suffisante d'une primitive étroite sans l'exécuter sur la K1. Une
future pose ou un essai physique devra être une mission distincte avec fichiers,
commandes, backup, rollback et critères OK/KO relus.
