# Fondation K1-CONTROL-V1

Statut : **candidat hors imprimante, non déployable sans un futur GO G4 nommé**.

Cette première pose candidate ajoute une seule API Moonraker, une petite
passerelle web dédiée au port `4409` et Mainsail comme interface experte. Elle
ne remplace ni l'écran, ni Creality Web/Print, ni les deux CFS. Elle n'écrit
dans aucun fichier constructeur. `K1 Control` reste un prototype local tant que
son adaptateur réel et les macros métier ne sont pas prêts.

## Versions figées

- Moonraker MIPS : paquet du Helper Script au commit
  `b46787a61b3ce2f04ec04d115a73a46c26814057`, contenant Moonraker
  `fccffa96c63ed77dc3953e18615e9fe9cd3d69ea` et son environnement Python 3.8 ;
- nginx MIPS : archive du même commit ;
- Mainsail : `v2.18.2`, commit
  `009ae11fc0676a6f3b0d4697f5d28aa345c697ff` ;

Les archives communautaires ne sont pas recopiées dans Git. Leur taille et
leur SHA-256 sont dans `foundation-manifest.json`. Aucune mise à jour en direct
n'est permise sur la machine : une évolution crée une nouvelle version du
paquet, repasse les tests et reçoit un nouveau GO.

## Sécurité choisie

- Moonraker écoute seulement `127.0.0.1:7125` ;
- le premier démarrage de la passerelle écoute seulement en boucle locale ;
- le compte administrateur est créé à travers un tunnel SSH, sans exposer la
  fenêtre de création du premier compte au réseau local ;
- le port dédié `4409` n'est ouvert au réseau qu'après cette connexion vérifiée ;
- Moonraker exige une connexion et ne fait confiance à aucun réseau par défaut ;
- le compte initial et sa clé API seront créés pendant une future pose, jamais
  stockés dans Git ;
- pas de mise à jour automatique, caméra, MQTT, découverte réseau, notification
  ou service cloud dans ce premier paquet.

Moonraker effectue sa propre rotation quotidienne. La politique
`config/logrotate-k1-control` borne le journal nginx. Le futur préflight doit
d'abord prouver, par un contrôle sans écriture, que le `logrotate` déjà présent
sur la machine accepte cette politique. Sinon, la pose s'arrête avant copie.

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
au simulateur de pose et à la revue de `G4-K1-CONTROL-FOUNDATION-V1`. Cette gate
est préparée mais **pas autorisée** : aucun fichier ne doit encore être copié
sur l'imprimante.
