# Garde du bus RS-485 des CFS (document 80, remède 3 ; ADR-068)

Enveloppe Python du transport série Creality : après toute réponse d'un CFS
dont le dernier octet vaut `F7`, la question suivante attend 300 ms. Rien
d'autre ne change (trame, adresse, délai d'attente). Cause traitée : le CFS 2
n'entend pas une question partie moins de 100 ms après une telle réponse du
CFS 1 ; cinq questions muettes de suite font `key831` et une pause.

## Fichier

`serial_485.py` remplace `/usr/share/klipper/klippy/extras/serial_485.py`
(deux lignes en stock, qui rendent `Serial_485_Wrapper(config)`). La classe
`KctrlSerial485` hérite du transport compilé et enveloppe
`cmd_send_data_with_response`, que le module CFS compilé et
`auto_addr_wrapper.py` appellent tous deux.

## Compteurs, lisibles depuis Mainsail ou par Moonraker

Objet `serial_485 serial485` (`printer/objects/query?serial_485+serial485`,
port 7125 sur la machine ou 4409 depuis le réseau) :

| Champ | Sens |
| --- | --- |
| `kctrl_calls` | questions passées par la garde (monte d'environ 2 par seconde au repos) |
| `kctrl_seen` | réponses dont le dernier octet a été lu |
| `kctrl_last_tail` | dernier octet de la dernière réponse lue, `-1` avant la première |
| `kctrl_marked` | réponses finies par `F7`, chacune ouvre une garde |
| `kctrl_held` | questions retenues (une par garde) |
| `kctrl_unknown` | réponses de forme non reconnue : la garde ne fait alors rien |
| `kctrl_hold_ms` | durée de la garde, 300 |

Au repos, `marked` et `held` restent à 0 : la réponse finie par `F7` est
celle du capteur de filament en veille, pendant une impression. La preuve
décisive est `silences_cfs.py` sur le journal de la prochaine impression
(`scripts/audit-en-direct/bus.sh`, lecture bornée) : zéro question muette
après une trame finie par `F7`, et `kctrl_held` égal à `kctrl_marked`.

## Pose et retour arrière (machine à l'arrêt)

```sh
ssh k1max-root 'cp /usr/share/klipper/klippy/extras/serial_485.py /usr/share/klipper/klippy/extras/serial_485.py.bak-<date>'
cat packages/k1-control-v1/cfs-bus-guard-v1/serial_485.py | ssh k1max-root 'cat > /usr/share/klipper/klippy/extras/serial_485.py'
ssh k1max-root '/usr/share/klippy-env/bin/python -m py_compile /usr/share/klipper/klippy/extras/serial_485.py && /etc/init.d/S55klipper_service restart'
```

Retour arrière : recopier le `.bak-<date>` sur `serial_485.py` et redémarrer
Klipper. Le fichier est dans `/usr/share/klipper` : une mise à jour du
firmware Creality peut le remettre en stock, la ligne « kctrl serial_485:
garde de 300 ms » au démarrage de Klipper dit si la garde est en place.

Tests hors machine : `tests/test_cfs_bus_guard_v1.py` (faux transport).
