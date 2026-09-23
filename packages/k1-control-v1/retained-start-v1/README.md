# Retained start V1 — intégration locale testée

Statut : **candidat local testé, non installé**. Le déployeur transactionnel
reste à préparer ; le manifeste indique `installer_ready=false`.

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

Validation : **280 tests ciblés verts**, comprenant les régressions de fin V3,
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

Il manque la pose/restauration transactionnelle, les contrôles à froid et la
qualification physique après nettoyage frais. **Ne pas installer les briques
séparément.** Lire ADR-071 et le document 98. La fin installée reste inchangée.
