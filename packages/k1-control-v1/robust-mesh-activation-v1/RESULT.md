# Résultat final

Statut : **ACTIVATION_OK ; robuste `6 × 6` actif ; gate close**.

Le préflight frais
`20260827-robust-mesh-activation-v1-authorized-preflight` a exécuté le
programme distant figé par stdin en lecture seule. Il a confirmé :

- Klipper prêt, sans composant échoué ni avertissement ;
- K1 en `standby`, cibles buse et plateau à zéro, axes libérés ;
- Z accepté `−0,04 mm`, chemin Z fermé et deux CFS connectés ;
- profil composite `k1_p001_t055_r001_n11x11` actif avec sa matrice exacte ;
- profil robuste quotidien `k1_p001_t055_r001_n06x06` présent avec son
  empreinte exacte ;
- toutes les empreintes de configuration attendues exactes ;
- aucune commande G-code, écriture distante, action de service, chauffe ou
  mouvement avant l'effet autorisé.

La capture `20260827-robust-mesh-activation-v1-authorized-run` a ensuite envoyé
une seule fois :

`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n06x06`

Sa relecture immédiate a obtenu `ACTIVATION_OK` : profil actif `6 × 6`, matrice
exacte `c3c7a2ba…`, aucune modification de configuration, cibles zéro, axes
libérés et état `standby`. Aucun rollback n'a été nécessaire.

La capture indépendante
`20260827-robust-mesh-activation-v1-independent-validation` a enfin obtenu deux
lectures stables avec le même profil et la même matrice. Elle confirme aussi le
Z accepté `−0,04 mm`, les deux CFS connectés sans commande active et l'absence
d'effet supplémentaire.

Le GO exact est consommé. Cette gate ne doit pas être rejouée. Le profil robuste
quotidien est `k1_p001_t055_r001_n06x06` ; le `11 × 11` reste la source
composite physique immuable et n'est pas promu à cause de son KO sévère aux
bords.

Vérifications locales finales : `22/22` tests ciblés activation et CLEAN-MOTION
verts ; suite complète de `513` tests, dont `510` verts et `3` ignorés connus ;
`32/32` scripts PowerShell versionnés relus sans erreur.
