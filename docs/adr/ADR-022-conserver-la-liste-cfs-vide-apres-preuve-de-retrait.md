# ADR-022 — Conserver la liste CFS vide après la preuve de retrait

Date : 2026-08-26

Statut : accepté

## Contexte

ADR-021 a fermé le premier protocole minimal en KO borné parce que le journal
alors examiné ne contenait aucune trame de retrait. La mission suivante a trouvé
dans un ancien journal un cycle `T1A` avec deux requêtes de retrait, deux
réponses réussies, un timeout de 150 secondes et un capteur local devenu libre.

Deux instantanés contiennent les mêmes lignes. Le plus court est le préfixe exact
du plus long : il s'agit d'une seule observation, pas de deux reproductions.

## Options

### 1. Rendre les deux trames de retrait appelables

Refusé. Leur effet a été observé dans le propriétaire constructeur, sans prise
exclusive, sans route fraîche dans le même événement et sans qualification des
erreurs, réponses tardives ou reconnexions.

### 2. Compléter les trous avec une rétroanalyse publique

Refusé. La source publique la plus détaillée utilise une autre table de numéros
de commandes. Elle confirme des formes et des durées, mais pas l'identité du
protocole local.

### 3. Reconnaître la preuve partielle et garder la surface appelable vide

Retenu. La carte de preuve est enrichie, le vérificateur la rend reproductible
et un protocole de capture passive séparé est préparé.

## Décision

`G4-K1-CONTROL-CFS-MINIMAL-OWNER-EVIDENCE-V1` est close avec
`gate_verdict=KO_BOUNDED` et `callable_messages=[]`.

La commande locale `0x11` est reconnue comme une observation exacte de retrait
`T1A` dans un cycle stock historique. Elle n'est pas reconnue comme une API sûre
ou réutilisable.

La concordance CRC-8 qualifie la terminaison de la réponse capturée. La requête
complète sur le fil et son ajout de CRC par la couche série restent à capturer.

## Conséquences

- la preuve de retrait n'est plus « absente », mais « partielle et non
  appelable » ;
- aucun transport, déployeur ou write-set n'est créé ;
- aucune connexion K1 ni action physique n'a lieu dans cette gate ;
- la production et le diagnostic de bord restent fermés ;
- la prochaine étape possible est une capture passive séparément autorisée ;
- toute implémentation exige encore une nouvelle ADR après preuves complètes.
