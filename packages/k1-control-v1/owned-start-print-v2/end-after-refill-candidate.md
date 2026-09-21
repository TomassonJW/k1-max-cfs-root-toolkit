# Fin après relève — candidat hors imprimante ADR-069

Date : 21 septembre 2026. **Implémenté et vérifié en simulation ; désactivé,
non installé, non qualifié physiquement.** Autorité : GO de Thomas pour la
prochaine étape recommandée après le diagnostic du document 83, à savoir la
construction et les tests hors imprimante. Aucune connexion K1 dans cette étape.

## Fichiers et comportement

- `kctrl_end.py` : composant Klipper sans dépendance ajoutée. Désactivé par
  défaut, il ne remplace aucune commande et n'installe aucun écouteur console.
- `k1-control-owned-end-candidate.cfg` : configuration séparée `enabled: false`.
  Aucun include n'est ajouté à la configuration existante. Ce fichier n'est pas
  un paquet de pose qualifié.
- `tests/test_kctrl_end_after_refill_v1.py` : simulations de l'incident, essais
  avec pannes injectées et vérification facultative du répartiteur Creality capturé.

Si une version future est qualifiée et activée, elle enveloppera `START_PRINT`
et remplacera les entrées `END_PRINT` et `CANCEL_PRINT`, en une seule étape
au démarrage de Klipper. Un échec d'enregistrement restaure les entrées d'origine.
Le départ existant est conservé ; seule son ancienne information de changement
d'outil est vidée pour ne pas la réutiliser dans le nouveau travail.

| Étape | Condition pour poursuivre |
| --- | --- |
| Demande de fin | Travail identifié par numéro de départ et nom de fichier ; une seule demande retenue. Consigne de buse mémorisée. |
| Attente différée | Retour immédiat au lecteur G-code, puis attente de sa sortie et de `do_resume_status=False`, hors verrou de commande. Aucune écriture de ce drapeau. |
| Lecture | Deux CFS connectés, une seule case engagée et capteur de tête connu. Route physique prioritaire ; table logique actualisée utilisée pour détecter une contradiction, jamais appliquée deux fois. |
| Température | Consigne déjà présente, finie, entre 150 et 320 °C ; température à ±5 °C et `can_extrude=True`. Aucun chauffage ajouté ni plancher de 200 °C. La consigne ne doit pas changer pendant l'attente ou la coupe. |
| Coupe | Une seule commande stock ; contact du cutter, marqueur de retour réussi, marqueur de déclenchement puis relâchement observés dans cette tentative. `box.cut_pos`, événements anciens, absence d'exception et `M400` ne suffisent pas. |
| Retrait | Route et température relues après coupe ; un seul `BOX_RETRUDE_MATERIAL_WITH_TNN` de la case physique courante, même après relève interne stock. |
| Fin | Tête vide ET aucune route engagée ; alors seulement `END_PRINT_NO_M84`, puis `M84` et arrêt des chauffes vérifié. |
| Refus/erreur | Aucune relance ni repli sur un ancien emplacement, pas de `BOX_END` tête chargée ; coupure thermique et motif conservé. |

Une tête déjà vide n'autorise la fin que si aucune route n'est engagée. Ce
candidat vise les travaux CFS démarrés par notre `START_PRINT` ; une identité
absente, un redémarrage, un CFS absent ou un état contradictoire ferment la
partie filament. Il n'essaie pas de reprendre automatiquement une fin échouée.
Le prochain départ réarme le capteur de tête par la séquence existante.

## Erreur, annulation et délai

Le délai total est de 180 s, attente de sortie du fichier comprise. Un minuteur
séparé appelle directement l'arrêt des chauffes, sans attendre le verrou G-code.
Si une commande stock rend finalement la main après le délai, le contrôle interdit
l'étape suivante. Le délai de 5 s de confirmation de coupe commence au retour de
la commande et reste inclus dans les 180 s. Aucun de ces délais n'est qualifié
sur une nouvelle coupe réelle.

L'événement Creality `gcode:cancel`, émis avant l'acquisition du verrou dans le
répartiteur historique capturé, coupe les chauffes d'une fin en cours. Une
annulation pendant cette fin n'en crée pas une seconde ; `CANCEL_PRINT_BASE`
reste demandé pour annuler le travail. Une annulation indépendante utilise la
même vérification de route et de coupe, seulement si une consigne valide existe
encore. Une buse déjà froide n'est pas réchauffée. Un nouveau départ est refusé
tant que le traitement de la fin précédente n'a pas réellement rendu la main,
y compris lorsque son échec a déjà été annoncé.

