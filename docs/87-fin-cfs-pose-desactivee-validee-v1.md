# 87 — Fin CFS posée désactivée, machine libre

21 septembre 2026, suite demandée par Thomas : « La fin a été achevée ce matin »
et « AVANCE ». **La récupération manuelle était terminée ; aucun blocage de fin
ne persistait.** Le défaut logiciel encore présent ne devait pas être décrit
comme une machine bloquée.

## Réalisation

Capture privée `inventory/raw/20260921-cfs-end-disabled-install`,
[preuve nettoyée](../inventory/redacted/20260921-cfs-end-disabled-install/result.json).

La lecture fraîche confirme `cancelled`, aucune pause, tête vide, deux CFS
connectés sans route engagée et cibles buse/plateau zéro. Les **24 chemins** du
manifeste correspondent exactement, y compris la porte et les trois JS jusque-là
non relus. La première garde froide s'est arrêtée avant mutation car elle
exigeait à tort un mesh actif et Z −0,04. L'état réel récupéré avait un mesh
inactif et Z à zéro (erreur flottante de −2,8e−17).

La garde a été corrigée et testée : elle accepte explicitement les deux états
froids connus et exige la conservation de la matrice et de l'origine observées.
Elle n'autorise ni une chauffe, ni un mouvement, ni une nouvelle calibration.
Les requêtes à un objet absent peuvent renvoyer `{}` : la collecte utilise la
liste effective des objets pour distinguer absence et module chargé.

Sept fichiers figés ont ensuite été posés, après copies exactes vérifiées.
L'include est passé en dernier. Le service Klipper a été arrêté, son processus
réel a disparu, puis une nouvelle instance est devenue prête. Le restart ayant
modifié la géométrie logique, la pose a restitué une seule fois l'état initial :

```gcode
BED_MESH_CLEAR
SET_GCODE_OFFSET_BASE Z=-0.000000000000 MOVE=0
```

Aucun homing, palpage, recalcul de mesh, déplacement, chauffe, extrusion,
chargement, coupe ou retrait n'a été envoyé. Les configurations constructeur
épinglées, dont `printer.cfg`, sont inchangées. Les destinations remplacées
conservent leurs modes et propriétaires.

## Résultat vérifié

- Deux lectures indépendantes : `ready/standby`, aucune pause ni attente,
  chauffes zéro, axes libérés, tête vide et aucune route T1/T2.
- `kctrl_end` chargé, `enabled=false`, `phase=disabled`, `pending=false`, époque
  zéro et aucune erreur ; la porte publie exactement ce même état.
- Sept empreintes posées exactes ; autres empreintes initiales conservées.
- Une nouvelle connexion confirme les trois hashes JS servis en HTTP, la
  balise Mainsail et le même état froid. Les descriptions START/END/CANCEL
  restent celles des commandes précédentes. L'absence de remplacement est
  appuyée par le module exact désactivé et son code testé ; aucune commande
  physique n'a été appelée pour la vérifier.
- Chrome réel : Bobines affiche « Au repos » et « Aucune impression n'attend
  de choix », avec ses boutons de choix disponibles. Mainsail affiche Standby
  et les deux chauffes à zéro. Aucun bouton d'action n'a été cliqué.
- **92 tests ciblés réussis** pour le paquet corrigé et la fin différée.

Sauvegardes conservées sur la K1 :
`/usr/data/k1-control-v1/backups/cfs-end-ui-disabled-v1`.
Le staging homonyme est conservé comme preuve de cette pose ; ne pas le réutiliser.
Le conducteur exact envoyé sur stdin est archivé dans la capture privée.
Aucun rollback n'a été nécessaire. Le rollback préparé n'est donc pas présenté
comme un rollback réellement exécuté.

## Limite exacte et suite

La machine est libre ; aucune récupération manuelle supplémentaire n'est
requise pour cette pose. L'interface et le module sont installés. **La nouvelle
séquence de fin reste désactivée** : sa pose à froid ne qualifie pas une coupe
et un rembobinage réels après relève.

Suite utile : qualification active sur un petit essai surveillé, avec contrôle
caméra, route T1B constatée, coupe confirmée, retrait unique de la bonne case,
capteur de tête vide, relâchement puis chauffes coupées. Ne pas refaire la
récupération déjà achevée ni redemander un GO pour les étapes techniques de
préparation. La présence humaine utile et l'état visuel restent à établir avant
le premier mouvement de cet essai.

Modèle conseillé : **GPT-5.6 Sol / high** pour le cycle actif et ses contrôles.
Option économique : **Sol / medium** pour la préparation seule ; high reste
préférable lorsque la chauffe et les effets filament sont en jeu.
