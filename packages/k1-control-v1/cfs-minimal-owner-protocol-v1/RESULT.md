# Résultat — CFS Minimal Owner Protocol V1

Date : 2026-08-26

Verdict : **KO borné, correctement fermé**.

## Ce qui est prouvé

- les quatre captures privées gardent leurs empreintes exactes ;
- la requête observée suit la forme `adresse / longueur / 0xff / commande /
  payload` ;
- la réponse observée expose `0xf7 / adresse / longueur / état / commande /
  payload ou terminaison` ;
- le wrapper corrèle visiblement par `(adresse, commande)` ; aucun identifiant
  de transaction n'est observé ;
- les adresses 1 et 2 répondent aux requêtes d'état ;
- une séquence `EXTRUDE_PROCESS` existe pour `T1A`, adresse 1, slot A ;
- un état `OK` et l'erreur `EXTRUDE_ERR8` ont été vus sur cette séquence ;
- les symboles de retrait et de moteur de connexion existent dans les chaînes
  statiques, mais pas leurs trames dans le journal complet.

## Pourquoi la gate est KO

Le propriétaire minimal doit charger, retirer, couper, purger, s'arrêter et se
resynchroniser sur huit routes possibles, sans collision avec le propriétaire
constructeur. Les preuves disponibles ne couvrent qu'une séquence de
chargement stock sur `T1A` et quelques requêtes d'état.

Restent inconnus :

- la règle d'intégrité ou de checksum des trames ;
- les trames et réponses de retrait, coupe, purge isolée et arrêt ;
- les effets pour B/C/D et pour le second CFS ;
- la séparation exacte entre réponse et événement hors d'une attente active ;
- la resynchronisation après perte ou reconnexion ;
- l'exclusion exclusive puis la restauration du propriétaire constructeur.

La ligne `box heart process not enable` n'est pas une preuve d'exclusion : elle
ne fournit ni contrat public, ni acquittement, ni cycle de restitution.

## Résultat vérifiable

- liste de messages appelables : `[]` ;
- transport K1 : absent ;
- candidat de pose : faux ;
- connexion K1 pendant la mission : aucune ;
- binaire MIPS chargé, importé ou exécuté : non ;
- matrice de sûreté : `25/25` attendus ;
- identifiants privés publiés : aucun.

Le vert des tests signifie que toute ambiguïté est bloquée. Il ne transforme
pas ce KO de preuve en réussite matérielle.
