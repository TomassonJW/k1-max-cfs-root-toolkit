# Résultat — CFS Minimal Owner Evidence V1

Date : 2026-08-26

Verdict : **KO borné, avec avancée réelle**.

## Avancée obtenue

L'ancien journal de 2026-08-21 contient un retrait constructeur complet sur le
chemin déjà relié à `T1A` :

- une demande vers le tampon ;
- une demande vers le capteur matière ;
- une réponse réussie pour chacune ;
- un timeout hôte de 150 secondes ;
- un capteur local qui passe de présent à libre.

Les deux fichiers qui contiennent cette séquence ne sont pas deux essais : le
plus court est le préfixe exact du plus long. La mission compte donc une seule
observation physique historique.

La terminaison de la réponse correspond au CRC-8 public décrit avec le
polynôme `0x07`. Cette concordance qualifie la réponse capturée, mais pas encore
la transformation complète d'une requête par la couche série exacte.

## Ce qui bloque encore

- aucune prise exclusive et restitution du propriétaire constructeur n'est
  prouvée ;
- aucune route fraîche n'est présente dans le même événement de retrait ;
- B/C/D et le second CFS ne sont pas qualifiés pour les effets ;
- coupe et purge restent mêlées à la géométrie et à la température stock ;
- aucun arrêt sûr, timeout tardif ou cycle de reconnexion n'est qualifié ;
- la source publique de retrait consultée décrit une variante dont plusieurs
  numéros de commandes diffèrent du binaire local.

## Clôture

- liste de messages appelables : `[]` ;
- transport : absent ;
- candidat de déploiement : non ;
- connexion K1 pendant la mission : non ;
- action physique pendant la mission : non ;
- module MIPS chargé, importé ou exécuté : non.

La prochaine gate proposée est
`G4-K1-CONTROL-CFS-MINIMAL-OWNER-PASSIVE-CAPTURE-V1`. Son protocole est préparé,
mais son exécution demanderait un GO exact distinct après revue.
