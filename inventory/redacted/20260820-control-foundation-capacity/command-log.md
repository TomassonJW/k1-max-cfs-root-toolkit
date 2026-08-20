# Journal de commandes classées sans effet

Date : 2026-08-20

La cible SSH exacte et ses identifiants restent hors Git. Les commandes ont été
envoyées en mode non interactif par l'alias local dédié.

| Classe | Commande distante | Résultat | Effet machine |
|---|---|---|---|
| mémoire noyau | `cat /proc/meminfo` | OK | lecture seule |
| processus | `ps w` | OK | lecture seule |
| ports TCP | `netstat -lnt` | OK, absence de pile TCP6 signalée par BusyBox | lecture seule |
| version Python | `/usr/share/klippy-env/bin/python --version` | OK | lecture seule |
| stockage persistant | `df -h /usr/data` | OK | lecture seule |

Aucun fichier distant n'a été créé, modifié, copié vers la machine, renommé ou
supprimé. Aucun service, chauffage, moteur, calibration ou impression n'a été
commandé.
