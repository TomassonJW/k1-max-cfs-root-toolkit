# Protocole du propriétaire filament minimal CFS V1

Date : 2026-08-26

Statut : **KO borné hors imprimante ; aucun message appelable**.

## Question traitée

`CFS-DYNAMIC-TEMP-ROUTING-V1` a choisi un propriétaire filament minimal séparé
pour recevoir la bonne température avant le premier effet. Cette mission devait
vérifier si les seules preuves privées déjà capturées permettent de décrire son
protocole sans inventer de trame, d'acquittement, d'état ou de règle de
coexistence.

La gate n'a établi aucune connexion à la K1. Le module MIPS a seulement été
haché ; il n'a été ni chargé, ni importé, ni exécuté.

## Sources exactes

Quatre fichiers privés restent hors Git : le module `box_wrapper`, ses chaînes
statiques, le journal complet et la fenêtre d'incident. Leurs empreintes sont
figées dans `evidence-map.json`. La carte publiée ne contient aucun numéro de
série, identifiant unique ou payload de réponse d'identité.

Le vérificateur lit ces fichiers localement, recalcule les empreintes, les
comptes de lignes et les trames annoncées, puis confirme les absences bornées.
Il n'ouvre le binaire que comme suite d'octets pour le SHA-256.

## Ce que montre réellement le journal

Les requêtes observées utilisent cette forme :

```text
adresse | longueur | 0xff | commande | payload
```

Les réponses retenues utilisent :

```text
0xf7 | adresse | longueur | état | commande | payload ou terminaison
```

La longueur est cohérente sur les exemples, mais le dernier octet et la règle
d'intégrité ne sont pas qualifiés. Le wrapper journalise une attente par clé
`(adresse, commande)`. Aucun identifiant de transaction n'apparaît. Une réponse
tardive pourrait donc être confondue avec une nouvelle requête sur la même clé
si le protocole de resynchronisation était inventé.

Huit commandes sortantes apparaissent dans le journal complet :

- `SET_BOX_MODE` (`0x04`) ;
- `GET_BUFFER_STATE` (`0x05`) ;
- `GET_FILAMENT_SENSOR_STATE` (`0x08`) ;
- `GET_BOX_STATE` (`0x0a`) ;
- `SET_PRE_LOADING` (`0x0d`) ;
- `TIGHTEN_UP_ENABLE` (`0x0f`) ;
- `EXTRUDE_PROCESS` (`0x10`) ;
- `GET_VERSION_SN` (`0x14`).

Cette présence ne les rend pas appelables. Les requêtes d'état n'ont pas encore
un contrat complet de réponse, timeout et reconnexion. Les commandes mutantes
appartiennent à une séquence constructeur plus large dont température et
géométrie ne sont pas séparées.

## Route et deux CFS

Les adresses 1 et 2 sont toutes deux interrogées. En revanche, la seule action
filament reliée à un outil logique est `T1A` : adresse 1, slot A, numéro 1.
`EXTRUDE_PROCESS` n'apparaît que sur l'adresse 1. Aucun effet n'est observé pour
B/C/D ou pour le second CFS.

Une présence sur les deux adresses prouve donc deux appareils joignables dans
la capture, pas un protocole d'effet symétrique.

## Retrait, coupe et purge

Les chaînes statiques contiennent notamment
`communication_retrude_process`,
`communication_ctrl_connection_motor_action` et
`communication_extrude2_process`. Le journal complet ne contient aucune
réponse nommée correspondante et aucune trame sortante ne peut leur être
attribuée.

Le nom haut niveau de coupe ne révèle pas davantage une trame série isolée.
La purge observée appartient au chemin stock déjà refusé, qui possédait la
température et la géométrie. Un symbole seul n'autorise donc aucune
reconstitution.

## Propriétaire exclusif

Deux lignes indiquent que le traitement heartbeat n'était pas actif pendant
une partie de l'incident. Elles ne définissent ni prise de verrou, ni
acquittement, ni arrêt sûr, ni restitution au propriétaire constructeur. Elles
ne prouvent pas que deux propriétaires ne peuvent jamais envoyer une commande
concurrente.

Sans mécanisme exclusif prouvé, le propriétaire minimal ne peut pas être armé.

## Émulateur de sûreté

L'émulateur ne possède aucun transport. Il accepte seulement les trames exactes
de la carte de preuve en mode rejeu. Il applique ces règles :

- une seule requête en attente par `(adresse, commande)` ;
- un doublon est bloqué ;
- un timeout met la clé en quarantaine ;
- une réponse tardive ou sans attente correspondante ne devient jamais un
  acquittement ;
- une reconnexion invalide les attentes et les routes ;
- une révision de mapping rend l'ancienne route caduque ;
- une méthode visible seulement dans les chaînes reste non appelable ;
- tout effet reste bloqué par l'absence de transport, d'intégrité qualifiée,
  de liste appelable et d'exclusion du propriétaire stock.

Les 25 scénarios couvrent aussi deux clés de requête simultanées sur les deux
CFS, sans prétendre qu'un effet est qualifié sur le second.

## Verdict

La gate est **KO borné** : le sous-ensemble visible est cartographié, mais il
ne suffit pas à réaliser le propriétaire minimal. La liste appelable reste
`[]`, `deployment_candidate=false` et la production reste fermée.

Ce KO est une clôture correcte, pas un échec de l'émulateur. Les tests verts
prouvent que le paquet refuse les zones inconnues.

## Réouverture possible

La branche suivante peut seulement chercher les preuves manquantes sous
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1`. Par défaut elle reste hors
imprimante. Toute connexion, capture réelle ou action filament exigera une
autorité fraîche et une gate séparée revue.

Voir ADR-021 et
`packages/k1-control-v1/cfs-minimal-owner-protocol-v1/`.
