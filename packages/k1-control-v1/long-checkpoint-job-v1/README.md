# Job long de checkpoints — candidat hors imprimante

Ce paquet dérive un candidat privé de huit couches depuis le G-code R2 de deux
couches. Il conserve le départ possédé `T1A`, le `11 × 11`, le Z accepté et la
fin sûre, mais ajoute assez de couches pour séparer deux futures fenêtres :

- couche 3 : changement humain `T1A → T2C` ;
- couche 6 : runout humain sur T2 avec remplacement strictement équivalent.

Les fenêtres sont seulement des commentaires déterministes dans le G-code.
Elles ne déclenchent aucune action CFS. Le candidat ne contient aucun `T0`,
`START_PRINT`, `END_PRINT`, `G28` ou commande `BOX_*` exécutable. Sa fin coupe
les chauffes, monte à `Z50`, parque à `X203 Y273`, attend la fin du mouvement,
puis libère les axes.

Ce paquet ne contient ni connecteur, ni upload, ni runner. Il reste bloqué par
le verdict thermique de deux couches, l'identité exacte de `T2C`, la preuve
d'une bobine T2 strictement équivalente et une future gate physique séparée.

Construction locale déterministe :

```powershell
python.exe packages/k1-control-v1/long-checkpoint-job-v1/build_candidate.py
```
