# 80 — Pauses `key831` : le CFS 2 n'entend pas la question qui suit une réponse du CFS 1 finie par `F7`

Date : 2026-09-15. Analyse le matin, pendant l'impression
`4x1x3SHELL_4x2x4 LU - Topped Rail - MultiBin Shell_PLA_8h16m` lancée le
14 septembre à 23:42:27 sur `T1A`, toujours en cours à 10:27 (85,6 %).
Journaux de Klipper du 10 au 15 septembre, lus en basse priorité et analysés
hors de la machine ; le journal extrait n'entre pas dans le dépôt. Lecture
seule : rien n'a été modifié sur la machine, l'impression n'a pas été touchée.

Conventions, comme le document 70 : **[FAIT]** lu dans un journal ou un fichier,
horodaté ; **[HYPOTHÈSE]** cohérent avec les faits, non démontré ;
**[INCONNU]** non observable ou pas encore observé.

## 0. La question

Thomas, le 15 septembre au matin : `{"code":"key831", "msg":"serial_485
communication timeout", "values": [2]}` revient « sans aucune raison
apparente », l'impression se met en pause, il relance, la machine purge et
perd du filament. « Pourquoi ? Comment éviter ce problème ? » Il soupçonne nos
modifications, et remarque que le CFS 2 ne sert même pas à cette impression
(un filament y est déclaré dans le fichier, mais inutilisé).

## 1. Réponse courte

1. **La pause est décidée par le module CFS de Creality.** Il demande son état
   à chaque CFS branché toutes les 5 s environ, qu'il serve ou non. Après cinq
   questions de suite sans réponse du même CFS, il lève `key831` avec le numéro
   de ce CFS (`values: [2]`) et met l'impression en pause. [FAIT]
2. **Le CFS 2 n'entend pas une question partie moins de 100 ms après une
   réponse précise du CFS 1** : celle de son capteur de filament quand il vaut
   `1`, dont le dernier octet (le contrôle de la trame) vaut `F7`, l'octet qui
   ouvre toute trame. 139 questions sur 139 perdues dans ce cas ; aucune perdue
   après une autre trame. [FAIT] Ce qui se passe dans le CFS 2 reste une
   [HYPOTHÈSE] (section 5).
3. **Cette réponse revient toutes les 5 s depuis 03:45:58** : le CFS 1 a
   signalé une tension du filament `T1A`, et depuis le module interroge son
   capteur, qui répond toujours `1`. Du 10 au 14 septembre, cette valeur n'était
   apparue que dans quatre réponses isolées. [FAIT]
4. **Nos modifications ne sont pas en cause** : aucune des trames en jeu ne
   vient de notre code, et la pause est décidée par le module Creality. [FAIT]
5. **Remède posé** : la question qui suit une réponse finie par `F7` attend
   300 ms (section 6). Posé le 15 septembre à 17:52 (ADR-068), vérifié au
   repos : les questions du module compilé passent par la garde. Preuve
   décisive à la prochaine impression. [FAIT]

## 2. Méthode

- `klippy.log` du 15 septembre, de 00:00:01 à 10:13:28 : lignes des questions
  envoyées aux CFS (`retries = …, cmd = …`) et des trames reçues
  (`Serial_485: got …`), extraites en basse priorité dans un dossier hors du
  dépôt. 38 966 trames reçues, 8 687 questions d'état au CFS 2, 8 683 au CFS 1.
- `scripts/audit-en-direct/silences_cfs.py` (nouveau) : pour chaque question,
  la trame qui la précède sur le fil, l'écart entre les deux, et la réponse du
  CFS visé dans les 1,1 s. Contrôle de chaque trame reçue recalculé (CRC-8,
  polynôme `07`, de l'octet de longueur à la fin des données ; format de
  trame du document 32).
- Journal complet autour de 03:45:58 et des trois pauses.
- Rotations du 10 au 14 septembre : `key831`, questions d'état sans réponse,
  valeurs du capteur.

## 3. Ce que montre le journal

### 3.1 Les pauses

[FAIT] Trois pauses, toutes sur `key831` avec `values: [2]` :

| `key831` | Sortie d'impression | Reprise |
| --- | --- | --- |
| 05:15:21,251 | 05:15:21,887 | 07:51:36 |
| 08:01:10,323 | 08:01:10,415 | 09:01:17 |
| 09:24:23,817 | 09:24:25,186 | 09:39:28 |

Chaque question d'état sans réponse écrit
`communication_get_box_state return false, timeout_times: N`. La première du
lot écrit 4, la cinquième 0 et déclenche `key831` ; une seule réponse efface
le décompte (07:54:31 à 2, puis 4 au silence suivant, à 07:55:35). Avant la
pause de 05:15:21, les cinq questions perdues sont parties à 05:14:59,
05:15:05, :10, :15 et :20, à 24, 3, 20, 40 et 87 ms de la réponse du capteur
du CFS 1. Deux lignes « the same err » (05:15:31, 08:01:46) répètent l'erreur
pendant une pause sans en créer une autre. Jusqu'à 10:13:28, les 159 lignes
`return false` tombent une à une sur les 159 silences comptés en section 3.2.

