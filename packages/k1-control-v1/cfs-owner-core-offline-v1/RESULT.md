# Résultat du cœur propriétaire CFS hors imprimante V1

Statut : `OFFLINE_OWNER_CORE_CLOSED_GREEN_EFFECTS_UNQUALIFIED`

La matrice canonique obtient `21/21`. Elle prouve que le moteur pur prend et
rend un verrou logique, sépare les départs conserver/charger/changer, choisit un
unique remplacement strictement identique entre les deux CFS et refuse toute
reprise tant que le contexte structuré de pause n’est pas comparé valeur par
valeur.

Le cas positif de fin de bobine passe de `T1A` à `T2A` dans la simulation. Ce
résultat démontre le choix logique inter-CFS, pas un comportement matériel. Les
cas sans candidat, avec deux candidats ou avec une couleur seulement proche
restent tous en pause et fermés.

La valeur précédente de l’auto-remplacement stock est conservée puis restaurée
exactement, qu’elle soit initialement `1` ou déjà `0`. Un changement d’époque de
connexion, une cartographie périmée ou un rappel du propriétaire stock invalide
le verrou. Un effet inconnu n’est jamais rejoué ; une intention déjà consommée
est refusée au second passage.

Les tests ciblés obtiennent `21/21`. La suite complète exécute `654` tests,
dont `651` verts et `3` ignorés connus. Le moteur se relit comme Python 3.8 et
n’importe aucun module de réseau, processus ou transport. Toutes les intentions
restent `dispatchable=false` et les sorties déclarent systématiquement zéro
connexion, G-code, chauffe, mouvement, effet CFS, écriture distante et candidat
de pose.

La preuve S12 nettoyée reste épinglée. Elle confirme deux CFS connectés et
l’auto-remplacement stock actif au moment de la lecture, mais aucune paire
identique réelle. Les paires de la matrice sont synthétiques et ne remplacent
aucune validation physique.

La prochaine gate proposée est
`G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-OFFLINE-V1`. Elle préparera seulement
le garde une tentative / vérification / restauration de l’auto-remplacement
stock. Elle ne joindra pas encore la K1.
