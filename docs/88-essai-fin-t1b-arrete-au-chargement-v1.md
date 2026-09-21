# 88 — Essai de fin T1B arrêté au chargement

21 septembre 2026. Thomas confirme le plateau vide, la buse propre et sa
proximité. Il autorise la poursuite de l'essai, puis demande de traiter aussi
le démarrage récurrent : impression d'un CFS qui pousse sans que l'extrudeur
prenne correctement le relais, coupe puis réinsertion. Cette observation est
retenue comme un problème à investiguer, pas écartée au motif que la commande
interne appartient au constructeur.

**Résultat : le départ a échoué ; la nouvelle fin n'a pas été exécutée.**
La récupération manuelle du matin était bien terminée avant cet essai.
L'incident ci-dessous est nouveau, produit pendant le chargement de cet essai.

## Essai et résultat

[Preuve nettoyée](../inventory/redacted/20260921-cfs-end-active-trial/result.json).
Capture privée : `inventory/raw/20260921-cfs-end-active-trial`.

Le candidat est activé après contrôle des empreintes, avec sauvegarde exacte de
sa configuration désactivée. Une vraie nouvelle instance Klipper est confirmée.
Le petit fichier, transféré une seule fois et vérifié par SHA-256, utilise
`START_PRINT EXTRUDER_TEMP=200 BED_TEMP=55`, puis un dégagement et une pause
sans travail supplémentaire. La reprise prévue était `RESUME_BASE`, suivie de
`END_PRINT`. Il ne devait pas reproduire une bobine réellement épuisée.

La porte Bobines confirme le PLA noir et la correspondance T1A logique → T1B
physique, seule correspondance exacte. Un surveillant externe limité à 900 s
lit état et caméra, coupe immédiatement au défaut et ne relance aucun effet.

| Heure K1 | Fait observé |
|---|---|
| 18:04:22 | Départ 55/200 °C, profil `k1_p001_t055_r001_n11x11`, Z sauvegardé +0,065 ; aucune valeur historique imposée. |
| 18:07:09 | Unique appel T0 enveloppé par K1 Control, résolu vers T1B. |
| 18:07:59 | Première étape de prise, avance E5 commandée ; le capteur de tête apparaît présent dans l'échantillonnage suivant. |
| 18:08:46 | `buffer is always full` puis `auto_retry_extruder_gear` interne. |
| 18:08:50 | Contact cutter ; retour confirmé ; relâchement à 18:09:04. |
| 18:09:19 | Nouvelle prise E5, puis nouvelles avances E commandées. |
| 18:10:06 | Tampon encore plein, erreur `key837`, le chargeur abandonne. |
| Après abandon | Le garde du départ arrête avant la ligne d'amorce ; cibles buse et plateau zéro enregistrées avant l'arrêt d'urgence externe. |

La coupe vue par Thomas est donc celle de la relance interne du **chargement**.
Elle ne provient pas du nouveau propriétaire de fin, resté `phase=idle` dans
chaque échantillon. La pause du fichier, `RESUME_BASE` et `END_PRINT` n'ont pas
été atteints. Il n'y a eu ni amorce ni modèle. Une purge réussie n'est pas
attestée par les images ; des avances E commandées ne prouvent pas un débit réel.

Le surveillant a envoyé un arrêt d'urgence après `print_stats=error`.
Klipper a ensuite quitté sur des exceptions TMC et de déconnexion constructeur.
Le message `SET_HOTEND_FAN` inconnu apparaît après l'abandon : il n'explique pas
les deux échecs de prise déjà survenus.

## Retour vérifié

Le premier arrêt du service a renvoyé une erreur car son ancien processus était
déjà absent. Vérification du PID et du hash avant de poursuivre : aucun fichier
n'avait été restauré. Le retour corrigé copie la sauvegarde exacte puis démarre
une nouvelle instance ; aucun `FIRMWARE_RESTART` supplémentaire n'a été nécessaire.

Deux lectures indépendantes confirment `ready/standby`, aucune pause, cibles
zéro, axes libérés, les deux CFS connectés et commande vide. Le candidat est
`enabled=false`, `phase=disabled`. Son hash correspond à la sauvegarde.
Le seul G-code d'essai a été supprimé après contrôle de son hash exact.

