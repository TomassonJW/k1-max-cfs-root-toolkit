# Démarrage T1B du 23 septembre : prise non confirmée, key837

## Résultat et périmètre

Après la pose du correctif de fin V3, Thomas a pu lancer un nouveau fichier.
Le démarrage échoue avant la ligne d'amorce. Il signale très peu de filament
extrudé, alors que le CFS l'a amené dans la tête. Il n'a pas observé la roue de
l'extrudeur pendant ce départ. Cette observation reste inconnue.

Intervention de diagnostic uniquement : lectures HTTP/SSH, copie des journaux
et des sources exactes. Aucune modification distante, chauffe, extrusion,
rétraction, redémarrage, remise à zéro d'erreur ni arrêt d'urgence.

La cause mécanique ou de commande qui empêche le filament d'avancer normalement
n'est pas encore établie. Aucune correction de ce défaut de prise n'est annoncée.

## Chronologie prouvée

Capture privée : `inventory/raw/20260923-startup-cfs-abandoned-v1/`.
Heures du journal de la K1 :

| Heure | Observation |
| --- | --- |
| 09:31:33 | Un appel T0 est transmis au chargeur, cible physique T1B. |
| 09:32:23 | Signal de prise reçu, avance E5 demandée, réponse CFS OK. |
| 09:33:09 | La réserve reste pleine : `buffer is always full`. |
| 09:33:13–29 | Le chargeur effectue sa relance interne : coupe, retrait, nouvelle insertion. |
| 09:33:43 | Deuxième signal de prise, avance E5 demandée, réponse OK. |
| 09:34:30 | Toujours pleine ; erreur CFS `key837`, puis pause et parc constructeur. |
| 09:34:43 | Le contrôle K1 Control détecte la pause et arrête le départ avant l'amorce. |

`key165` et « CFS qui abandonne » sont le message secondaire de
`_KCTRL_START_STOPPED`. L'erreur d'origine est bien `key837`. La présence de
filament ne prouve pas que les engrenages l'entraînent ni qu'il sort de la buse.

## Pistes vérifiées

### Capteurs

Les deux capteurs indiquent `filament_detected=true`. Celui de la tête affiche
`enabled=false`. Dans le fichier **installé** `filament_switch_sensor.py`, la
présence est actualisée avant le contrôle `sensor_enabled` ; l'événement
`box:extrude_process_stage7` est émis indépendamment de cet indicateur.
Il s'agit donc de l'alarme de manque de filament désarmée, pas d'une lecture
de présence coupée. Les deux signaux de prise du journal le confirment.

Le démarrage réarme l'alarme après le chargement validé. Cette ligne n'a pas été
atteinte puisque le chargeur a échoué. Réactiver simplement l'alarme ne résout
pas la prise et ne prouve pas le débit. Le fichier constructeur ne journalise
pas le nom du capteur à l'origine de chaque événement de prise : cette limite
demeure, comme au document 88.

### Température, courant et communication

- Première prise : cible 200 °C, mesure 202,7 °C ; seconde : environ 200,2 °C.
  Le fichier demandait 195 °C, mais le chargeur avait appliqué son plancher
  de 200 °C. Aucune preuve de commande d'extrusion à froid.
- La garde série affiche `kctrl_marked=0`, `kctrl_held=0`, `kctrl_unknown=0` :
  elle n'a introduit aucun délai depuis le redémarrage. Les demandes utiles
  ont reçu leurs réponses ; ce cas ne ressemble pas aux pertes `key831`.
- Le courant **après la pause** vaut environ 0,281 A. C'est l'état réduit de
  pause, pas une mesure du courant pendant les prises. Les valeurs 0,55 A
  retrouvées avant le départ dans les gros états sont la configuration ; elles
  ne constituent pas une mesure historique d'entraînement. Ne pas en déduire
  qu'un faible courant a causé ce départ raté.
- Les avances E sont des commandes/estimations de logiciel. Sans observation
  de roue ni mesure matérielle, elles ne prouvent pas une rotation ou un débit.

### Dernier correctif et antécédents

Les 22 fichiers protégés sont conformes aux empreintes attendues. Le fichier de
démarrage et le chargeur sont inchangés. Le composant de fin V3 est `idle`,
sans demande de fin, pendant ce travail ; sa nouvelle mise à jour de route
n'a pas été exécutée. La machine avait été vérifiée vide après sa pose.

Le même enchaînement prise → réserve pleine → relance interne → `key837` était
déjà capturé le 21 septembre (document 88). Le chargement suivant avait réussi
sans changement de vitesse ou de courant (document 89). Le correctif de fin
n'avait pas résolu ce défaut intermittent. L'appartenance du chargeur au code
constructeur n'exclut pas un contexte inadapté installé par notre démarrage.

## État réel conservé et prochaine étape

Klipper est `ready`, le fichier est en erreur, aucune pause en cours, aucune
opération de fin en cours. Cibles buse et plateau zéro, mouvements estimés nuls.
Les deux capteurs voient le filament ; les deux CFS sont connectés mais aucune
route n'est validée. Cet état n'est ni « tête vide » ni un chargement accepté.
Il n'a pas été effacé pour faire disparaître le message.

La prochaine étape utile est un diagnostic physique court de l'entraînement,
avec observation de la roue, du débit et mesures du courant, plutôt qu'un nouveau
départ complet suivi des relances automatiques. Le collecteur GET existant
`scripts/audit-en-direct/startup_samples.py` est réutilisable. Il faudra préparer
la récupération du filament et le parcours au bac depuis l'état frais ; aucun
homing/palpage chargé, rétraction aveugle ou simple relance de ce fichier.

Les causes restant à départager sont une prise inefficace, un entraînement
insuffisant, une résistance du trajet ou un état de réserve erroné. Modifier
une vitesse, un courant ou un délai avant cette discrimination masquerait
l'incertitude. Aucun changement logiciel de ces paramètres n'est effectué ici.

Pour préparer cet essai : GPT-6 Sol, raisonnement high. Une simple relecture des
traces peut utiliser Sol medium ; la conduite physique exige la corrélation
des états, des commandes et de l'observation humaine.
