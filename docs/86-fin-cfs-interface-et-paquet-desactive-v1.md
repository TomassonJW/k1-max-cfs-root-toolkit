# 86 — Affichage de fin CFS et paquet de pose désactivée

21 septembre 2026. Suite autorisée du document 85 par « ok go ».
**Préparation hors imprimante ; aucune connexion, pose ou activation.**

## Comportement préparé

L'état de `kctrl_end` est maintenant publié par `kctrl_print_gate` dans la
lecture déjà utilisée par Bobines. La page autonome et sa fenêtre dans
Mainsail donnent priorité à **Fin en cours**, **Fin incomplète** ou **Fin non
vérifiée**, même si le lecteur du fichier annonce `complete`.

Le message distingue la coupe, le rembobinage et le rangement. Un défaut
d'arrêt des chauffes demande une vérification immédiate, sans affirmer qu'elles
sont coupées. Une perte de connexion retire les commandes de départ et marque
l'observation inconnue. Les requêtes de statut ne se chevauchent plus.

La fenêtre reste réductible afin de permettre l'accès aux commandes d'arrêt
de Mainsail. Une pastille garde l'état visible ; un échec la rouvre. Une
annulation suivie d'une fin correcte ne devient pas une impression réussie.

La porte refuse `SDCARD_PRINT_FILE` et `KCTRL_GATE_CONFIRM` **avant** ouverture
SD ou changement de table lorsque la fin est pendante, échouée ou illisible.
Cela couvre aussi la demande de reprise après coupure. Le contrôle déjà présent
sur `START_PRINT` reste inchangé. Une installation ancienne sans module et le
candidat réellement désactivé gardent leur fonctionnement courant.

Une fin échouée reste bloquante après la sortie du callback. Il n'y a ni bouton
de réessai automatique ni acquittement artificiel ; il faut résoudre l'état
physique puis réinitialiser dans une procédure contrôlée. Cet état est volatile :
un redémarrage ne constitue pas une preuve de récupération.

## Paquet concret

[Paquet et procédure](../packages/k1-control-v1/end-after-refill-install-disabled-v1/README.md),
[manifeste](../packages/k1-control-v1/end-after-refill-install-disabled-v1/manifest.json) et
[plan ordonné](../packages/k1-control-v1/end-after-refill-install-disabled-v1/plan.json).

Le générateur local vérifie les empreintes, copie sept fichiers et produit le
plan. Il ne possède **aucun transport** et n'exécute pas les commandes du plan.
La procédure est préparée pour une exécution contrôlée ultérieure ; elle n'est
pas présentée comme un déployeur automatique déjà éprouvé sur la machine.

Deux fichiers nouveaux, une porte Python et trois JS remplacés, puis l'include
ajouté à la fin de la copie exacte du fichier des macros possédées.
`printer.cfg` reste intact. Le composant reste `enabled: false` et ne remplace
aucune commande START/END/CANCEL. Aucun autre propriétaire n'est activé.

Le manifeste contrôle 24 chemins avant pose : les 16 empreintes du document 85,
quatre bases attendues du dépôt (porte et JS, encore à comparer en lecture fraîche),
deux fichiers nouveaux et leurs deux emplacements possibles de cache, attendus
absents. Une dérive ferme la pose ; elle ne devient pas une mise à jour implicite.

Le plan fixe les sauvegardes exactes, destinations, copies atomiques par fichier,
include posé en dernier, arrêt/démarrage de `S55klipper_service`, constat d'une
nouvelle instance, remise unique du mesh existant et deux validations à froid.
Il impose la résolution du lien `current`, la conservation des métadonnées et
la vérification des backups avant remplacement. Les fichiers remplacés et le
répertoire de sauvegarde ne sont jamais effacés globalement.

Au premier échec après remplacement : restauration des backups vérifiés,
suppression des seuls ajouts de la mission, véritable redémarrage, remise du
profil et vérification des empreintes/absences initiales. Un rollback échoué
laisse Klipper arrêté ; aucun essai filament ne suit.

## Vérifications et limites

- **203 tests Python ciblés réussis** : fin différée, porte, interface et paquet.
- **33 tests Node réussis** : logique et véritable fonction de rendu avec DOM/API
  simulés ; priorité sur `complete`, perte de connexion, réduction et réouverture.
- Paquet réellement construit localement ; empreintes des fichiers sources
  vérifiées et plan enregistré comparé au résultat du générateur.
- Suite complète : **1 590 réussis, 2 échecs historiques, 2 échecs attendus et 55 sous-tests réussis** ; les deux divergences
  historiques du document 84 restent signalées, sans changement d'exclusion.
- Ni test dans le navigateur réel ni vérification sur la passerelle installée
  dans cette étape. Le DOM simulé ne prouve pas le rendu CSS dans Mainsail.
- L'écran tactile Creality conserve ses libellés ; le blocage de son départ
  passe par la commande SD, pas par un remplacement de son interface.
- Un appel direct aux commandes internes peut contourner la porte utilisateur.
- Aucun état physique récent n'est déduit des tests. Le dernier état réel est
  celui du document 85 ; **le défaut de fin installé est toujours présent**.

Fichiers concernés : porte Python, `logic.js`, `bobines.js`, `overlay.js`, leurs
tests, nouveau paquet et tests de paquet, ADR-069, contrat candidat, STATE et
HANDOFF. Le moteur de fin et la configuration installée ne sont pas modifiés.

## Prochaine action

Exécuter le préflight frais puis la **pose désactivée** du paquet, avec validation
à froid et rollback au premier écart. La récupération des empreintes manquantes
fait partie de ce préflight ; ne pas recommencer l'analyse du binaire déjà close.
Cette pose ne chauffe pas, ne déplace pas le filament et n'active pas la correction.
Un essai physique ultérieur, avec caméra et relève réelle, reste nécessaire avant
promotion. Un simple passage à `enabled: true` n'est pas la prochaine action.

Modèle conseillé : **GPT-5.6 Sol, raisonnement high**, pour le contrôle des fichiers
réels, du redémarrage et du retour arrière. Option économique : **Sol, medium**
pour une relecture du paquet uniquement ; conserver high pour l'exécution machine.
