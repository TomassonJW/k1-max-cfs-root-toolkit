# Cœur propriétaire CFS hors imprimante V1

Ce paquet rend exécutable, uniquement sur le PC, la décision d’ADR-032 : K1
Control possède le cycle complet et le système Creality ne reste qu’un futur
exécutant de petites phases qualifiées séparément.

Le moteur couvre trois responsabilités :

- prendre puis rendre un verrou de propriétaire sans perdre la valeur précédente
  de l’auto-remplacement stock ;
- décider entre conserver, charger ou changer le filament au démarrage ;
- choisir un unique remplacement réellement identique après une fin de bobine,
  y compris dans le second CFS, puis autoriser une reprise K1 Control seulement
  après vérification complète.

## Refus sûrs

Le moteur bloque avant une nouvelle intention si la cartographie ou l’époque de
connexion change, si deux routes semblent engagées, si une commande CFS est
active, si le propriétaire stock rappelle son propre cycle, ou si l’identité
matière n’est pas exacte et approuvée.

Une bobine de remplacement doit avoir la même référence utilisateur, le même
type, la même couleur, le même diamètre et la même recette thermique. Zéro ou
plusieurs candidats laissent l’impression en pause. Un résultat d’effet
incertain n’est jamais rejoué et une intention déjà consommée ne peut pas être
réutilisée.

La reprise ne dépend pas d'un simple indicateur. Le moteur conserve et compare
le contexte structuré de pause : position de retour, modes, extrusion, mesh, Z,
cibles thermiques, ventilateurs, facteurs vitesse/débit, pressure advance,
outil logique, route, capteurs et fraîcheur de cartographie.

## Ce que produit le moteur

Il produit uniquement des intentions abstraites comme `load_selected_route` ou
`purge_visible`. Elles portent toutes `dispatchable=false`, au plus une tentative
et le nom de la future gate séparée qui devra qualifier l’effet réel.

Il ne contient aucun nom de commande `BOX_*`, encodeur de commande, connecteur,
G-code, accès réseau, écriture distante, script de pose ou candidat de
déploiement. Les observations d’effet utilisées par la matrice sont
synthétiques ; leur réussite ne qualifie aucune primitive sur la K1.

## Ancrage S12

La matrice relit le résultat nettoyé du préflight S12 et vérifie ses empreintes.
Elle conserve le fait réel suivant : l’auto-remplacement stock était actif et
aucune paire de bobines identiques n’était présente dans cette capture. Les
paires utilisées pour exercer l’algorithme sont donc explicitement fictives.

## Vérifier localement

```powershell
python packages\k1-control-v1\cfs-owner-core-offline-v1\run_scenarios.py
python -m unittest tests.test_cfs_owner_core_offline_v1 -v
```

La prochaine mission proposée préparera encore hors imprimante le garde exact
qui devra, plus tard et sous une autre autorité, désactiver une seule fois
l’auto-remplacement stock, vérifier l’effet et restaurer exactement sa valeur
précédente.
