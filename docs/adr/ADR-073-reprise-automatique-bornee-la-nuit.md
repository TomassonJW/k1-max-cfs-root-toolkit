# ADR-073 — Reprise automatique bornée d'une impression en pause

Date : 24 septembre 2026. Statut : accepté et en service.

## Contexte

Thomas veut qu'une impression longue se termine seule la nuit. Un changement de
filament raté (`key837`) met l'impression en pause ; le 23 septembre, sa reprise
à l'écran a rechargé et purgé correctement, puis s'est figée (corrigé par
ADR-072). La nouvelle tentative consiste donc à refaire ce que Thomas fait à
l'écran : `RESUME`. Le mécanisme exact de pause du CFS sur `key837` reste
inconnu.

## Décision

Un processus externe à Klipper, `kctrl_autoresume.py`, lancé dans `/tmp` de la
K1, lit l'état par `/tmp/klippy_uds` toutes les 10 s et n'envoie qu'une
commande, `RESUME`, quand toutes les conditions sont réunies :

- impression en pause depuis au moins 60 s avec le G-code libre
  (`idle_timeout = Ready`) ;
- axes toujours référencés `xyz` : jamais après une coupure moteurs ;
- au moins 300 s d'impression : jamais pendant la séquence de départ ;
- au moins 150 s depuis la tentative précédente ; 15 tentatives au plus.

Il s'arrête seul à la fin, à l'annulation, à une erreur de l'impression, à un
arrêt de Klipper ou à la présence de `/tmp/kctrl_autoresume.stop`. Il ne touche
ni module, ni configuration, ni départ, ni fin, et ne redémarre rien ; un
redémarrage de la K1 l'efface.

## Conséquences

- Une pause manuelle pendant l'impression est reprise au bout d'une minute ;
  pour garder une pause, créer le fichier d'arrêt ou annuler.
- Une bobine réellement vide sans bobine identique de secours épuise les
  15 tentatives puis reste en pause.
- Chaque pause journalise message, état CFS et extrudeur dans
  `/tmp/kctrl_autoresume.log` : preuve pour la future reprise intégrée dans
  K1 Control.
