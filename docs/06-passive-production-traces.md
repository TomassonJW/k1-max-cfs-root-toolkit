# Traces passives autour de travaux utiles

## But

Observer le défaut rapporté sans lancer une campagne d'essais coûteuse. La preuve recherchée est la succession naturelle de deux travaux :

1. une vraie impression longue et utile ;
2. le travail suivant, avec des réglages différents ou plusieurs objets.

Cette séquence ne cherche pas à obliger le défaut à apparaître. Elle enregistre assez d'état pour comprendre ce qui change s'il apparaît pendant l'usage normal.

## Autorité

Thomas choisit, prépare, lance, surveille et arrête les impressions. Codex ne fait qu'observer par SSH en lecture seule.

Sont interdits pendant la capture : mouvement, chauffe, extrusion, homing, calibrage, lancement ou annulation par Codex, écriture distante, modification de configuration, rotation de journal et redémarrage de service.

## Deux dossiers privés distincts

Chaque travail reçoit un dossier ignoré sous `inventory/raw/g3-production/` :

- `long-<date>` pour l'impression longue ;
- `followup-<date>` pour le travail suivant différent ou multi-objet.

G-code, noms de fichiers, journaux complets et notes humaines restent privés. Le dépôt public ne reçoit que les empreintes, événements nettoyés et conclusions.

## Capture automatique

Le script [start-passive-production-trace.ps1](../scripts/start-passive-production-trace.ps1) ouvre une seule connexion SSH sans mot de passe et :

- fige les empreintes des trois configurations principales ;
- relève la valeur Z sauvegardée visible dans `printer.cfg` ;
- relève la taille et la date du journal Klipper actif ;
- suit uniquement les nouvelles lignes du journal, y compris après rotation ;
- ouvre un abonnement Klipper unique et enregistre les changements d'état, avec un échantillon complet toutes les deux secondes pour les températures, la pression advance, la position, le Z visible et l'origine de homing ;
- suit aussi les seuls indicateurs CFS non secrets utiles à la causalité : état
  global, commande `T` en cours, refill automatique et présence filament ;
- écrit tout dans le dossier privé local sans créer de fichier sur l'imprimante.

La capture démarre quand la machine est au repos, avant le lancement humain. Elle s'arrête après le retour au repos et quelques minutes de refroidissement. `Ctrl+C` arrête seulement l'observateur.

## Notes humaines minimales

Pour chaque travail, noter :

- heure réelle de lancement et de fin ;
- G-code utilisé et son SHA-256 local ;
- trancheur et réglages qui diffèrent du travail précédent ;
- nombre d'objets ;
- filament, slot et CFS utilisés ;
- correction Z faite en direct, avec heure et valeur ;
- qualité de la première couche ;
- nettoyage, intervention mécanique, reboot ou changement de plaque entre les deux travaux.

Une correction Z de sécurité reste autorisée à Thomas. Elle n'invalide pas la trace, mais son heure doit être donnée pour distinguer la décision humaine du comportement automatique.

## Décision après les deux travaux

La comparaison porte d'abord sur les transitions d'état :

- PA demandée, valeur injectée par CFS et valeur finale active ;
- origine Z avant lancement, après les homings et à la première extrusion ;
- nombre et dispersion des mesures PR Touch visibles ;
- mesh chargé, vérifié ou régénéré ;
- ordre nettoyage → homing → mesh → extrusion ;
- différences de chemin entre le travail long et son successeur.
- transitions exactes de `box.state` et `box.t_command` autour d'un chargement,
  refill équivalent ou changement volontaire entre les deux CFS.

Si le défaut ne se produit pas, la capture reste utile mais n'autorise pas une conclusion causale. Aucun troisième travail sacrificiel n'est ajouté automatiquement.
