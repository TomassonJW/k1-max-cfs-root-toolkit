# Résultat — préflight live du garde de retrait CFS

Verdict : **mapping OK avec correction du garde ; état actuel non prêt faute de
route engagée ; aucune action physique**.

Deux lectures espacées de deux secondes confirment :

- Klipper `ready`, sans composant échoué ni avertissement ;
- impression `standby` ;
- unités `T1` et `T2` connectées ;
- `box.t_command` vide ;
- aucun slot CFS engagé ;
- consignes buse et plateau à zéro ;
- segment après cutter toujours détecté dans la tête ;
- trois empreintes de configuration identiques avant et après.

La lecture complète de `box` prouve qu'aucun champ direct
`stock_unload_state` n'existe. La capture précédente prouve aussi que
`box.t_command` est resté vide avant, pendant et après le retrait officiel.

Le garde ne peut donc pas attendre un état constructeur fictif. Sa règle est
alignée sur les preuves disponibles : la requête stock doit revenir sans erreur
de transport, la route demandée doit réellement disparaître et `t_command` doit
être vide. Une réponse HTTP `ok` sans libération de route reste KO.

Le premier essai du collecteur est écarté parce que le `curl` Creality a signalé
les options incompatibles `-sS`. Il n'a provoqué aucune action distante. La
seconde capture, sans ces options, est l'unique autorité live de cette gate.

Aucun G-code, chauffage, mouvement, service, restart, fichier distant ou
retrait n'a été produit.
