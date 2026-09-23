# Retained start V1 — reprise réelle validée, température corrigée à froid

Statut : **installé et validé à froid le 23 septembre 2026**. Le déployeur
transactionnel est testé ; le manifeste indique `installer_ready=true`.
Son champ statique `installed=false` n'est pas un reçu d'état distant : la
preuve de pose est `inventory/raw/20260923-retained-start-install-v1/`.

La nouvelle règle de Thomas autorise le homing avec filament engagé après
nettoyage manuel confirmé à 150 °C, puis retour à la température de contact
prévue. Les références XYZ doivent être présentes avant toute action au bac.
Le prochain départ doit prouver un homing frais, pas réutiliser un Z supposé.

- `kctrl_start_policy.py` : décisions pures, garde de volume, trajet de
  décrochage en Y et conversion du débit du filament.
- `kctrl_purge_guard.py` : candidat de contrôle après mesh/offset, sur tous les
  mouvements cinématiques ; refus avec arrêt thermique, sans M112.
- `kctrl_bin_motion.py` : candidat préservant le calcul constructeur de
  descente/retour, avec marge de 35 mm et sortie avant restauration Z.
- `kctrl_start.py` : identité avant les effets, preuve de homing frais,
  courant nominal relu, branche normale ou purge conservée sans commande T.
- `kctrl_start_context.py` : lecture bornée des limites du filament dans le
  fichier Orca et contrôle que le fichier ne change pas pendant le départ.
- `integration.py` et `build_candidate.py` : construction déterministe du
  fichier de départ candidat et de `manifest.json`. Le fichier installé
  est reproduit à son empreinte exacte avant transformation, **inclusion de
  fin V3 comprise**. Cinq modules ajoutés et une configuration remplacée.

Validation : **376 tests ciblés verts**, comprenant les deux poses/restaurations,
les sélections répétées et les régressions de fin V3,
changement d'outil, pause et amorce, le rendu Jinja et la grammaire Python 3.8.
Les tests utilisent de faux objets et aucun transport imprimante. Une sonde
distincte dans un processus isolé a confirmé les méthodes du binaire exact,
avec faux transport et sans instance Klipper ni effet physique.

Le candidat restaure les vitesses normales, purge 140 mm à au plus 6 mm/s
selon le fichier, puis effectue trois allers-retours Y291,5/Y305 et sort à
Y273 avant toute remontée. Le mode PRINT est acquitté ; le tampon doit montrer
une consommation. Cela ne remplace pas la confirmation visuelle du débit et
du décrochage. La route constructeur n'est écrite qu'après cette séquence.

L'attribution `KCTRL_RETAINED_ADOPT SLOT=T1B` est une action explicite sans
mouvement, chauffe ou trame CFS, utile quand un redémarrage a effacé la preuve
de la bobine physique. Le choix du prochain fichier ne peut pas la remplacer.
Une prise ratée attribuable dans le même processus peut servir au départ
suivant ; une coupe ou opération manuelle de filament invalide cette preuve.

`remote_install.py` vérifie les fichiers protégés, sauvegarde la configuration,
ajoute les cinq modules et redémarre Klipper. Une erreur de copie/démarrage
restaure les sources exactes ; une modification étrangère interdit ce rollback.
Il remet le mesh et les offsets sans inventer de références XYZ. La validation
indépendante après pose est verte ; la fin V3 reste inchangée.

Thomas a confirmé le cycle réel complet : purge du filament T1B conservé,
amorce, carré de deux couches et retrait. La fin V3 est complète et libérée.
L'essai ne requalifie pas une nouvelle insertion depuis une tête vide.

Le T0 après amorce déduisait à tort une couche ultérieure du relevage Z et
remontait de 195 à 200 °C. `kctrl_start.py` conserve désormais la consigne sur
une sélection déjà confirmée du même outil, avec preuve du travail, des caches,
des capteurs et de la route. Les vrais changements gardent le chemin existant.
`remote_selection_patch.py` a posé ce delta d'un fichier avec une sauvegarde
séparée ; sa validation froide indépendante est verte. Aucune autre impression
n'a été lancée après ce dernier delta.

**Ne pas rejouer les poses ni installer les briques séparément.** Les reçus de
la première pose décrivent sa première empreinte ; le delta suivant est dans
`inventory/raw/20260923-retained-start-temperature-v1/`. Lire ADR-071 et le
document 98 pour l'état final et les limites de preuve.
