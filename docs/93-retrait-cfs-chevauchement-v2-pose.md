# 93 — Pose à froid du retrait coordonné V2

## Récupération après le KO

Thomas a éteint/rallumé puis terminé le retrait depuis l'écran. Le journal
montre que `BOX_CUT_MATERIAL` a été appelé mais a sauté la coupe sur
`filament_sensor false / No filament found`. Le retrait a suivi la branche
CFS seule et reçu `RETRUDE_PROCESS OK[0x0]` après environ 20,27 s. L'absence
de chauffe est cohérente avec cette branche. Le bruit/effort rapporté n'est
pas expliqué par ce seul retour ; aucun constat d'absence de dommage.

La lecture suivante confirme ready/standby, cibles zéro, tête non détectée,
T1/T2 sans route. V1 est revenu idle après reboot : il n'est plus verrouillé
en échec. Buse non nettoyée, plateau propre et haut selon Thomas ; Z non
référencé. Le retrait n'est plus une action humaine en attente.

## Delta autorisé et contrôlé

Le GO suivant couvre la préparation et la pose du correctif. Le delta change
un fichier Python, conserve la configuration active et tous les autres
fichiers protégés. Il rétablit l'attente après E-20, puis le chevauchement
E-15 lent/CFS ; l'attente finale précède les preuves et le parc. Le code
fonctionnel testé au document 92 n'est pas retouché pendant cette pose.

Le paquet `packages/k1-control-v1/end-overlap-v2` contient le manifeste,
l'installateur avec modes de préflight/validation/rollback et leurs tests.
Deux lectures stables peuvent accepter X/Y référencés avant restart, sans
commande pour libérer les moteurs. Le restart doit ensuite laisser tous
les axes non référencés. La position physique Z n'est jamais déduite du zéro
logique. Le profil et la matrice réellement actifs ainsi que les offsets
sont conservés sans mouvement, sans choisir un autre mesh historique.

199 tests ciblés verts : correctif de coordination, garde de fin, historique
V1 et 29 tests de pose. Échecs injectés avant mutation et après restart,
rollback exact vers V1 actif, dérive de fichier, mouvement, température,
version inattendue et altération de matrice couverts hors imprimante.

## Résultat réel

Préflight frais OK : 22 empreintes exactes, deux lectures stables, XY
référencés seulement, cibles zéro, températures environ 30/28 °C, tête vide,
aucune route. Caméra examinée : tête à gauche, plateau haut et libre.
Capture privée : `inventory/raw/20260921-cfs-end-overlap-v2-install`.
Pose `INSTALLED_COLD_OK` en environ 33 s : un fichier remplacé, ancien
processus disparu, nouveau processus confirmé, V2 actif/idle. Aucune
restauration arrière nécessaire. Le contrôle séparé `VALIDATED_COLD_OK`
confirme les 22 empreintes et les octets exacts du backup V1.

Après le reboot manuel de Thomas, aucun profil de mesh n'était actif et les
offsets XYZ étaient zéro. Cet état réel est conservé : aucun ancien profil
historique n'est chargé arbitrairement. Le contrôle de matrice et d'offsets
est vert. Tous les axes sont non référencés, cibles zéro, aucune route ni
commande CFS, tête non détectée. Les lectures HTTP et images avant/après
confirment l'état au repos et aucune modification visible de la position.
Seules les commandes logicielles `BED_MESH_CLEAR` et remise des offsets
avec `MOVE=0` ont été envoyées ; aucune commande physique.

Preuve publique nettoyée :
`inventory/redacted/20260921-cfs-end-overlap-v2-install/result.json`.

La pose froide ne qualifie pas le rembobinage réel. Aucun essai chaud ni
palpage avec la buse actuellement sale. Le chargement intermittent et
l'éventuel dommage mécanique ne sont pas déclarés résolus.

Prochaine étape physique : nettoyage manuel frais de la buse, références
avant insertion, puis cycle intégré supervisé incluant chargement/purge,
coupe/retrait coordonné et preuve de fin avant parc. Aucun rejeu du fichier
d'essai V1 clos KO. Le GO de pose n'est pas une preuve de réussite de ce cycle.
