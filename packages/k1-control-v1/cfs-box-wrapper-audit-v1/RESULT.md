# Résultat — CFS Box Wrapper Audit V1

Date : 2026-08-26
Statut : **audit OK ; aucune primitive stock qualifiée ; production fermée**

## Verdict

```text
verdict=block_stock_sequence_no_callable_primitive
BOX_EXTRUDE_MATERIAL=blocked_observed_temperature_and_geometry_owner
BOX_EXTRUDER_EXTRUDE=unqualified_not_isolated
BOX_MATERIAL_FLUSH=unqualified_not_isolated
adapter.deployment_candidate=false
```

L'empreinte du binaire capturé correspond exactement au manifeste historique.
Son en-tête confirme un module partagé ELF 32 bits MIPS little-endian. Il n'a
été ni chargé ni exécuté pendant l'audit.

La trace complète prouve l'ordre suivant : demande explicite à `190 °C`, chemin
de géométrie interne, lecture de la température matière `220 °C`, cible réelle
de buse `220 °C`, puis purge qui conserve encore son paramètre `TEMP=190` sans
reprendre la propriété de la cible. Le plateau est resté à cible zéro pendant
ce passage précis.

## Adaptateur étroit préparé

Le contrat d'adaptation est volontairement fermé : liste de primitives stock
appelables vide, six invariants obligatoires et aucune pose candidate. Il faut
maintenant soit isoler une primitive avec une preuve complète, soit préparer un
propriétaire minimal séparé. Le module complet n'est pas remplacé : sa surface
couvre aussi les deux CFS, les capteurs, le refill et les reprises.

## Portée

La collecte a été strictement en lecture seule. Aucun G-code, chauffage,
mouvement, purge, restart ou fichier distant n'a été produit. Ce résultat
n'autorise ni pose ni essai physique.

## Validation locale

- analyseur exécuté sur le binaire et la fenêtre privée exacts : verdict attendu ;
- 10 tests propres au paquet verts ;
- 334 tests Python du dépôt verts, 3 ignorés historiques ;
- contrats JSON lisibles et `git diff --check` vert.
