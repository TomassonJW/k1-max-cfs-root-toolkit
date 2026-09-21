# 89 — Prise T1B réussie, arrêt causé par l'observateur

21 septembre 2026. Suite du document 88. Thomas a retiré le filament via
l'interface officielle, nettoyé la buse et confirmé le plateau libre. Une
lecture fraîche confirme le capteur de tête libre et les chauffes à zéro.

## Ce qui a réellement changé

Aucun changement de chargement, vitesse ou courant moteur. Le candidat de fin
est activé à froid sous contrôle d'empreintes puis reste `idle` tout l'essai.
Un surveillant externe ajoute les mesures de courant/positions/capteurs et un
arrêt avant la relance interne : huit réponses consécutives `full` sans état
`middle` ou `empty`. Le rejeu du défaut précédent place cet arrêt 17,643 s avant
le contact cutter. Cela reste une preuve rétrospective, pas une garantie de
marge pour tous les défauts futurs.

## Preuves de la prise

- À 18:48:39, une seule première prise `extrude_process_stage7` réussit.
- Le tampon revient à `middle` ; zéro réponse `full` dans ce chargement.
- 48 échantillons avec T1B et présence à la tête : courant déclaré stable à
  0,5615259733 A. Les coordonnées et vitesses sont des estimations du firmware.
- Thomas confirme « Ça tourne », puis l'insertion et l'extrusion sans problème
  apparent, et explicitement la purge au bac avec boule décrochée.
- La commande de ligne d'amorce est atteinte à 18:49:24. L'arrêt survient
  pendant les mouvements suivants, avant la pause prévue du fichier.

Ces faits prouvent ce chargement réussi. Ils n'expliquent pas le défaut
intermittent précédent. Un effet du retrait manuel sur la position initiale
reste une hypothèse ; une panne générale du moteur ou une correction par le
nouveau propriétaire de fin ne sont pas démontrées.

## Erreur de surveillance assumée et corrigée

À 18:49:31, la commande `SET_HOTEND_FAN VALUE=1` est rejetée comme inconnue.
Le journal montre une requête `gcode/script` venant d'un autre client webhooks,
reçue auparavant et terminée à cet instant. `PAUSE POST_WORK=0` figure encore
parmi les prochaines lignes du fichier. L'attribution initiale à la pause
était donc trop rapide. L'émetteur exact de cette requête reste non identifié.

À 18:49:32, notre observateur transforme tout `!!` en arrêt d'urgence. Cet arrêt
évitable provoque ensuite la sortie de Klipper, avec les erreurs TMC/connexion
déjà observées après M112. L'interface ne répond alors plus côté Klipper.
Ni `RESUME_BASE` ni `END_PRINT` n'ont été exécutés.

Le garde corrigé journalise uniquement la chaîne exacte de cette réponse
externe connue. Il ne fournit aucune commande manquante dans Klipper et ne
modifie pas les gardes de zone. Les autres erreurs, `key837`, le tampon plein,
les états d'erreur machine et les plafonds thermiques restent bloquants.
Le rejeu de cette capture passe ; celui du vrai défaut s'arrête toujours avant
le cutter. **27 tests ciblés passent.** Le correctif n'a pas encore été éprouvé
sur un nouvel essai physique.

## Récupération vérifiée

L'ancien processus Klipper est vérifié absent. Le fichier du candidat est
restauré depuis sa sauvegarde exacte, puis le service démarre en 47 s.
Aucun `FIRMWARE_RESTART` supplémentaire, mouvement ou chauffe de récupération.
Une lecture indépendante confirme `ready/standby`, aucune pause, cibles zéro,
candidat désactivé, deux CFS connectés sans route et capteur de tête présent.

Le redémarrage ne retire pas le filament et perd les références d'axes. Le
retrait officiel et le nettoyage sont demandés comme gestes physiques avant
R2. La gestion automatique de cette récupération reste à concevoir ; aucun
retrait à route inconnue ni homing chargé n'est tenté.

## Reprise

R2 a ensuite été exécuté après le second retrait/nettoyage confirmé. Il est
clos avec chargement OK et fin KO : voir le document 90. Le plan était : Après retrait/nettoyage confirmé :
préflight frais, caméra, activation froide exacte, un seul chargement suivi
de pause puis fin candidate. Échec → retour désactivé exact. Une fin T1B après
pause/reprise ne qualifie pas un véritable épuisement T1A → T1B.

[Preuve nettoyée](../inventory/redacted/20260921-cfs-startup-probe-v1/result.json).
La capture brute privée contient les mesures, images, journal borné de 1,8 Mo,
ancien garde exécuté et scripts exacts. Les exemples publics ne contiennent
ni adresse réseau ni identifiants CFS.

Prochaine action immédiate : geste manuel, sans besoin d'un autre agent.
Pour poursuivre la conduite et le diagnostic : GPT-5.6 Sol / high ; Sol / medium
suffit à relire les captures hors machine, avec moins de marge pour corréler
les états concurrents et préparer une récupération physique.
