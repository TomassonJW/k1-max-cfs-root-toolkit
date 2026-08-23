# G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1

Correctif séparé de compatibilité avec le `prtouch_v3` exact de la K1 Max.

La première grille réelle `9 × 9` a prouvé que le wrapper Creality ignore la
taille dynamique attendue par Klipper et conserve le `probe_count` chargé depuis
`printer.cfg`. Le correctif ajoute un composant Moonraker qui commute cette
unique valeur après backup et avant chauffe, redémarre Klipper, relit la valeur
chargée et vérifie toutes les gardes. Dès que les chauffes sont coupées, il
restaure la valeur précédente et revérifie le redémarrage.

La pose elle-même ajoute uniquement le composant et remplace le
`moonraker.conf` dédié par la même configuration avec sa section. Elle redémarre
seulement `S56k1_control_moonraker` et ne touche ni `printer.cfg`, ni Klipper, ni
les chauffes, ni les axes, ni les meshes, ni le Z.

Le rollback restaure le `moonraker.conf` exact, retire le composant et redémarre
seulement le Moonraker dédié. Si une campagne interrompue avait laissé un
`probe_count` temporaire, le backup exact de cette campagne reste l'autorité de
récupération.