Après la reprise de 09:39:28, les silences continuent : 37 de 10:14:49 à
10:48:55, dont deux séries de quatre questions de suite (10:26:30 à 10:26:45,
10:46:38 à 10:46:53) ; une de plus, et l'impression repartait en pause.

### 3.2 Quand le CFS 2 n'entend pas

[FAIT] Questions d'état au CFS 2, 15 septembre de 00:00 à 10:13 :

| Trame juste avant la question | Écart | Répond | Sans réponse |
| --- | --- | --- | --- |
| réponse du capteur du CFS 1, finie par `F7` | moins de 100 ms | 0 | 139 |
| la même | 100 à 300 ms | 841 | 20 |
| la même | 300 ms et plus | 188 | 0 |
| toute autre trame | tout écart | 7 499 | 0 |

Contre-épreuves dans le même journal [FAIT] :

- après une réponse du CFS 1 **non** finie par `F7` (état, présence), le CFS 2
  répond aux 8 554 questions parties à moins de 100 ms : ce n'est pas la
  proximité d'une réponse du CFS 1 qui gêne, c'est cette réponse-là ;
- le CFS 1 répond aux 684 questions d'état parties moins de 100 ms après **sa
  propre** réponse finie par `F7` (581 à moins de 10 ms) : seul le CFS qui
  écoute la trame de l'autre est touché ;
- le contrôle de présence du CFS 2 (commande `a2`) tombe de la même façon :
  6 sur 6 à moins de 100 ms après cette réponse ;
- 38 966 trames reçues, aucun contrôle faux : ni le câble ni un parasite
  électrique ;
- les 159 silences du CFS 2 de la journée sont tous des questions parties
  moins de 300 ms après cette réponse.

Les deux questions reviennent toutes les 5 s environ et leur décalage glisse
lentement : quand il passe sous 100 ms, plusieurs questions de suite y tombent,
et la cinquième déclenche la pause.

### 3.3 D'où vient la réponse finie par `F7`

[FAIT] Journal du 15 septembre :

- 03:45:58,664 : réponse d'état du CFS 1 avec le statut `FILAMENT_ERR`
  (`0x50`), `recode_err: filament_err, last_tnn: T1A, tnn: T1A` ;
- 03:45:58,719 : `filament_err_tighten_up_event`, tension du filament ;
- 03:45:58,735 : première question au capteur, `01 04 ff 08 01`, réponse
  `f7 01 04 00 08 01 f7`, lue `Tn_inner_data[T1][filament_sensor][connections]: 1`.

Depuis, une question toutes les 5 s environ, en impression comme en pause :
4 473 jusqu'à 10:13:28, 4 872 jusqu'à 10:47:28, toutes répondues `1`. Dans la
journée : 18 réponses d'état du CFS 1 marquées `FILAMENT_ERR`, un seul
événement de tension, aucun relâchement signalé.

Contrôle de cette réponse selon la valeur du capteur (calcul, même CRC) :
0 → `F0`, 1 → `F7`, 2 → `FE`, 9 → `CF`. Sur les 256 valeurs possibles, seule
la valeur 1 finit par l'octet d'ouverture.

### 3.4 Pourquoi en impression, et pas en pause

[FAIT] Questions d'état au CFS 2 depuis 03:45:58 :

| Machine | Durée | Moins de 100 ms après `F7` | Sans réponse |
| --- | --- | --- | --- |
| en impression | 156 min | 133 | 153 (133, plus 20 entre 100 et 300 ms) |
| en pause | 231 min | 6, toutes dans les 36 s qui suivent le début d'une pause | 6 |

Une fois la pause installée, la question au CFS 2 part 100 à 300 ms après la
réponse du capteur (655 fois, toutes répondues), ou 300 ms et plus après elle,
ou après une autre trame (2 632 fois, toutes répondues) : le rythme des
questions du module n'est pas le même qu'en impression. La veille du capteur,
elle, continue pendant la pause.

### 3.5 Pourquoi jamais avant

[FAIT] Du 10 au 14 septembre, rotations du journal comptées en entier : aucun
`key831`, aucune question d'état sans réponse.

- Réponses finies par `F7` sur le bus, toutes commandes confondues : une le 10,
  une le 11, aucune le 12 ni le 13, cinq le 14, jamais répétées toutes les
  5 s. Dont la
  réponse du capteur à 1 : deux fois du CFS 1 (14 septembre, 20:35:45 et
  22:35:15), deux fois du CFS 2 (14 septembre, 18:24:49 et 18:24:50). Le
  contrôle ne dépend pas de l'adresse : la même valeur finit par `F7` sur les
  deux CFS.
