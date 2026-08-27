# Adaptateur hors ligne du garde de retrait CFS V1

Date : 2026-08-27

Mission : `G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`

Verdict : **OK hors imprimante ; traduction déterministe ; production fermée**.

## But

Transformer une réponse K1 déjà nettoyée en huit valeurs simples comprises par
le garde : état d'impression, état CFS, unités connectées, commande active,
route engagée, deux consignes thermiques et présence du segment dans la tête.

Le paquet ne sait ni lire la K1, ni envoyer un G-code, ni lancer un programme
externe. Il n'est pas un adaptateur de transport.

## Refus sûrs

L'adaptateur refuse un champ absent, une valeur de mauvais type, une température
négative ou non finie, plusieurs routes, un slot actif sur une unité
déconnectée et une unité `T3/T4` déclarée connectée.
Un état d'unité inconnu est refusé au lieu d'être assimilé à une déconnexion.
La validation live suivante a ensuite prouvé la valeur exacte `None` pour les
unités non provisionnées `T3/T4` ; cette valeur précise est désormais reconnue
comme inactive, sans élargir les autres valeurs acceptées.

Une route absente reste traduite en liste vide. Un second CFS déconnecté reste
traduit en liste incomplète. Dans les deux cas, le garde peut ensuite expliquer
son refus normal avant toute commande.

## Vie privée

Les dix exemples sont synthétiques. Aucun numéro de série, UUID, adresse réseau
ou contenu de capture privée n'est versionné. L'adaptateur ne copie que les huit
champs autorisés et ignore toute donnée supplémentaire.

## Limite de la gate

Cette mission prouve seulement la traduction locale. Elle ne prouve pas qu'un
futur collecteur nettoie correctement toutes les variantes de réponse, ni que
la forme du firmware restera stable.

La prochaine gate proposée sera une validation live strictement en lecture
seule, distincte. Elle devra nettoyer la réponse avant l'adaptateur et ne devra
jamais appeler `StockUnloadGuard.run`.

## Vérifications obtenues

- dix scénarios synthétiques sur dix ;
- dix-sept tests ciblés sur dix-sept ;
- quarante-sept tests verts pour l'ensemble garde, mapping live et adaptateur ;
- suite complète : `429` tests exécutés, `426` verts et `3` ignorés connus ;
- aucun import réseau, série ou processus dans les modules du paquet ;
- aucun champ d'identité dans les exemples versionnés.
