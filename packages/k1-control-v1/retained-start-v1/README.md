# Retained start V1 — briques hors imprimante

Statut : **incomplet, non installable, non installé**.

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

Validation locale : 49 tests, aucun transport imprimante dans les tests.
Il manque le départ intégré, ses tests, le paquet de pose/restauration et les
validations froides/physiques. Ne pas copier ces fichiers seuls sur la machine.
Lire ADR-071 et le document 98 pour le périmètre restant et les refus du
contrôle automatique. La fin installée doit rester inchangée.
