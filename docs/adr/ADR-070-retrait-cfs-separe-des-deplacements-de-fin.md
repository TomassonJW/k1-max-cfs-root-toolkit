# ADR-070 — Séparer le retrait CFS des déplacements de fin

Statut : successeur séparé installé et actif sous autorisation utilisateur
explicite, validé à froid (document 91). Qualification physique encore ouverte.
Les décisions ci-dessous décrivent aussi le confinement historique du candidat
précédent, qui reste interdit de rejeu.
Date : 21 septembre 2026. Complète ADR-069 après son premier essai de fin.

## Constat

Le candidat a correctement attendu la fin de la reprise SD, choisi T1B et
prouvé la coupe. Il a ensuite appelé `BOX_RETRUDE_MATERIAL_WITH_TNN`, qui
commence par rejoindre la position de purge. L'observation physique rejette
cet ordre. Le contrôle immédiat après sa réponse a ensuite trouvé tête libre
mais route B, et arrêté sans déclarer une réussite.

## Décision

1. Le candidat actuel reste désactivé. Ses essais V1 et R2 sont clos et non
   rejouables. Les preuves de coupe et de choix de route sont conservées.
2. Le retrait doit exposer séparément ses effets : dégagement local du cutter,
   rétraction extrudeur, rembobinage de la case physique, preuve de fin, puis
   parc explicite. Aucun mouvement Z ou aller au bac caché dans une primitive.
3. Le retour d'une commande ne vaut pas propagation de tous les états. Une
   future attente bornée doit conserver l'identité du job et de la route,
   distinguer l'ancien état B d'une route différente/inconnue, vérifier tête
   libre et rembobinage terminé, puis seulement autoriser la fin stock.
4. Aucun remplacement de commande série ou appel interne compilé ne devient
   appelable par cette décision. Identifier signatures, effets, limites,
   arrêts et retour exact hors machine avant de produire le successeur.
5. Respecter l'interdiction présente de relever le plateau. Le redémarrage a
   perdu les références : aucun homing chargé ou au bac par simple supposition.

## Alternatives écartées

- Rejouer R2 ou augmenter uniquement un délai : conserve le mouvement rejeté.
- Ignorer la route B dès que la tête est libre : abandonne la preuve de retrait.
- Augmenter courant/vitesse au hasard : aucun défaut établi sur ces paramètres.
- Installer un bouchon `SET_HOTEND_FAN` : ne corrige ni le retrait ni sa preuve.

## Conséquences

La validation physique de la fin demeure KO. Le prochain incrément est borné
au retrait et à son attente, avec tests de mise à jour différée, d'états
contradictoires et d'effets interdits. La récupération doit également éviter
un nouveau départ/probing lorsqu'une simple remise en état logicielle suffit.

## Mise en œuvre du 21 septembre

Les signatures et le retour des primitives ont été confirmés sur le binaire
exact avec de faux objets et un faux transport, sans imprimante active.
Le paquet `end-separated-v1` retient les méthodes élémentaires, exige un ACK
booléen positif et sépare leur exécution des mouvements. Les wrappers G-code
sont écartés pour l'appel d'effet car ils jettent cet ACK. L'attente utilise les
notifications existantes, sans ajouter la lecture stock à délai de 3600 s.
La pose à froid est validée ; voir document 91 et le manifeste pour les preuves,
les limites, les deux destinations et la restauration exacte.
