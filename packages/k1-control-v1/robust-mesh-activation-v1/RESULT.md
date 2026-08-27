# Résultat provisoire

Statut : **PREFLIGHT_OK ; activation non exécutée**.

La capture privée
`20260827-robust-mesh-activation-v1-preflight` a exécuté le programme distant
figé par stdin en lecture seule. Elle confirme :

- Klipper prêt, sans composant échoué ni avertissement ;
- K1 en `standby`, cibles buse et plateau à zéro, axes libérés ;
- Z accepté `−0,04 mm`, chemin Z fermé et deux CFS connectés ;
- profil composite `k1_p001_t055_r001_n11x11` actif avec sa matrice exacte ;
- profil robuste quotidien `k1_p001_t055_r001_n06x06` présent avec son
  empreinte exacte ;
- toutes les empreintes de configuration attendues exactes ;
- aucune commande G-code, écriture distante, action de service, chauffe ou
  mouvement.

La seule suite autorisable par cette gate est une charge runtime unique du
robuste suivie de sa relecture. Elle attend encore le GO exact
`GO G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`.

Vérifications locales : `11/11` tests ciblés verts, suite complète de `502`
tests verte avec `3` ignorés connus, programme distant compatible Python 3.8,
script PowerShell relu sans erreur et activation sans drapeaux bloquée avant
toute création de capture ou connexion.