**Le capteur de tête reste présent alors que T1 et T2 n'annoncent aucune route.**
Le restart n'est pas un retrait. La machine est accessible et ne chauffe plus,
mais cette situation ne qualifie pas un nouveau départ ni une tête vide.
Aucun mouvement, nouveau chargement, coupe ou retrait n'a été commandé pour la
récupération logicielle. La sauvegarde reste dans
`/usr/data/k1-control-v1/backups/cfs-end-active-trial-v1`.

## Cause : ce qui est démontré et ce qui manque

Le document 79 décrivait déjà ce type de tampon constamment plein et la relance
qui coupe puis recharge. Cela explique la séquence, **pas sa cause première**.
L'attribution au constructeur de l'appel interne n'exclut pas un mauvais
contexte installé par notre départ.

- Le wrapper de T0 appelle une fois le chargeur ; il ne commande pas la boucle
  d'avances/coupe/réinsertion. Les tentatives supplémentaires `_KCTRL_CFS_LOAD`
  ne sont pas atteintes : le garde ADR-066 arrête dès le retour en erreur.
- La température observée pendant les prises est environ 200 °C. Des avances E
  figurent dans les positions commandées, mais aucune mesure de rotation réelle
  de l'extrudeur n'existe dans cette capture.
- Le fichier exact des capteurs émet le même événement de prise depuis chaque
  `SwitchSensor`. La désactivation de l'alarme continue de mettre à jour la
  présence et d'émettre cet événement. La piste d'un mauvais déclencheur n'est
  **pas démontrée** : les arrivées à la tête concordent avec les deux prises,
  à la résolution de quatre secondes du surveillant.
- La pause constructeur abaisse le courant de l'extrudeur à environ 0,28 A.
  Notre START ne contient pas de restauration explicite du courant ; le binaire
  CFS n'a pas de référence aux commandes de restauration/courant recherchées.
  C'est un point à tester sur un départ après pause, pas la cause établie ici :
  cet essai est parti après redémarrage, et le courant durant la prise n'a pas
  été enregistré. Le courant mesuré après récupération est 0,562 A.
- Restent à départager : moteur non entraîné, moteur qui tourne sans accrocher,
  arrivée trop précoce/tardive, résistance du trajet, ou état du tampon incorrect.
  La seule erreur `key837` ne permet pas de conclure à une buse bouchée.

Aucun réglage de courant, de vitesse ou de délai n'a été modifié sur supposition.
Le défaut de démarrage demeure ouvert, tout comme la qualification de fin.

## Mesure suivante préparée

`scripts/audit-en-direct/startup_samples.py` complète le journal existant par
une capture **GET uniquement**, bornée à 900 s et 2 lectures/s au maximum.
Elle garde les deux capteurs, les modes absolu/relatif, le facteur d'extrusion,
les positions commandées et estimées, la vitesse estimée, le courant déclaré,
la route et les températures. Elle refuse d'écraser une capture existante,
limite les réponses à 512 Kio et retire les identifiants CFS.

Les valeurs absentes ne deviennent jamais « moteur arrêté » : objets/champs
omis → erreur ; valeurs nulles → `unavailable_fields`. Ici `stepper_enable`
renvoie `{}` et l'état détaillé du pilote vaut null au repos. Les coordonnées
et vitesses restent des estimations du firmware, pas un capteur physique.

Validation : **113 tests ciblés réussis** ; 10 échantillons froids réellement
lus en cinq secondes. La capture froide valide le connecteur, pas le mouvement
ni la synchronisation. La première lecture du journal brut avait chargé le
fichier entier (400 Mo) et échoué en mémoire dans le processus de lecture ;
les lectures suivantes utilisent une queue bornée, sans nouvelle action moteur.

Suite utile : obtenir une observation précise de la roue de l'extrudeur et
résoudre le filament encore présent avant de définir un nouvel essai court.
Ne pas rejouer ce G-code, ne pas palper avec le filament engagé et ne pas
répéter le démarrage complet pour ajouter des journaux. Le futur essai doit
observer la première prise et s'arrêter avant une nouvelle coupe automatique.
Aucun collecteur installé sur la K1 et aucune modification des moteurs.

Modèle conseillé pour poursuivre le diagnostic : **GPT-5.6 Sol / high**, car il
faut corréler firmware compilé, état réel et observation physique. Sol / medium
convient au simple examen des captures, avec moins de marge pour la conduite
physique. L'observation manuelle de la roue ne demande aucun agent.
