# ADR-068 — La garde du bus est posée : la question qui suit une réponse finie par `F7` attend 300 ms

Date : 2026-09-15

Statut : **acceptée** (« tu peux faire tout ce qui reste a faire, installer,
tout niquel », Thomas, le 15 septembre) ; posée le 15 septembre à 17:44, puis
avec ses compteurs à 17:47 et sous sa forme finale à 17:52, machine au repos,
sauvegarde `/usr/share/klipper/klippy/extras/serial_485.py.bak-20260915` (le
stock, deux lignes) ; vérifiée au repos ; première impression sous la garde le
15 septembre de 18:02 à 18:28 (document 82) : 1 218 questions au CFS 2, 0
muette, 0 `key831`, une question retenue et répondue ; **preuve décisive
encore à venir**, le cas du matin (rapport du capteur en veille toutes les
5 s) ne s'est pas présenté.

## Contexte

Trois pauses `key831` le 15 septembre (05:15, 08:01, 09:24), hors de notre
code (document 80). Le module CFS de Creality interroge chaque CFS toutes les
5 s environ ; le CFS 2 n'entend pas une question partie moins de 100 ms après
une réponse du CFS 1 dont le dernier octet, le contrôle de la trame, vaut
`F7`, l'octet qui ouvre toute trame : 139 questions sur 139 perdues dans ce
cas, aucune après une autre trame. Cinq questions muettes de suite et le
module met l'impression en pause. La réponse en cause est celle du capteur de
filament du CFS 1, en veille depuis une tension de `T1A`.

Le transport série est compilé (`serial_485_wrapper…so`), mais Klipper le
charge par `serial_485.py`, deux lignes en Python, et `auto_addr_wrapper.py`,
lisible, l'appelle par `cmd_send_data_with_response(data, timeout, False)`
sur l'objet `serial_485 serial485` ; le module compilé porte les mêmes noms.

## Décision

1. `serial_485.py` est remplacé par
   `packages/k1-control-v1/cfs-bus-guard-v1/serial_485.py` : `KctrlSerial485`
   hérite du transport et enveloppe `cmd_send_data_with_response`.
2. Après toute réponse dont le dernier octet vaut `F7`, la question suivante
   attend jusqu'à 300 ms (`reactor.pause` depuis le fil principal de Klipper,
   `time.sleep` depuis un autre fil), puis la garde est levée : une seule
   attente par réponse. Trame, adresse et délai d'attente restent ceux du
   module.
3. La forme de la réponse n'étant pas documentée, `last_byte` accepte octets,
   liste d'entiers, dictionnaire portant `#msg` ou objet portant `msg`, et ne
   retient rien s'il ne la reconnaît pas (compteur `kctrl_unknown`).
4. `get_status` expose les compteurs dans l'objet `serial_485 serial485`,
   lisibles par Moonraker, donc depuis Mainsail ou par
   `printer/objects/query?serial_485+serial485` : `kctrl_calls`,
   `kctrl_seen`, `kctrl_last_tail`, `kctrl_marked`, `kctrl_held`,
   `kctrl_unknown`, `kctrl_hold_ms`.

## Preuves

- Hors machine : 8 tests sur faux transport
  (`tests/test_cfs_bus_guard_v1.py`), suite complète verte hors les deux
  rouges volontaires de la CI.
- Sur la machine, au repos, après la pose de 17:52 (Klipper prêt à 17:52:55,
  « kctrl serial_485: garde de 300 ms apres une reponse finie par 0xF7 » au
  journal, aucune erreur, 102 Mo de mémoire disponible) :

  | Heure | `kctrl_calls` | `kctrl_seen` | `kctrl_last_tail` | `marked` / `held` / `unknown` |
  | --- | --- | --- | --- | --- |
  | 17:53:07 | 44 | 30 | 230 | 0 / 0 / 0 |
  | 17:53:27 | 83 | 57 | 29 | 0 / 0 / 0 |
  | 17:53:47 | 121 | 87 | 29 | 0 / 0 / 0 |

  `calls` monte de deux par seconde environ : les questions du module compilé
  et de la boucle d'adressage passent par la garde [FAIT] ; l'hypothèse de la
  section 5 du document 80 est levée. `seen` monte avec elles : la forme de
  la réponse est lue (`auto_addr_wrapper.py` traite le retour comme des
  octets ; le journal montre chaque réponse sous `Serial_485: got {'#msgid':
  …, '#msg': b'…'}`, et `last_byte` lit les deux formes). Les derniers octets
  vus, `E6` et `1D`, sont des octets de contrôle plausibles ; `unknown`
  reste à 0. La différence `calls − seen` vient des questions sans réponse de
  la boucle d'adressage (`Error: no response`, adresses 3 et 4 absentes).
- `marked` et `held` restent à 0 au repos : aucune réponse finie par `F7`
  dans la fenêtre. `silences_cfs.py` sur les trames de 17:47 à 17:50
  (`bus.sh`, lecture bornée) : 37 questions au CFS 2, 0 muette, 0 réponse
  finie par `F7`. La garde n'avait alors pas encore eu à retenir une question.
- Impression de 18:02 (document 82, section 5) : trois réponses finies par
  `F7`, dont le rapport du capteur du CFS 1 à 18:06:24 ; la question suivante
  est partie 314 ms après et a eu sa réponse en 8 ms (`kctrl_held` 1) ; les
  deux autres questions venaient d'elles-mêmes après 800 ms. 1 218 questions
  au CFS 2, 0 muette. Le rapport en veille toutes les 5 s, avec la question
  au CFS 2 juste derrière, ne s'est pas produit : preuve décisive à venir.

## Conséquences

- Au plus 300 ms de retard sur la question qui suit une réponse finie par
  `F7` ; tout le reste du bus est inchangé, la boucle d'adressage aussi.
- Retour arrière en une commande : recopier le `.bak-20260915` sur
  `serial_485.py` et redémarrer Klipper.
- Le fichier est dans `/usr/share/klipper` : une mise à jour du firmware
  Creality peut le remettre en stock ; la ligne « kctrl serial_485: garde »
  au démarrage de Klipper dit si la garde est en place.
- Vérification à la prochaine impression : `kctrl_marked` > 0 et
  `kctrl_held` égal à `kctrl_marked`, aucune pause `key831`, puis
  `silences_cfs.py` sur la sortie de `bus.sh` : zéro question muette après
  une trame finie par `F7`.
- [INCONNU] Si le CFS 2 manque encore des questions après la garde, le
  silence nécessaire est plus long que 300 ms (`HOLD_S` dans le fichier) ou
  la cause est ailleurs ; `silences_cfs.py --detail` le dira.

## Voir aussi

- Document 80 — pauses `key831`, méthode et remèdes
- Document 81 — fin d'impression en boucle, lectures bornées
- ADR-036 — propriétaire CFS direct sur transport série borné (interface du
  transport)
- ADR-067 — la fin d'impression vide la tête avant la fin stock
