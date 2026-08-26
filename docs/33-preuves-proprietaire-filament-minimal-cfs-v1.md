# Preuves du propriétaire filament minimal CFS V1

Date : 2026-08-26

Statut : **KO borné hors imprimante, avec preuve de retrait ajoutée**.

## Résultat en une phrase

La solution fiable n'est pas morte : l'ancien journal apporte la trame de
retrait qui manquait, mais il ne permet toujours pas de construire sans risque
un propriétaire indépendant du CFS.

## Nouvelle preuve locale

Une séquence historique du chemin constructeur montre, sur le chemin déjà
relié à `T1A` :

```text
capteur local présent
  -> retrait vers BUFFER
  -> réponse OK
  -> retrait vers MATERIAL
  -> réponse OK
  -> capteur local libre
```

Les deux requêtes portent l'adresse 1 et le slot numérique 1. Elles utilisent
la commande locale `0x11`, avec les déclencheurs `0` puis `1`. Les deux réponses
portent l'état `0` et le même octet final `0xca`. Le timeout hôte est de 150
secondes.

Le journal court est le préfixe exact du journal long : ce sont deux instantanés
du même fichier, pas deux essais indépendants. La preuve compte donc une fois.

## Intégrité des trames

Une référence publique moderne décrit une trame complète avec tête `0xf7` et
CRC-8, polynôme `0x07`, calculé sur longueur, état, commande et données. Cette
règle redonne exactement `0xca` pour la réponse locale de retrait.

Cette concordance est utile, mais la capture locale ne montre pas la requête
complète après transformation par la couche série. La règle côté émission reste
donc partielle.

## Références publiques et limite de compatibilité

Le dépôt officiel Creality examiné publie le module `box_wrapper` sous forme
compilée, pas une source lisible reliée à l'empreinte locale.

Une autre rétroanalyse publique documente les deux déclencheurs de retrait et le
timeout de 150 secondes. Elle ne correspond toutefois pas à notre table exacte :
plusieurs commandes ont des numéros différents. Elle aide à interpréter la
capture, mais ne peut jamais servir à fabriquer une trame locale.

## Configuration constructeur

La configuration locale décrit l'ordre haut niveau : température, contrôle,
coupe, retrait, déplacement, nettoyage, chargement, extrusion et purge. Elle
confirme que coupe et purge appartiennent à une chorégraphie plus large. Elle ne
révèle ni une trame isolée de coupe, ni une séparation sûre de la température et
de la géométrie.

## Pourquoi la liste reste vide

Le retrait désormais observé reste :

- un seul passage historique ;
- non isolé du propriétaire constructeur ;
- sans route fraîche dans le même événement ;
- limité à l'adresse 1 et au slot A ;
- sans contrat sûr après timeout, réponse tardive ou reconnexion.

Il manque aussi la coupe, la purge, l'arrêt et les effets sur les sept autres
routes. Surtout, aucun mécanisme ne prouve que le propriétaire constructeur a
cessé d'émettre puis repris proprement.

Le verdict reste donc `KO_BOUNDED`, `callable_messages=[]`, sans transport ni
candidat de déploiement.

## Suite bornée

Le paquet prépare un protocole de capture passive. Il n'autorise aucune
connexion. La prochaine gate possible est
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`, après revue puis GO exact
séparé.

Voir ADR-022 et
`packages/k1-control-v1/cfs-minimal-owner-evidence-v1/`.
