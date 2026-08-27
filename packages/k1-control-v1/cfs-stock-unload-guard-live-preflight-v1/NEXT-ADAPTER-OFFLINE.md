# Prochaine étape proposée — adaptateur hors imprimante du garde CFS

Nom technique proposé :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-OFFLINE-V1`.

## En langage courant

Construire sur l'ordinateur un petit traducteur entre la réponse réelle de la
K1 et le garde déjà testé. Il transformera par exemple `box.T1.filament=A` en
route `T1A`, et les états `connect` en liste des deux CFS présents.

Il travaillera uniquement avec des exemples nettoyés, sans numéro de série ni
identité matérielle. Il vérifiera les cas route absente, route unique, route
ambiguë, CFS déconnecté, état incomplet et températures invalides.

Cette étape est utile avant toute nouvelle action matérielle : elle prouvera
que les données réelles sont traduites sans hypothèse cachée. Elle ne se
connectera pas à la K1 et ne pourra envoyer aucun G-code.

Le GO exact de cette mission autorisera seulement ce travail hors imprimante.
Une connexion ou un retrait réel restera interdit jusqu'à une gate ultérieure
distincte.
