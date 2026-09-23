# Fin de retrait — confirmation V3

Correctif ciblé de `end-overlap-v2`. Un seul fichier de la K1 est remplacé :
`/usr/share/klipper/klippy/extras/kctrl_end.py`.

Le 23 septembre, le retrait T1B a reçu `OK[0x0]` après 13,835 s et Thomas
confirme le rembobinage réel. V2 a néanmoins échoué vingt secondes plus tard
avec `rewind_not_confirmed`. `box.T1.filament` est une mémoire du programme :
la primitive de transport ne l'efface pas. La simulation du binaire installé
prouve que le chemin constructeur complet appelle `update_filament_pos`
et remet `box_save.last_cmd` à `None` après le succès.

V3 conserve toute la séquence V2 jusqu'au dernier `M400`. Après les trois
réponses strictement `True`, elle exige une tête vide stable pendant 0,5 s,
une coupe/release prouvée, aucune pause/reprise/erreur et la même route ou aucune.
Elle effectue une fois la mise à jour constructeur, vérifie son résultat puis
observe encore 0,5 s avant la finalisation existante. Aucune relance de retrait,
aucune nouvelle trame, aucun réglage moteur ou thermique modifié.

`remote_install.py` conserve les sauvegardes exactes, les 22 empreintes, le
retour arrière, le redémarrage Klipper et la restauration du mesh/offset sans
mouvement. La récupération du défaut courant n'accepte que V2 installé avec
`failed/rewind_not_confirmed/T1B`, capteur vide, machine froide, arrêtée et sans
mouvement en attente. Elle ne traite pas un retrait interrompu ou non acquitté.
Les références d'axes sont perdues au redémarrage, sans palpation ni déplacement.

Le paquet conserve `physical_validation=false` : la correction logicielle est
testée hors impression ; aucune nouvelle fin physique n'est lancée pour sa pose.
Voir [le compte rendu](../../../docs/96-fin-rewind-not-confirmed-correction.md).
