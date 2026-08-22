# FIRST-CALIBRATION-V2

V2 corrige le défaut de preuve rencontré par V1 sans modifier le code PR Touch
constructeur. La pile active a produit 209 contacts pour 72 points : le filtre
interne écarte les très gros faux contacts, mais deux maillages restent trop peu
robustes pour un seuil maximal de `0,025 mm`.

Le protocole exécute exactement six maillages `6 x 6` dans un même contexte
thermique. Les trois premiers et les trois derniers forment deux groupes
indépendants. Chaque groupe est réduit par médiane point par point. Les deux
médianes doivent respecter simultanément : moyenne absolue `<= 0,020 mm`, RMS
`<= 0,025 mm` et maximum `<= 0,060 mm`. Aucun septième passage automatique
n'existe.

Après qualification seulement, la médiane point par point des six passages est
chargée par l'endpoint Klipper `update_mesh`, relue, comparée exactement puis
enregistrée sous `k1_p001_t055_r001_n06x06`. Le backup exact et le rollback
restent obligatoires. Le chemin Z conserve ses paliers séparés et son
acceptation observable.
