# 91 — Retrait CFS séparé : installé et validé à froid

21 septembre 2026. Autorité utilisateur : « prépare puis installe directement,
GO ». Successeur de la fin refusée au document 90 et d'ADR-070.

## Résultat réel

**Installé et actif**, révision `separated-end-v1`, au repos. Deux fichiers
remplacés, sauvegardes exactes disponibles et vrai nouveau processus Klipper.
Une validation indépendante confirme les 22 empreintes attendues, tête vide,
aucune route engagée, deux CFS connectés, chauffes zéro et axes non référencés.
Aucun mouvement, chauffage, retrait, extrusion, homing, palpage ou impression
n'a été commandé pendant cette mission. Les images avant/après montrent la même
pose, tête vers l'avant gauche. Cela ne qualifie pas la propreté de la buse.

Le profil `default` et les offsets XYZ zéro observés juste avant la pose ont
été conservés par restauration logicielle sans mouvement. Aucun ancien profil
`11 × 11` ni ancien offset n'a été imposé à partir de l'historique.

La pose est close OK. **La nouvelle séquence physique reste à qualifier** ;
`physical_validation=false` dans l'objet installé. Les essais V1/R2 précédents
restent clos et interdits de rejeu.

## Correction

La commande combinée `BOX_RETRUDE_MATERIAL_WITH_TNN` conduisait réellement au
bac avant le retrait. Le successeur remplace cet appel par un dégagement local
du levier à X inchangé, sans Z, deux rétractions explicites, puis les petites
commandes constructeur de rembobinage de la case physique fraîchement résolue.
Les mêmes distances/vitesses d'extrudeur sont conservées. Le déplacement local
Y305,5 → 291,5 sert uniquement à libérer la lame ; ce n'est pas un départ au bac.

Le firmware exact a été testé dans un processus isolé avec faux propriétaire et
faux port série : adresse CFS basée sur 1, lettre de case, trames locales et
retour booléen confirmés. Le successeur exige ce retour positif, puis tête vide
et route libérée stables pendant 0,5 s. L'ancien état de la même case est toléré
au plus 20 s après le retour, car la mise à jour CFS est périodique. Une route
différente, ambiguë ou inconnue échoue. Aucun retry ni reprise automatique.

La fin attend toujours la sortie de la reprise SD ; elle ne se fie pas au cache
logique T1A quand le CFS a basculé sur T1B. Elle conserve la température du job,
contrôle les preuves du cutter et coupe les chauffes au premier échec. Le parc
final existant n'est autorisé qu'après la preuve du retrait.

## Fichiers et retour arrière

Paquet : `packages/k1-control-v1/end-separated-v1/`.
Les seules destinations modifiées sont :

- `/usr/share/klipper/klippy/extras/kctrl_end.py` ;
- `/usr/data/printer_data/config/k1-control-owned-end-candidate.cfg`.

Le manifeste fige les sources, les empreintes avant/après et le déployeur.
Les deux fichiers ont ensuite été normalisés en fins de ligne LF, conformément
au dépôt ; le texte a été prouvé identique, sans redémarrage supplémentaire,
puis les empreintes finales ont été vérifiées indépendamment à nouveau.
Sauvegarde : `/usr/data/k1-control-v1/backups/cfs-separated-end-v1`.
Le mode `rollback` restaure exactement les deux versions antérieures désactivées,
redémarre Klipper à froid, rétablit les références logicielles sans mouvement
et vérifie les empreintes. Son chemin d'échec est testé hors imprimante ; aucun
rollback n'a été nécessaire pendant cette pose.

## Vérifications et suite

- 142 tests ciblés réussis : fin historique, nouveau retrait, installation et
  rollback, y compris états retardés, erreurs, annulation et absence de Z.
- Suite complète : 1 668 réussis, 2 échecs historiques déjà recensés dans la CI,
  2 xfail et 55 sous-tests réussis. Aucune exclusion ajoutée pour ce correctif.
- Deux fichiers installés, 22 empreintes finales et deux sauvegardes vérifiées.
- Observation caméra avant/après : même pose ; aucune validation physique du
  retrait ne découle de cette comparaison.

Prochaine action : préparer un essai physique court utilisant exclusivement le
successeur, avec observation du cutter, du rembobinage complet et du parc final.
Avant toute nouvelle palpation, la propreté de buse devra être confirmée à neuf.
Ne pas relever le plateau depuis une position incertaine ; relire la caméra
et les références réelles avant tout mouvement. Aucun nouvel essai n'a été lancé.
Le défaut intermittent de première prise au chargement reste distinct et non
résolu : aucun réglage moteur n'a été modifié.

Preuve nettoyée : `inventory/redacted/20260921-cfs-separated-end/installation.json`.
Les photos, traces firmware et captures série restent exclusivement privées.
