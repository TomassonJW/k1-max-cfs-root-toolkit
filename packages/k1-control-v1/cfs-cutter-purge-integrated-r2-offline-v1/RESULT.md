# Résultat — CFS cutter/purge integrated R2 hors imprimante

La séquence décrite par Thomas est maintenant figée comme un **delta de la
séquence officielle réellement observée**, et non comme une chorégraphie
inventée. Le moteur refuse notamment le filament avant les références, un profil
thermique approché, un mesh autre que `11 × 11`, une palpation après insertion,
un effet `BOX_*`, un retrait sans cutter, une purge sans `3 ou 4` allers-retours
et preuve caméra, la ligne approximative `Y120`, ou un `G28` complet en fin.

La géométrie de ligne retenue vient de la source constructeur capturée :
`X0,1/X0,4`, `Y20..180` et deux passages de `10 mm`. La baisse relative du
plateau de `5 mm` est enregistrée séparément comme correction demandée ; elle
n'est plus attribuée à tort à la macro stock. La calibration
multi-températures est séparée du print et reste accessible par une action K1
Control dédiée.

La carte `stock-sequence-delta.json` vérifie une impression mono-filament
complète et une P5 complète à changement unique. Elle classe chaque tranche en
`KEEP`, `REPLACE` ou `ADD_EXPLICIT_CORRECTION`. Aucune impression supplémentaire
n'est nécessaire pour découvrir le cutter, le bac, la purge, la ligne ou la
reprise.

Le roulement de bobine identique est également conservé. Le validateur intègre
maintenant un runout automatique `T1A → T2D`, avec identité stricte approuvée,
candidat unique, température G-code inchangée, propriétaire stock exclu et
reprise du contexte. Les cas de quasi-correspondance, ambiguïté ou double
propriétaire sont refusés.

La matrice locale contient `35` scénarios. Les quatre parcours positifs couvrent
`3` et `4` allers-retours ainsi que le repli CFS complet. Les refus couvrent les
frontières de géométrie, température, cutter, purge, caméra, changement et fin.

Le paquet n'a aucun transport, aucune macro installable et aucun candidat de
pose. Le port direct de la chorégraphie stock reste à implémenter puis à
qualifier physiquement avant toute installation active.
