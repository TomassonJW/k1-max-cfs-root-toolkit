# ADR-024 — Refuser les faux succès du retrait stock

Date : 2026-08-27

Statut : accepté

## Contexte

La macro officielle Creality sait couper puis désengager le filament côté CFS,
mais le passage réel `T1A` a laissé la chauffe active. L'API a par ailleurs
répondu `ok` à une commande mal encodée que Klipper a refusée.

Un simple appel de macro ne constitue donc pas un retrait autonome fiable.

## Options

### 1. Faire confiance à la réponse HTTP

Refusé. Le passage réel montre qu'elle peut être positive sans effet G-code.

### 2. Relancer automatiquement jusqu'au succès

Refusé. Après une perte de réponse, le premier retrait peut encore être en
cours. Une seconde commande risquerait un double effet mécanique.

### 3. Prouver les effets et nettoyer une seule fois

Retenu. Le garde sépare trois moments : refus sans effet, tentative unique du
retrait, puis nettoyage thermique obligatoire et vérifié.

## Décision

Le garde ne déclare un succès que si la requête revient sans erreur de
transport, la route est réellement libérée, la commande CFS est vide et les
chauffes sont à zéro. La réponse HTTP est conservée comme information, jamais
comme preuve suffisante. Le préflight live a ensuite confirmé qu'aucun champ
direct de fin stock n'existe : le contrat n'en suppose plus un.

Avant le premier effet, un refus n'envoie pas `TURN_OFF_HEATERS`, afin de ne pas
interrompre une activité étrangère. Dès que `BOX_QUIT_MATERIAL` a été tenté, le
nettoyage thermique est exécuté une fois dans tous les chemins de sortie.

## Conséquences

- aucun retry automatique du retrait ;
- un timeout produit un KO et demande une vérification humaine ;
- un arrêt thermique non prouvé masque le succès apparent du retrait ;
- le contrôleur reste indépendant du transport grâce à une API injectée ;
- la fausse API suffit pour cette gate hors imprimante ;
- un adaptateur live sera une gate séparée, d'abord en lecture seule ;
- aucune pose ou action physique n'est autorisée par cette décision.
