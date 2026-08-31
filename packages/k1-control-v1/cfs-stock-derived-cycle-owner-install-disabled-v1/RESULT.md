# Résultat — cycle stock-derived install-disabled V1

Statut : **candidat hors imprimante, désactivé, non installé**.

Le cutter n'est plus une abstraction. La configuration capturée fixe
`pre_cut X38/Y230`, `cut X38/Y303,2`, un offset `1,3` et une vitesse `7000`.
La trace réelle prouve que la tête reste à `X38/Y304,5` pendant le retrait CFS
et la traction locale `−20 mm`; elle ne quitte la butée qu'après la libération
du filament. Le composant exige désormais `cut_pos=1` avant le retrait, reste à
la butée pendant toute la commande directe, puis exige `cut_pos=0` après le
retour à `Y230`.

La purge et la ligne de départ reprennent également les données retenues : bac
`X185,5/Y305/Z30`, décrochage `X203..206` sur `Y305/Y304` à `Z32`, puis ligne
stock `Y20..180` et dégagement relatif `Z+5` demandé. Aucun appel `BOX_*`,
`G28`, palpage ou recalcul de mesh n'est présent dans les effets filament.

Le roulement automatique vers une bobine identique reste une capacité requise.
Le garde refuse une quasi-correspondance, plusieurs candidates ou une pause non
verrouillée. La sélection complète et la reprise exacte resteront possédées par
l'orchestrateur Moonraker afin d'éviter une concurrence avec l'auto-remplacement
stock.

La matrice locale contient maintenant `16/16` scénarios, dont le refus de
rejouer un ticket après une issue incertaine. La pose désactivée prévue
ajoute deux fichiers et un include, redémarre seulement Klipper puis remet le
meilleur `11 × 11`. Son déployeur réversible passe la lecture PowerShell et le
mode `Plan` ; un `Preflight` sans la gate exacte est refusé avant toute
connexion. La pose n'est pas exécutée et aucune activation n'est autorisée.
