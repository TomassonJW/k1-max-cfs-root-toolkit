# 14 — G4-K1-CONTROL-FOUNDATION-V3

Date : 2026-08-21

Statut : **installée et validée le 2026-08-21 ; observation de huit heures requise**

## Pourquoi V3 existe

V2 a atteint un Mainsail fonctionnel en boucle locale, puis a été rollbackée.
Le test réel a prouvé que Mainsail `v2.18.2` ne sait ni créer ni utiliser un
compte Moonraker. La sécurité ne peut donc pas reposer sur `force_logins` sans
rendre Mainsail inutilisable.

V3 conserve Moonraker sur `127.0.0.1:7125` et place l'authentification sur nginx,
la seule frontière réellement traversée par les clients Mainsail. Le binaire
MIPS figé a été inspecté hors imprimante : les directives `auth_basic` et
`auth_basic_user_file` sont présentes et le module n'est pas explicitement
désactivé.

## Contrat de sécurité

- Moonraker écoute seulement sur `127.0.0.1:7125` ;
- seule la connexion locale nginx est déclarée fiable dans Moonraker ;
- l'API key et `force_logins` sont désactivés ;
- nginx retire l'en-tête `Authorization` avant toute transmission à Moonraker ;
- le compte nginx est demandé deux fois par une invite PowerShell masquée ;
- le mot de passe n'est jamais un argument de commande, un fichier local ou une
  preuve ;
- seul un hachage RFC 2307 SSHA avec sel aléatoire de 16 octets est transmis par
  SSH et stocké en `root:www-data`, mode `0640`, afin que seul root et le worker
  nginx puissent le lire ; le dossier parent est `root:www-data`, mode `0710`,
  et une lecture sous `www-data` est exigée avant la saisie humaine ;
- un seul compte initial est accepté par la pose ;
- le port LAN refuse les sources hors boucle locale et plages IPv4 privées ;
- une requête anonyme doit recevoir HTTP `401` avant et après l'ouverture LAN ;
- le mot de passe doit contenir 16 à 128 caractères ASCII imprimables sans
  espace ;
- PowerShell 7 ou plus récent est exigé afin de garantir le flux UTF-8 sans BOM
  et la fin de ligne Unix envoyés directement à l'entrée standard de SSH.

HTTP Basic ne chiffre pas le trafic : le mot de passe et la session sont
protégés contre le stockage en clair, mais pas contre l'écoute active du réseau.
Le port `4409` est donc réservé au LAN privé de confiance. Depuis un Wi-Fi
invité, Internet, un réseau public ou un accès distant, le tunnel SSH reste
obligatoire. V3 n'ajoute pas TLS et ne doit jamais être publiée par redirection
de port.

## Pose en trois états

### 1. Fondation locale sans compte

`InstallBootstrap` répète le préflight réel, installe la fondation et démarre :

- Moonraker sur `127.0.0.1:7125` ;
- Mainsail sans authentification sur `127.0.0.1:4409` uniquement.

Cette fenêtre n'est accessible que par le tunnel SSH explicite. Toute écoute
LAN, cible déjà présente, différence d'empreinte ou régression de ressources
provoque l'arrêt et le rollback.

### 2. Compte vérifié, encore local

Thomas exécute lui-même `scripts/set-control-foundation-account.ps1`. Le script
demande le nom, le mot de passe et sa confirmation, écrit atomiquement seulement
le hachage distant, teste la configuration locale authentifiée puis exige :

- HTTP `401` sans identifiants ;
- HTTP `200` avec les identifiants saisis ;
- Mainsail et Moonraker toujours en boucle locale ;
- Klipper, les processus Creality et les deux CFS inchangés.

Thomas ouvre ensuite le tunnel :

`ssh -N -L 4409:127.0.0.1:4409 k1max-root`

Il vérifie lui-même la demande de connexion, le chargement de Mainsail, puis
ferme et rouvre le navigateur pour confirmer que les identifiants sont bien
redemandés. Aucun identifiant ne doit être envoyé dans le clavardage.

### 3. LAN privé authentifié

Après le signal humain exact de compte vérifié, `ActivateLan` :

1. confirme l'unique fichier SSHA et la configuration locale authentifiée ;
2. confirme HTTP `401` sans identifiants ;
3. teste la configuration LAN suivante ;
4. remplace atomiquement `nginx-active.conf` ;
5. redémarre seulement le nouveau nginx, car un reload ne peut pas élargir la
   socket existante de `127.0.0.1` vers `0.0.0.0` sur le même port ;
6. confirme `0.0.0.0:4409`, HTTP `401`, les ressources, Klipper et les deux CFS ;
7. restaure la configuration précédente puis rollback la fondation au premier
   KO.

Moonraker reste en boucle locale pendant les trois états.
Le rollback ne supprime le dossier du projet que si le marqueur du même
`CaptureId` prouve qu'il était absent avant la pose. Il exige ensuite l'absence
du dossier, des deux services, des deux PID et des ports `7125` et `4409`.

## Effets exclus

V3 ne transmet aucun G-code et ne modifie ni `printer.cfg`, ni les macros, ni le
Z, ni le mesh, ni les CFS, ni le firmware, ni les interfaces Creality, ni Orca.
Le post-traitement `+0,27 mm` reste actif. Aucun redémarrage de l'imprimante
n'est autorisé.

## État réel et suite

La capture finale `20260821-015722-g4-control-foundation-v3` a validé les trois
états. Thomas a vérifié son compte dans le vrai tableau de bord Mainsail ;
Moonraker reste en boucle locale et Mainsail authentifié est ouvert au LAN privé.
Les ressources, Klipper, les interfaces Creality et les deux CFS sont verts.

La fondation ne doit plus être réinstallée ou modifiée sous le nom V3. Après
ouverture du tableau de bord, une inspection bornée et sans mutation a confirmé
que Moonraker dérive deux racines vides `state/config` et `state/gcodes`,
distinctes des chemins Creality actifs sous `printer_data`. Cela produit deux
avertissements de gestion de fichiers sans casser la connexion à Klipper.

La suggestion générique de changer `[virtual_sdcard]` est refusée. La correction
est préparée comme un lot séparé
`G4-K1-CONTROL-FOUNDATION-V3-PATHS-V1` dans le document 15. Elle conserve les
chemins Creality, utilise les liens symboliques supportés par Moonraker, rend
`config` non modifiable par l'API et documente le pouvoir d'écriture de la racine
`gcodes`. Son premier GO exact est arrivé avant la préparation du paquet et n'a
pas été consommé ; elle attend un renouvellement après revue et ne peut réutiliser
aucun GO V3 antérieur.

L'acceptation durable exige ensuite huit heures d'observation sur l'état final
retenu, comprenant une impression normale choisie et lancée manuellement par
Thomas. Cette observation n'autorise aucun G-code ou changement automatique de
comportement. Le post-traitement `+0,27 mm`, le Start G-code et le G-code de
changement de filament restent inchangés.
