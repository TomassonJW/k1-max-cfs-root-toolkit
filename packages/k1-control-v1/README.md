# Fondation K1-CONTROL-V1

Statut : **fondation V3, runtime Z/mesh, calibration quotidienne et navigation
installés ; composite `11 × 11` retenu comme source mais mode Précision KO aux
bords ; éditeur dérivé hors ligne validé ; routage thermique CFS simulé ;
protocole du propriétaire minimal fermé en KO borné sans transport ; retrait
stock `T1A` capturé avec garde thermique encore à construire ; production
fermée**.

La fondation initiale ajoute une seule API Moonraker, une petite
passerelle web dédiée au port `4409` et Mainsail comme interface experte. Elle
ne remplace ni l'écran, ni Creality Web/Print, ni les deux CFS. Elle n'écrit
dans aucun fichier constructeur. Les tranches de calibration sont désormais
réelles et validées ; les séquences de production restent absentes jusqu'aux
gates ADR-016.

## Éditeur de profil dérivé hors ligne

Le paquet [`mesh-editor-offline-v1/`](mesh-editor-offline-v1/) crée en mémoire
un profil dérivé versionné du composite physique `11 × 11`. Il fournit une
grille orientée de 121 points, les actions `Rapprocher/Éloigner`, les pas
`0,005/0,010 mm`, les gardes, l'historique, un aperçu 3D sans glisser vertical
et deux exports déterministes.

Sa moyenne est calculée sur la surface bicubique Klipper `31 × 31`, puis remise
à zéro sans toucher au Z global. Le serveur de démonstration écoute seulement
sur `127.0.0.1` et utilise une fausse API en mémoire. Ce paquet ne contient
aucune pose K1 et ne rend pas encore visible le mode Précision réel.

## Audit de la frontière CFS

Le paquet [`cfs-box-wrapper-audit-v1/`](cfs-box-wrapper-audit-v1/) vérifie hors
imprimante l'identité du module compilé et la chronologie exacte de l'incident
du 26 août. Il confirme que le chemin de chargement stock possède la cible
thermique `220 °C` et la géométrie malgré une purge demandée à `190 °C`.

Son adaptateur est volontairement fermé : aucune primitive stock n'est
qualifiée, aucune pose n'est préparée et la production reste bloquée.

## Routage dynamique des températures CFS

Le paquet
[`cfs-dynamic-temp-routing-v1/`](cfs-dynamic-temp-routing-v1/) compare les
quatre voies possibles et choisit un propriétaire filament minimal séparé. Son
ticket lie la phase, la route fraîche, la buse, le plateau et les six invariants
avant le premier effet filament.

Sa matrice hors ligne obtient `25/25` sur deux CFS, first/normal, chargement,
changement, refill, runout, pause/reprise, annulation et arrêts sûrs. Il ne
contient aucun transport K1 ni candidat de pose ; la production reste fermée.

## Protocole du propriétaire filament minimal

Le paquet
[`cfs-minimal-owner-protocol-v1/`](cfs-minimal-owner-protocol-v1/) relie les
trames visibles aux empreintes et lignes exactes des captures privées, puis
teste les ambiguïtés hors ligne. Il confirme les requêtes d'état sur deux
adresses, mais seulement une route d'effet `T1A` sur le premier CFS.

Retrait, coupe, purge isolée, slots B/C/D, effets du second CFS, intégrité des
trames et exclusion du propriétaire constructeur restent non prouvés. La gate
est donc close en KO borné avec `callable_messages=[]`. Ses 25 scénarios verts
prouvent le blocage sûr, pas un protocole déployable.

## Preuves supplémentaires du propriétaire minimal

Le paquet
[`cfs-minimal-owner-evidence-v1/`](cfs-minimal-owner-evidence-v1/) retrouve dans
un ancien journal un retrait constructeur `T1A` exact : deux requêtes
`RETRUDE_PROCESS`, deux réponses réussies, timeout hôte de 150 secondes et
capteur local devenu libre. Il prouve aussi que les deux journaux concernés sont
deux instantanés du même passage, pas deux essais.

Cette avancée ne lève ni l'exclusion du propriétaire stock, ni les autres routes,
ni la coupe, la purge ou les reprises après faute. La gate reste close en KO
borné avec `callable_messages=[]`. Le paquet prépare seulement le protocole
d'une future capture passive, qui exige une revue et un GO exact distincts.

## Capture réelle du retrait officiel

