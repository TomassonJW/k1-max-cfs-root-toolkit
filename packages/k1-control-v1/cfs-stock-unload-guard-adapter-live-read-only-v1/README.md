# Validation live en lecture seule de l'adaptateur CFS V1

Mission :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`.

Ce paquet lit deux fois les objets utiles de la K1, calcule les empreintes des
trois configurations avant et après, puis valide localement la réponse privée.
Le collecteur ne contient aucune route G-code ni écriture distante.

Avant l'appel à l'adaptateur, le validateur impose la forme exacte observée et
reconstruit une réponse réduite. Les champs `sn` et `uuid`, ainsi que tous les
champs non utiles, ne passent jamais dans l'adaptateur. Un champ nouveau dans
l'état, `box` ou une unité CFS ferme la validation.

La capture brute reste sous `inventory/raw/` et n'est pas versionnée. Seuls son
empreinte et le résultat fonctionnel nettoyé figurent dans `evidence-map.json`.

Verdict : deux lectures stables, adaptation identique, configurations
inchangées et état `BLOCKED_NO_ENGAGED_ROUTE`. `StockUnloadGuard.run` n'est ni
importé ni appelé.
