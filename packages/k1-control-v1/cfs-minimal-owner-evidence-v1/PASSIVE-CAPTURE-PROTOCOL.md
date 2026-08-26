# Protocole préparé — capture passive du propriétaire CFS V1

Statut : **document de revue uniquement ; aucune connexion ni action physique
autorisée**.

## But

Capturer le dialogue exact du chemin constructeur sans injecter de trame et
sans modifier le logiciel de la K1. Les gestes physiques restent déclenchés par
l'interface constructeur, un seul à la fois, devant l'imprimante.

## Conditions obligatoires avant exécution

1. GO exact séparé :
   `GO G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`.
2. Revue et gel du script de capture, du write-set nul, des commandes, des
   bornes de temps et du rollback documentaire.
3. Plateau et trajectoire libres, buse propre, filament et températures connus.
4. Un seul opérateur devant la K1 ; arrêt immédiat possible depuis l'interface
   stock.
5. Aucun outil ne doit écrire sur le bus série. La capture doit observer
   seulement le trafic déjà produit par le propriétaire constructeur.

## Ordre minimal des cas

Chaque cas commence au repos et finit par une vérification de retour au repos.
Un KO arrête la campagne ; aucun rerun automatique.

1. inventaire passif des deux CFS et des huit routes A/B/C/D ;
2. chargement stock isolé sur `T1A` ;
3. retrait stock isolé sur `T1A` ;
4. arrêt ou annulation stock pendant une phase sans extrusion dangereuse ;
5. seulement après analyse hors imprimante : répéter séparément sur B/C/D ;
6. seulement après validation de l'unité 1 : répéter séparément sur l'unité 2 ;
7. traiter coupe et purge comme des cas différents, avec température et
   géométrie explicites ;
8. tester perte, réponse tardive et reconnexion uniquement dans une gate de
   faute dédiée, jamais pendant la campagne nominale.

## Preuve attendue par cas

- état initial et route fraîche ;
- geste humain exact dans l'interface stock ;
- horodatage monotone ;
- octets complets émission/réception, y compris tête et CRC ;
- événement ou réponse relié à la requête sans ambiguïté ;
- états des capteurs avant, pendant et après ;
- température et mouvements observés, sans les attribuer au protocole série ;
- état final, erreurs et arrêt humain éventuel ;
- empreintes SHA-256 des captures privées ;
- résumé nettoyé sans numéro de série, UUID ou identifiant matériel.

## Gate propriétaire exclusif

La simple absence d'un heartbeat ne suffit pas. Avant tout futur propriétaire
minimal, il faut observer ou obtenir une interface qui prouve :

1. demande de prise de main ;
2. acquittement explicite du propriétaire stock ;
3. absence d'émission concurrente ;
4. arrêt sûr des opérations en cours ;
5. restitution explicite ;
6. reprise stock saine après restitution et après reconnexion.

Sans ces six points, aucune trame d'effet ne devient appelable, même si elle a
réussi dans une capture.

## Critères OK / KO

OK de capture : fichier complet, horodaté, passif, cas unique, état final sûr et
preuve nettoyable.

KO immédiat : émission par l'outil, route ambiguë, capteur incohérent, erreur
CFS, mouvement inattendu, température non prévue, perte de la possibilité
d'arrêt, deux opérations simultanées ou état final non confirmé.

Un OK de capture n'est pas un GO de déploiement. Les preuves retournent d'abord
dans une mission hors imprimante pour analyse et nouvelle ADR.