- Le 13 septembre à 12:31:43, même événement de tension sur le CFS 1, même
  veille toutes les 5 s. Le capteur a répondu 2 (`FE`) seize fois, puis 0
  (`F0`) à 12:33:04 ; dès 12:33:43, le module a posé au capteur une autre
  question (`01 04 ff 08 00`), réponse 9 (`CF`), jusqu'à 12:48:48, puis la
  veille s'est arrêtée. De 12:30 à 12:50, 13 questions d'état au CFS 2 sont
  parties moins de 100 ms après une réponse du capteur du CFS 1 (12 finies
  par `CF`, une par `FE`) : 13 réponses, et aucune question sans réponse sur
  les 280 de la fenêtre. Même situation qu'aujourd'hui ; seul l'octet final
  change.

## 4. Nos modifications

[FAIT] Rien de notre code dans la chaîne :

- les questions périodiques (état, capteur, présence) et la décision de pause
  viennent du module CFS de Creality (`box_wrapper`, compilé, et
  `auto_addr_wrapper.py`) ;
- la veille du capteur est déclenchée par le rapport du CFS 1 lui-même ;
- le CFS 2 est interrogé qu'il serve ou non : 8 687 questions d'état ce matin,
  pour une impression sur `T1A`. Le filament déclaré mais inutilisé dans le
  fichier n'y change rien.

## 5. Hypothèses et inconnues

- [HYPOTHÈSE] Dans le CFS 2 : le récepteur prend le `F7` final de la trame du
  CFS 1 pour le début d'une nouvelle trame, avale la question qui suit comme la
  suite de cette fausse trame, et ne se remet à zéro qu'après un silence de
  100 à 300 ms environ. Cohérent avec tous les comptes de la section 3 ;
  firmware du CFS fermé, non observable.
- [HYPOTHÈSE] La tension de `T1A` vient d'une bobine qui frotte, d'une spire
  croisée ou d'un filament qui accroche dans le CFS 1, et la valeur 1 dit
  qu'elle dure : le module attendrait le retour à 0 pour passer à la suite,
  comme le 13 septembre.
- [INCONNU] Ce que signifient les valeurs du capteur, et ce qui arrêtera la
  veille du 15 si la valeur ne repasse pas à 0 (fin d'impression,
  redémarrage).
- [INCONNU] Si la purge de la reprise peut être raccourcie : pas étudié ici.
- [FAIT] L'envoi se laisse envelopper depuis Python (ADR-068, 15 septembre à 17:52).
  `auto_addr_wrapper.py`, lisible, appelle
  `self._serial.cmd_send_data_with_response(data_send, timeout, False)` sur
  l'objet `serial_485 serial485` (interface déjà citée par ADR-036). Le module
  compilé `box_wrapper` contient les mêmes noms (`serial_485 serial485`,
  `_serial`, `cmd_send_data_with_response`) : il appelle très probablement la
  même méthode par son nom. La garde posée compte ses
  questions (`kctrl_calls`, deux par seconde au repos) et lit ses réponses
  (`kctrl_seen`) : les deux modules passent par elle.

## 6. Remèdes classés

| # | Remède | Effet attendu | Qui décide | État |
| --- | --- | --- | --- | --- |
| 1 | Impression en cours : ne rien changer ; si elle repasse en pause, relancer | — | Thomas | fini : impression finie à 12:03 (document 81) |
| 2 | Après l'impression : vérifier que la bobine `T1A` tourne librement et que le filament n'accroche pas ; relire le journal pour voir si la veille du capteur s'arrête | retire le déclencheur du jour, pas le défaut | Thomas, puis lecture seule | à faire |
| 3 | Garde sur le bus : aucune question ne part moins de 300 ms après une réponse finie par `F7`, par une enveloppe autour de l'envoi du transport Creality | supprime ces silences quel que soit le déclencheur ; au plus 300 ms de retard sur la question qui suit une telle réponse | Thomas (« installer, tout niquel », 15 septembre) | **posé le 15 septembre à 17:52** (ADR-068, sauvegarde `serial_485.py.bak-20260915`) ; vérifié au repos : les questions du module compilé passent par la garde (`kctrl_calls`), leurs réponses sont lues (`kctrl_seen`). Impression de 18:02 (document 82) : 0 silence, 0 `key831`, une question retenue et répondue ; le cas du matin ne s'est pas présenté, preuve décisive encore à venir |
| 4 | Contrôle avant et après : `silences_cfs.py` sur le journal de la prochaine impression | preuve : zéro silence après `F7` | — | outil prêt ; au repos après la pose (17:47 à 17:50) : 37 questions au CFS 2, 0 muette, 0 réponse finie par `F7`. Impression de 18:02 : 1 218 questions au CFS 2, 0 muette, 3 réponses finies par `F7` (document 82, section 5) ; à refaire à la prochaine veille du capteur |
