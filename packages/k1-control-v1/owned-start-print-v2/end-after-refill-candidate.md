# Fin après relève — candidat hors imprimante ADR-069

> Essai physique du 21 septembre 2026 : **KO, candidat restauré désactivé**.
> La coupe est confirmée, mais la commande de retrait part au bac avant le
> rembobinage et le contrôle final échoue (`rewind_not_confirmed`).
> Ne pas activer/rejouer cette révision. Voir le document 90 et ADR-070.

Date : 21 septembre 2026. **Installé puis essayé ; qualification physique KO,
restauré désactivé.** Autorité historique de préparation : GO de Thomas pour la
prochaine étape recommandée après le diagnostic du document 83, à savoir la
construction et les tests hors imprimante (document 84). Le GO suivant a permis
la qualification en lecture seule du firmware (document 85), puis la correction
locale de l’ordre de contrôle du cutter. Aucun effet ni pose sur la K1.

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
| Coupe | Une seule commande stock ; contact du cutter, marqueur de retour réussi, marqueur de déclenchement observés dans cette tentative. Le relâchement peut arriver après retrait ; il ne doit pas être attendu avant celui-ci. `box.cut_pos`, événements anciens, absence d'exception et `M400` ne suffisent pas. |
| Retrait | Route et température relues après coupe ; un seul `BOX_RETRUDE_MATERIAL_WITH_TNN` de la case physique courante, même après relève interne stock. |
| Relâchement | Après retrait, attendre au plus 5 s le relâchement du cutter si non reçu ; son absence interdit la fin stock et coupe les chauffes. |
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
la commande ; le contrôle de relâchement dispose également de 5 s après retrait.
Ces deux attentes restent incluses dans les 180 s. Aucun de ces délais n'est qualifié
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

Résultats actuels : **72/72** ; voir le document 85. Les anomalies antérieures
de la suite globale sont décrites au document 84. Les tests ne
transforment pas les anciens propriétaires CFS désactivés en routes autorisées.

## Qualification en lecture seule du 21 septembre

Le document 85 et son manifeste nettoyé épinglent le firmware `2.3.5.34` et
16 empreintes inchangées avant/après collecte. La lecture statique du binaire
confirme que `if_in_resume` retourne `virtual_sdcard.do_resume_status`. Les
sources actuelles et les journaux corroborent cette lecture. Aucun attribut
n'est forcé et aucun binaire constructeur n'a été exécuté pour l'analyse.

La récupération manuelle de 09:19–09:21 confirme contact → retour OK → coupe
déclenchée, puis retrait et enfin relâchement. L'ancien candidat refusait ce
parcours en attendant le relâchement avant retrait. Le test avec les temps
réels est passé de KO à OK après correction ; le relâchement absent après
retrait reste un KO sans relance ni fin stock.

Le répartiteur G-code exact est utilisé dans six tests de compatibilité,
avec commandes physiques simulées : passage de paramètres, console multiligne,
exceptions, cycle différé et annulation avant verrou. Les macro-renommages à
la connexion précèdent l'enregistrement du candidat à l'état prêt. L'aide GET
ne publie pas toutes les commandes stock : une entrée absente n'est pas la
preuve d'une commande absente. Aucun test ne démarre Klipper complet.

## Suite du document 86 : UI et paquet préparés

La porte publie maintenant l'état de fin vers Bobines et sa fenêtre Mainsail.
Elle bloque les départs pendant une fin pendante/échouée ; l'UI ne confond plus
la sortie du fichier et la fin du cycle. Le tactile Creality garde ses libellés.

Le paquet `../end-after-refill-install-disabled-v1/` fixe sept fichiers, leurs
empreintes, le plan de pose désactivée, les backups/rollback et les contrôles à
froid. Son générateur est hors réseau. Aucun include n'a été posé sur la machine.

Reste : comparer les bases en lecture fraîche, poser désactivé et valider le
chargement réel. Puis qualifier séparément la séquence complète après relève,
avec route TNN explicite, coupe, bon rembobinage, tête vide, relâchement, arrêt
thermique et caméra. Ne pas réauditer le prédicat et l'ordre déjà établis ;
ne pas se contenter de changer `enabled` en `true`.
