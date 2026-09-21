# 84 — Correctif de fin après relève, préparation hors imprimante

21 septembre 2026. Suite du diagnostic du [document 83](83-fin-apres-releve-t1a-t1b-v1.md),
autorisée par « OK GO pour prochaine étape recommandée ».

**Le correctif est construit et testé hors imprimante. Il est désactivé et non
installé ; le défaut de la fin actuellement installée reste donc présent.**
Aucune connexion à la K1, aucune écriture distante, aucun redémarrage et aucun
effet physique dans cette étape.

## Décision et fichiers

[ADR-069](adr/ADR-069-fin-cfs-apres-releve-route-fraiche-et-coupe-confirmee.md)
est retenue pour le candidat hors imprimante. La fin est confiée à un petit
composant Python du paquet existant, afin de pouvoir attendre après la sortie
du lecteur G-code, recevoir une confirmation de coupe et arrêter les chauffes
même si une commande stock échoue. Une macro composée seulement d'appels
successifs ne fournit pas ces garanties de contrôle.

- `packages/k1-control-v1/owned-start-print-v2/kctrl_end.py` : route fraîche,
  identité du travail, confirmation de coupe, fin différée et gestion des erreurs.
- `packages/k1-control-v1/owned-start-print-v2/k1-control-owned-end-candidate.cfg` :
  réglages désactivés, fichier séparé, aucun include ajouté.
- [Contrat du candidat](../packages/k1-control-v1/owned-start-print-v2/end-after-refill-candidate.md) :
  étapes, délais, limites et prérequis d'installation.
- `tests/test_kctrl_end_after_refill_v1.py` : 66 cas automatisés.
- README du paquet, ADR-069, STATE et HANDOFF : reprise et statut actualisés.

Les trois fichiers installés contrôlés au diagnostic restent inchangés dans le
dépôt : configuration de départ/fin, `kctrl_tool_change.py`, `kctrl_slot_map.py`.
La relève stock reste disponible. Aucun nouveau service, paquet externe, accès
réseau, homing, mesh, palpage ou recalcul n'est ajouté au candidat.

## Ce qui est démontré en simulation

1. Après relève interne T1A → T1B, le cache peut encore contenir T1A : un unique
   rembobinage vise malgré tout **T1B**, lu dans la route CFS. Même contrôle vers
   le second CFS ; la correspondance logique n'est pas appliquée deux fois.
2. Le composant laisse sortir le lecteur du fichier avant de tenter la coupe.
   Il ne force jamais `do_resume_status` à False et ne lance jamais `RESUME`.
3. Une coupe silencieusement refusée, une preuve incomplète ou ancienne et un
   cutter non relâché interdisent le retrait. Les messages sont limités à la
   tentative courante ; `box.cut_pos` n'est pas une preuve (ADR-041).
4. La cible thermique du fichier est conservée : pas de réchauffage inventé
   après annulation, pas de plancher de 200 °C. Les températures et la route
   sont relues après coupe. La fin stock exige tête vide ET route libérée.
5. Erreur, délai dépassé et annulation coupent les chauffes et interdisent
   l'étape suivante. Un double appel ne répète pas les effets. Un ancien
   traitement ne peut pas agir sur un nouveau départ pendant son attente.

Les injections de panne ajoutées pendant la revue ont d'abord échoué, puis
réussi après correction : une erreur arrivée juste avant l'exécution ne doit
pas être effacée ; un changement de consigne ne doit pas être adopté ; la
mesure thermique doit rester valide après coupe ; un nouveau contact cutter
ne doit pas conserver une ancienne preuve de relâchement.

## Vérifications exécutées

| Vérification | Résultat |
| --- | --- |
| Tests propres au correctif | **66/66**, puis tous repris dans la suite complète. |
| Syntaxe Python 3.8 | Analyse AST réussie ; ne remplace pas un test sur l'interpréteur K1. |
| Répartiteur G-code Creality capturé | Enregistrement, paramètres et console multilignes vérifiés sur le fichier privé du 21 août, empreinte épinglée ; test facultatif sur les postes sans cette capture. |
| Suite locale complète, `python -m pytest -q tests` | **1 532 réussis, 2 échoués, 2 échecs attendus, 55 sous-tests réussis** en 10,90 s ; statut global KO connu, pas une suite entièrement verte. |
| Deux échecs sur copie isolée de la base `6fd0f7e` | Les mêmes deux échecs sont reproduits à l'identique, sans le nouveau module ni ses tests. |

Les deux échecs préexistants sont explicitement documentés par la CI existante :

- `test_unload_requires_head_sensor_to_clear` : l'ancien moteur direct ne produit
  plus `head_sensor_not_cleared_after_unload` dans le cas testé ;
- `test_all_canonical_scenarios_are_implemented_once` : le contrat exige
  `end_full_unload`, l'ancien moteur modélise encore `end_keep_engaged`.

Leur correction n'est pas mélangée à cette mission ; aucun test ni réglage CI
n'est assoupli pour masquer ces divergences. Le pytest utilisateur était
accessible avec le lanceur Python autorisé ; aucune dépendance n'a été installée.

## Limites et prochaine étape

La correction logicielle est testée ; **la séquence réelle ne l'est pas**.
Le prédicat compilé `if_in_resume` et la preuve de coupe dans le contexte différé
restent à qualifier sur le firmware exact. Les tests n'ont pas fait tourner
Klipper complet et ne prouvent pas les effets internes des primitives stock.
Le minuteur thermique dépend de la boucle Klipper ; il ne peut pas interrompre
un blocage complet du processus ni garantir l'arrêt d'un moteur CFS autonome.

Une autre limite est rendue explicite : le lecteur peut marquer le fichier
terminé avant la fin différée du retrait. Le module expose son état et annonce
la fin incomplète en console, mais l'interface ne s'y raccorde pas encore.
L'affichage « fin en cours / incomplète » doit être traité avant activation.
Le seul statut `print_stats=complete` ne validera pas le retrait.

**Suite recommandée : qualification à froid, en lecture seule, du firmware et
de l'intégration**, en exploitant d'abord les sources et journaux disponibles.
Produire la liste des points établis et des preuves physiques encore nécessaires,
puis compléter l'affichage et préparer une pose désactivée avec sauvegarde et
retour arrière exacts. Aucun simple passage à `enabled: true` n'est autorisé
par ce document. Une qualification physique restera distincte, avec caméra
et présence humaine utile, sur un essai sans valeur.

Modèle conseillé pour cette suite : **GPT-6 Astra, raisonnement high**, car les
limites concernent le firmware compilé, les événements concurrents et du matériel
réel. Alternative raisonnable : **GPT-5.6 Sol, high**, pour une collecte bornée
et la préparation UI ; garder une revue approfondie avant toute activation.