L'arrêt vérifie les deux consignes à zéro. Si l'API d'arrêt échoue ou si les
consignes restent non nulles, un arrêt Klipper est demandé. Cela ne prouve ni
la température physique ni l'arrêt immédiat d'un moteur CFS autonome. Un blocage
complet de la boucle Klipper peut aussi empêcher le minuteur de s'exécuter :
ce n'est pas un dispositif thermique matériel indépendant.

## Validation et portée

La commande de référence est :

```text
python -m pytest -q tests/test_kctrl_end_after_refill_v1.py
```

Les cas couvrent la relève T1A → T1B qui contourne l'enveloppe T, la relève vers
le second CFS, le départ suivant portant le même nom, une tentative d'outil
échouée, les routes ambiguës/perdues/contradictoires, la reprise persistante,
les refus silencieux de coupe, l'ordre et la fraîcheur des événements, un cutter
qui revient au contact, la baisse de température, le retrait incomplet,
l'annulation prioritaire, le double appel, la déconnexion, la coupure thermique
qui échoue et le refus d'un nouveau travail pendant une fin encore pendante.

Un test facultatif utilise le vrai répartiteur G-code capturé le 21 août
(SHA-256 `20d21ace63ac249c5e38d237898ff18d924047d4532a917124cb92eaed24cde7`).
Il vérifie l'enregistrement des enveloppes, le passage des paramètres de départ
et les sorties console multilignes. Il est ignoré sur un poste sans cette capture
privée. Aucun code constructeur n'est publié. Cette compatibilité partielle
n'est pas une exécution de Klipper complet ni une preuve du firmware actuel.

Résultats finaux et anomalies antérieures : voir le document 84. Les tests ne
transforment pas les anciens propriétaires CFS désactivés en routes autorisées.

## Ce qui interdit encore une pose ou activation

1. **Firmware exact** : comparer les composants actuels et qualifier le prédicat
   compilé `if_in_resume`. La fin de `do_resume_status` à la sortie SD est une
   observation de source, pas une équivalence démontrée avec ce prédicat.
2. **Preuve de coupe** : ADR-041 établit que `box.cut_pos` n'est pas le capteur
   réel ; les marqueurs console sont historiques (ADR-041/044). Leur présence,
   ordre et fraîcheur après `BOX_CUT_MATERIAL` seul, en fin différée, restent à
   qualifier. Si le relâchement n'est pas exposé dans ce contexte, la version
   actuelle refusera le retrait ; ne pas enlever le contrôle pour la faire passer.
3. **Intégration Klipper** : confirmer l'ordre d'enregistrement avec les macros,
   les erreurs émises par les commandes stock, `CANCEL_PRINT_BASE`, l'accès au
   verrou et l'API thermique sur les versions exactes. Les fausses API ne
   reproduisent pas tout le moteur d'exécution ni le transport CFS.
4. **Affichage** : `print_stats` peut annoncer `complete` dès la sortie du fichier,
   avant le retrait différé. Le candidat expose `phase`, `pending`, `failure` et
   `thermal_failure`, et écrit en console, mais l'écran constructeur et l'UI
   K1 Control ne sont pas raccordés à cet état. Il faut une indication claire
   « fin en cours » / « fin incomplète » avant activation ; un travail déclaré
   terminé ne constitue jamais une preuve de retrait.
5. **Pose réversible et essai réel** : préparer la liste exacte des fichiers,
   empreintes, sauvegardes, ordre de chargement, redémarrage et retour arrière
   après levée des points précédents. Puis seulement une validation distincte,
   avec caméra et présence humaine utile, sur une impression sans valeur.

Prochaine étape recommandée : qualification du firmware et de l'intégration
**à froid, en lecture seule**, sans commande filament. Elle doit soit fermer les
points prouvables par les sources et les journaux, soit isoler les preuves qui
exigent un essai physique ultérieur. Elle ne doit pas promettre de prouver une
coupe réelle à froid. Ne pas se contenter de changer `enabled` en `true`.
