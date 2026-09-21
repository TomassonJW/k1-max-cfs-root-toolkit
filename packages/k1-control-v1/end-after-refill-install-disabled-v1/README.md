# Pose désactivée de la fin CFS après relève — paquet de préparation

Mise à jour du 21 septembre : **posé désactivé et validé à froid**, document 87.
La préparation ci-dessous reste la procédure de référence ; ne pas rejouer les
dossiers déjà consommés. Le générateur reste **hors imprimante**. Il contient sept fichiers figés, leurs
empreintes, un plan ordonné de sauvegarde/pose/retour arrière et un validateur
pour les lectures à froid. Il ne contient aucun transport SSH et n'exécute
aucune commande du plan. Ce n'est pas un déployeur automatique.

## Construire et relire

Depuis la racine du dépôt :

```powershell
python packages/k1-control-v1/end-after-refill-install-disabled-v1/build_package.py --output .codex-work/cfs-end-disabled-review
```

Le dossier doit être neuf. Le générateur refuse toute empreinte source différente
avant de créer le dossier. `plan.json` contient les commandes exactes en tant que
données ; ne pas les exécuter en bloc en ignorant les contrôles intermédiaires.
Aucun paramètre ne permet l'activation.

## Delta exact

- Ajout de `extras/kctrl_end.py` et de la configuration `enabled: false`.
- Remplacement de `extras/kctrl_print_gate.py` et de trois fichiers Bobines :
  `logic.js`, `bobines.js`, `overlay.js`.
- Ajout d'un include **à la fin** de la copie du fichier de macros possédées.
  Tous ses octets initiaux sont conservés. `printer.cfg` reste inchangé.
- Aucun changement du binaire CFS, de nginx, de Mainsail, du mesh enregistré,
  de la consigne Z, de l'auto-remplacement ou des propriétaires historiques.

Le registre des macros existe à `klippy:connect`. `kctrl_end` observe
`klippy:ready` mais, désactivé, ne reprend aucune commande et n'accroche pas la
console. La porte de départ est compatible avec un module absent ou désactivé.

## Préflight obligatoire avant une future pose

Toute nouvelle pose doit exécuter ces contrôles, puis le plan. La préparation initiale du
document 86 ne les avait pas exécutés ; leur exécution réelle est consignée au document 87.

1. Réserver un créneau sans lancement externe. Lire un état complet, récent
   (moins de cinq secondes avant l'arrêt du service), puis appliquer
   `validate_cold(status, installed=False)` : prêt, aucun travail/pause/choix
   en attente, deux chauffes à zéro, axes libérés, tête vide, deux CFS connectés
   et sans route. Conserver la géométrie observée : soit le profil
   `k1_p001_t055_r001_n11x11` et Z `−0,04`, soit mesh inactif et Z zéro
   comme constaté après la récupération manuelle du 21 septembre.
   Conserver la matrice du mesh et l'origine complètes comme référence.
2. Lire les 24 chemins de `manifest.before` et appeler `check_hashes`.
   Une clé absente dans une réponse n'est **jamais** une preuve de fichier absent.
   Pour les nouveaux chemins, exiger une absence constatée, pas une erreur SSH.
   Les 16 empreintes du document 85 proviennent d'une lecture réelle ; celles
   de la porte et des trois JS sont les bases attendues de `main`, **pas une
   nouvelle lecture de la K1**. Tout écart arrête la pose avant remplacement.
3. Résoudre le lien `current` vers son dossier de version, enregistrer ce chemin
   et empêcher un changement de version pendant l'opération. Les commandes
   utilisant `current` sont exécutées seulement tant que sa cible reste identique.
4. Vérifier que les dossiers de sauvegarde et de staging du plan n'existent pas.
   Les créer une seule fois ; transférer les sept fichiers, vérifier leurs hashes
   côté K1. Enregistrer propriétaire, groupe et modes des destinations existantes.
5. Faire toutes les copies `cp -p` du plan et comparer chaque sauvegarde à son
   empreinte de départ. Sauvegarder aussi `printer.cfg` comme preuve indépendante,
   sans le modifier. Aucun arrêt/remplacement tant que ces contrôles ne passent pas.

## Pose et validation à froid

1. Arrêter `/etc/init.d/S55klipper_service`, vérifier son arrêt réel. Installer
   les sept fichiers à leur destination figée ; la configuration portant
   l'include passe en dernier. Mode des nouveaux fichiers : `0644` ; conserver
   les métadonnées enregistrées des fichiers remplacés (le plan suppose le
   propriétaire root existant, à contrôler avant exécution).
2. Démarrer le service. Exiger disparition de l'ancien processus/socket puis
   nouvelle instance prête dans les 60 secondes. `FIRMWARE_RESTART` ne recharge
   pas les modules Python et ne suffit pas.
3. Si le restart a changé la géométrie logique, restaurer une seule fois
   celle capturée avant pose : profil actif existant ou `BED_MESH_CLEAR`,
   puis `SET_GCODE_OFFSET_BASE Z=<valeur capturée> MOVE=0`. Ne pas imposer
   un mesh actif à une machine qui n’en avait pas. Aucun nouveau palpage.
4. Vérifier les sept empreintes posées et les empreintes inchangées ; faire
   deux lectures indépendantes et appliquer
   `validate_cold(after, installed=True, reference=before)` à chacune.
   Le nouveau module doit être `disabled`, `pending=false`, époque zéro,
   sans échec, et la porte doit publier exactement le même état.
5. Confirmer que START/END/CANCEL restent les handlers précédents, avec le
   registre réel/journal et la configuration ; l'aide Moonraker seule n'identifie
   pas un handler. Aucun appel d'essai à START, END, CANCEL ou BOX.
6. Recharger Mainsail et `/bobines/` ; vérifier les nouveaux fichiers servis,
   l'accès normal à Bobines et l'absence de lancement. Les captures de rendu
   locales ne remplacent pas cette vérification sur la passerelle installée.

Tout échec après un premier remplacement conduit au retour arrière. Aucun
chargement/retrait/chauffage, homing ou recalcul de mesh n'est inclus.

## Retour arrière

Suivre `plan.rollback` : service arrêté, copies des backups vérifiés, suppression
**uniquement** des deux nouveaux fichiers et des deux chemins de cache du nouveau
module préalablement constatés absents. Ne pas supprimer un répertoire de caches.
Retirer les éventuels fichiers `.kctrl-next` de cette tentative seulement après
vérification de leurs chemins. Restaurer les modes/propriétaires d'origine.

Redémarrer réellement, restaurer la même géométrie logique une fois, vérifier toutes les
empreintes et absences initiales, puis `validate_cold(installed=False,
reference=before)`. Conserver la sauvegarde et les preuves ; ne pas les écraser
lors d'une reprise. Si ce retour échoue, laisser Klipper arrêté et signaler KO.

## Limites avant activation

La pose désactivée conserve le comportement de fin actuellement installé,
donc son défaut. Elle qualifie uniquement le chargement et l'affichage au repos.
Le candidat actif, le retrait avec TNN explicite après relève et l'arrêt thermique
physique restent à qualifier avec caméra. L'écran Creality n'affiche pas cette
nouvelle interface ; sa demande de départ passe néanmoins par la garde SD.
Un accès direct à des commandes internes peut contourner la porte utilisateur.

Une fin en échec interdit les nouveaux départs normaux même après arrêt du
callback. Aucune commande de réessai/d'acquittement n'est ajoutée : récupération
physique contrôlée et constat frais avant de réinitialiser l'état. Le redémarrage
seul efface cet état volatile ; il ne prouve aucune récupération physique.
