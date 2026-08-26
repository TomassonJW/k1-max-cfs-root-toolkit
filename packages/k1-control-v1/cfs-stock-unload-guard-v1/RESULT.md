# Résultat — CFS Stock Unload Guard V1

Verdict : **OK hors imprimante ; aucune connexion K1 ; aucune pose ; aucun
retrait réel**.

Le garde enveloppe la macro officielle sans tenter de reproduire le protocole
série interne du CFS. Il refuse avant tout effet si l'état est occupé, ambigu ou
incomplet. Après une tentative, il ne relance jamais le retrait et vérifie
toujours l'arrêt réel des chauffes.

Les scénarios couvrent le succès, le faux succès HTTP du retrait, le faux succès
HTTP de l'arrêt thermique, les erreurs de transport, l'échec stock, le
changement de route, la déconnexion CFS et le changement inattendu d'état de la
machine.

La prochaine étape n'est pas un retrait. Elle consiste à connecter un futur
adaptateur en lecture seule pour vérifier que chaque donnée exigée par le garde
existe réellement sur la K1 et possède le sens attendu.
