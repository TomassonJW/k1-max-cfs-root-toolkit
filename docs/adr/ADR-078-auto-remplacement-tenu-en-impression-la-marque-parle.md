# ADR-078 - En impression, l'auto-remplacement CFS reste actif ; la marque d'un capteur contredit ne fait que parler

Date : 12 novembre 2026. Statut : accepté ; posée et validée au repos le
12 novembre à 16:27, pas encore vue sur une impression. Remplace le point 2 et le point 4 de ADR-077.

## Contexte

ADR-077 coupe l'auto-remplacement quand un capteur CFS reste contredit 180 s et
400 mm, pour qu'une fausse erreur ne déclenche pas la routine stock après la
fin. Le 12 novembre (document 106), la V1 a marqué T1B à 04:25:06 et coupé.
À 06:04:09, le CFS 1 a répondu `FILAMENT_ERR` sur T1B, `key839`, case B
toujours vue par son masque `connections`. Auto-remplacement coupé, le module
stock a mis l'impression en pause, poussé 3000 mm au bac en 25 min puis laissé
le CFS au repos (`mode = 0`) : sans mou, la première reprise n'a rien déposé.

La même fausse erreur, auto-remplacement actif, a laissé l'impression tourner
à 04:22:06 cette nuit-là, le 1er novembre à 07:07 et le 31 octobre à 19:01.
Pendant l'impression, la coupe est donc la cause de la pause, pas une
protection. Après la fin, la fin V5 coupe déjà l'auto-remplacement elle-même
avant la coupe (ADR-076), et la fenêtre de fin arrête toute poussée.

## Décision

Paquet `packages/k1-control-v1/cfs-sensor-guard-v2`, même module et même
section que la V1, révision `cfs-sensor-guard-v2`.

1. La marque d'un capteur contredit ne fait qu'une ligne de console. Plus
   aucune coupure de l'auto-remplacement.
2. Pendant l'impression (`printing`, fichier ouvert, hors des phases de la fin
   K1 Control), un auto-remplacement lu à 0 pendant 30 s est remis à 1 sous le
   verrou G-code, prouvé par deux lectures, nouvel essai toutes les 10 s.
   Option `keep_auto_refill`, vraie par défaut. Jamais en pause, jamais après
   la fin du fichier.
3. `START_PRINT` lit l'auto-remplacement à 1 ou le remet, prouvé par deux
   lectures, sinon refuse le départ.
4. En pause, fichier ouvert, après un `key839` ou un signalement sur le slot
   qui imprimait : si le masque `connections` voit encore la case, une ligne
   « fausse fin probable » avec la reprise ; si le CFS est lu au repos, une
   ligne avec le `BOX_SET_BOX_MODE` qui rend le mou. Aucune action.
5. La fenêtre de fin et son arrêt d'urgence restent ceux de ADR-077.

## Alternatives écartées

- Garder la coupe et arrêter la routine stock en pause : la routine est dans
  le module compilé ; l'interrompre de l'extérieur pendant qu'elle pousse
  risque une tête à moitié chargée.
- Remettre le mode impression automatiquement en pause : `BOX_SET_BOX_MODE`
  pendant une routine stock ou une vraie fin non prouvée peut pousser sans
  contrôle. Le geste reste à Thomas, guidé par la console.
- Ne rien changer et compter sur la procédure de reprise : la pause et la purge
  de 3 m ont déjà eu lieu.

## Conséquences

- Une fausse erreur en impression ne devrait plus mettre en pause. Trois cas
  observés le montrent ; le code stock, compilé, ne le prouve pas.
- Un vrai bout de bobine garde son relais stock pendant toute l'impression.
- Un auto-remplacement mis à 0 exprès pendant l'impression est remis à 1, sauf
  `keep_auto_refill: False`.
- Une fausse erreur dans la seconde et demie avant la coupe de la fin V5 relève
  de la fenêtre de fin.
- Pose au repos revérifié, accord de Thomas, préflight d'abord. Seul le module
  change ; la configuration de la V1 est épinglée. Retour arrière : V2 vers V1
  d'abord, puis celui de la V1.
