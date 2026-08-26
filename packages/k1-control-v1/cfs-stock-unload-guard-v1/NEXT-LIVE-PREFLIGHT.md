# Prochaine étape proposée — préflight live du garde de retrait

Nom technique proposé :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-LIVE-PREFLIGHT-V1`.

## En langage courant

La prochaine mission devra seulement lire la K1, sans couper, chauffer ni
retirer de filament. Elle vérifiera où trouver réellement les informations dont
le garde a besoin : machine au repos, deux CFS connectés, commande CFS inactive,
slot engagé, fin du retrait et consignes de chauffe.

Cette lecture sert à éviter de brancher le contrôleur sur un champ mal compris.
Elle ne posera aucun fichier sur la K1 et n'enverra aucun G-code.

Un GO exact distinct sera requis parce que cette mission se connectera à la K1,
même si elle restera entièrement en lecture seule. Un retrait réel ultérieur
demandera encore une autre autorisation après revue des preuves.
