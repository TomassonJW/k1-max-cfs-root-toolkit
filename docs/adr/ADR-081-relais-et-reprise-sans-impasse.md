# ADR-081 - Relais raté et « Reprendre » sans impasse

Date : 15 novembre 2026. Statut : accepté ; tranche 2 construite hors
imprimante, non posée. Documents 110 et 111. Complète ADR-080.

## Contexte

Le 15 novembre, le relais automatique de bobine a raté deux chargements : filament
en tête, CFS au repos, courant extrudeur à 0,28 A, route fausse, capteur de tête
coupé, garde du bac verrouillée. « Reprendre » aurait coupé les chauffes. La
pièce a été sauvée à la main (document 110). Thomas veut que ce soit impossible
à terme, sans IA ni console.

## Décision

1. Le départ `kctrl_start` accroche `BOX_CHECK_MATERIAL_REFILL`, `RESUME`,
   `BOX_RESUME_EXTRUDE` et `kctrl_tool_change.reload`, installés d'un bloc et
   défaits d'un bloc ; échec d'installation = tranche 1 intacte, dit dans
   `relay.failure`.
2. Courant remis avant le relais ; chargement raté attribué par preuves
   croisées ; reprise automatique par purge au bac (même gabarit que le départ,
   tampon lu) ; sinon pause réelle, phrase, tête hors du bac.
3. Ni exception ni pause dans l'enveloppe `T1A..T4D` (ADR-072).
4. « Reprendre » : sortie du bac d'abord, jamais de plateau remonté verrouillé ;
   jamais de second chargement stock après une purge prouvée.
5. Phrases : ASCII, sans apostrophe, jamais en `!!`, jamais « failed ».
6. Pose unique de `resilience-v2` (tranches 1 et 2), au repos, accord de Thomas.

## Conséquences

Limites et inconnues : document 111, sections 4 et 5. Retour arrière :
sauvegarde `backups/resilience-v2`, ou `resilience-v1` non posé donc sans objet.