Le paquet
[`cfs-minimal-owner-passive-capture-v1/`](cfs-minimal-owner-passive-capture-v1/)
qualifie un retrait constructeur réel sur la route fraîche `T1A`. La macro
stock a terminé, les deux phases ont répondu et le CFS ne considère ensuite
plus aucun slot engagé sur l'unité 1.

La capture révèle que la K1 demande `220 °C` mais laisse cette cible active
après la fin. Elle montre aussi qu'un retour HTTP `ok` peut masquer une commande
mal encodée. Le prochain incrément préparera donc hors imprimante un garde
autour de la macro stock, avec vérification de l'effet réel et arrêt garanti des
chauffes. Le propriétaire série reste fermé et `callable_messages=[]`.

## Versions figées

- Moonraker MIPS : paquet du Helper Script au commit
  `b46787a61b3ce2f04ec04d115a73a46c26814057`, contenant Moonraker
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea` et son environnement Python 3.8 ;
- nginx MIPS `1.17.7` : archive du même commit ;
- Mainsail : `v2.18.2`, commit
  `009ae11fc0676a6f3b0d4697f5d28aa345c697ff` ;

Les archives communautaires ne sont pas recopiées dans Git. Leur taille et
leur SHA-256 sont dans `foundation-manifest.json`. Aucune mise à jour en direct
n'est permise sur la machine : une évolution crée une nouvelle version du
paquet, repasse les tests et reçoit un nouveau GO.

## Sécurité choisie

- Moonraker écoute seulement `127.0.0.1:7125` ;
- le premier démarrage de la passerelle écoute seulement en boucle locale ;
- le compte HTTP nginx est créé par une invite PowerShell locale masquée ; seul
  son hachage SSHA salé est transmis par SSH et stocké avec le propriétaire
  `root:www-data` et le mode `0640`, dans un dossier `root:www-data` en `0710` ;
  une lecture sous l'identité réelle `www-data` est prouvée avant la saisie ;
- PowerShell 7 ou plus récent est requis pour cette saisie et ce transport ;
- le compte est vérifié à travers un tunnel SSH, sans exposer la fenêtre de
  connexion au réseau local ;
- le port dédié `4409` n'est ouvert au réseau qu'après cette connexion vérifiée ;
- le port LAN accepte seulement la boucle locale et les plages IPv4 privées ;
- Moonraker fait confiance uniquement au nginx local, et nginx retire l'en-tête
  HTTP `Authorization` avant chaque requête transmise ;
- aucune clé API ou empreinte de mot de passe n'est stockée dans Git ;
- pas de mise à jour automatique, caméra, MQTT, découverte réseau, notification
  ou service cloud dans ce premier paquet.

Le préflight réel de V1 a prouvé que la machine ne possède ni `logrotate`, ni
`/etc/logrotate.d`. V1 a donc été arrêtée avant toute copie. V2 n'a ajouté
aucune dépendance : Moonraker conserve sa rotation quotidienne interne et nginx
envoie ses erreurs au `syslogd` BusyBox déjà actif par `/dev/log`. Sur cette
machine, son aide confirme la rotation par défaut à 200 Kio avec une sauvegarde.
La pose réelle V2 a ensuite prouvé que Mainsail `v2.18.2` ne sait pas créer ni
utiliser un compte Moonraker. V2 a été rollbackée et fermée. V3 déplace donc
l'authentification à la seule frontière réseau réellement compatible : nginx.

## Ressources et arrêt automatique

L'instantané réel donne environ 118 Mio disponibles. La future validation
s'arrête si Moonraker dépasse 45 Mio au repos, s'il reste moins de 70 Mio
disponibles, si le swap augmente de plus de 8 Mio ou si les deux nouveaux
services deviennent instables, ou si les journaux dépassent ensemble 16 Mio. Un
test de durée d'au moins huit heures, incluant une impression représentative,
reste obligatoire après un futur GO.

## Pourquoi les scripts d'origine ne sont pas utilisés

Le script communautaire extrait ses archives, remplace des fichiers, crée des
liens système, lance les services et fait ensuite un `git pull`. Notre paquet
réutilise seulement les archives auditées. Il pose de nouveaux chemins
versionnés et de nouveaux services, sans toucher à `printer.cfg`,
`gcode_macro.cfg`, `box.cfg`, au Klipper constructeur ni au nginx constructeur.

Les fichiers `config/` et `services/` sont des originaux du projet. Ils servent
au simulateur de pose et à la revue de `G4-K1-CONTROL-FOUNDATION-V3`. Cette gate
est préparée mais **pas autorisée** : aucun fichier ne doit encore être copié
sur l'imprimante.
