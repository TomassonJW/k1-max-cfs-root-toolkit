# ADR-074 — Une annulation garde le filament en tête et libère le départ suivant

Date : 2 octobre 2026. Statut : accepté et en service.

## Contexte

Le 2 octobre, après l'annulation d'une impression depuis Mainsail, aucune
nouvelle impression ne pouvait partir. La commande d'annulation stock fait
d'abord `WAIT_EXTRUSION_ALL_MATERIALS`, qui descend la buse à 140 °C, puis
`CANCEL_PRINT`, puis `M84`. La fin V3 différait sa coupe et son rembobinage
derrière cette commande : buse chargée à 140 °C, elle refusait
(`approved_temperature_missing`) ou trouvait les moteurs déjà coupés
(`axes_not_referenced`). Elle restait en `failed`, et le portail de départ
refusait alors tout `START_PRINT`. Un redémarrage de Klipper la libérait, mais
effaçait la route CFS : le départ suivant exigeait de confirmer l'emplacement
à la main (`KCTRL_RETAINED_ADOPT`).

## Décision

`kctrl_end.py` V4 (`cancel-retained-v4`) : une annulation ne coupe jamais et
ne rembobine jamais. Quand la tête est chargée, juste après
`CANCEL_PRINT_BASE`, sous le verrou G-code et sans rien différer :

- tête dans le bac de purge (rectangle X 175..220 au-delà de Y280, ou verrou
  du garde de purge) : sortie vers Y273 à hauteur constante, refusée si le
  plateau est à moins de 30 mm ; jamais de remontée du plateau dans le bac ;
- puis la fin stock `END_PRINT_NO_M84` sans `BOX_END`, `BOX_END_PRINT` ni
  `BOX_GET_FIVE_WAY_STATE`, qui videraient la tête ou effaceraient la route ;
- chauffes coupées et prouvées à zéro, phase `complete`, emplacement relevé
  sur la route CFS en direct (`slot`) et `retained=true`.

Le départ suivant trouve la même route et garde le filament (purge conservée,
ADR-071). Si la route est absente, ambiguë ou contredite par la table, la fin
se libère quand même, n'invente aucun emplacement et le départ demandera de le
confirmer.

Inchangé : tête vide (chemin V3 différé), capteur de tête illisible, carte SD
encore active, annulation pendant une fin déjà en cours (`cancelled_during_end`).

## Conséquences

- Après une annulation, un nouveau départ est possible directement ; le
  filament reste en tête.
- Pour vider la tête, utiliser l'action séparée de désengagement ; une
  annulation ne le fait plus.
- Toute erreur du firmware, coupure ou chauffe non confirmée pendant cette
  fin la laisse `failed`, chauffes coupées : le départ reste bloqué, comme
  avant.
- Pas encore observé sur une vraie annulation : la première sera la preuve.
