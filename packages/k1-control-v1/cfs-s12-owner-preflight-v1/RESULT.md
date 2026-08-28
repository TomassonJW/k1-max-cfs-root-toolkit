# Résultat du préflight propriétaire CFS S12 V1

Statut : `CLOSED_READ_ONLY_S12_SURFACE_CONFIRMED_EFFECTS_CLOSED`

La collecte unique a joint la K1 pendant environ six secondes. La machine était
au repos, les deux chauffes demandaient `0 °C`, aucune commande CFS n'était en
cours, les deux CFS `1.1.3` étaient connectés et le profil
`k1_p001_t055_r001_n11x11` était actif.

Le chargeur et le binaire CFS ont exactement les mêmes empreintes que les
captures historiques. Le binaire n'a donc pas été recopié et sa cartographie
précédente n'a pas été jetée. La lecture fraîche retrouve 66 noms `BOX_*`, les
11 commandes nécessaires à la carte de propriétaire et les 13 rappels internes
obligatoires. Les 17 marqueurs examinés par le collecteur sont tous présents.

La configuration active confirme notamment le repli stock à `220 °C`, ses
positions de coupe, chargement et nettoyage, ainsi que 31 appels `BOX_*`. Le
binaire exact contient aussi `G28`, `M104`, `M109`, `BED_MESH_CLEAR`, `PAUSE`
et `RESUME`. Cela confirme que les grosses séquences stock ne doivent pas devenir
le propriétaire du démarrage, du changement ou de la fin de bobine.

L'API d'aide Klipper ne publie que cinq macros haut niveau auxquelles un texte
d'aide est associé. Elle ne publie pas les commandes compilées plus basses. Ce
n'est pas un KO : l'objet `box` était actif, le binaire exact était chargé et
les noms attendus sont tous présents dans ce binaire. Cette limite est désormais
traitée explicitement au lieu d'être confondue avec une commande absente.

L'auto-remplacement reste réalisable par notre futur propriétaire : les états
`auto_refill`, `enable`, `same_material`, les commandes de contrôle et les
rappels de fin de bobine sont présents. Au moment précis de la capture, la valeur
stock était activée, mais les six groupes reconnus ne contenaient chacun qu'un
seul emplacement. Il n'y avait donc pas de paire de bobines reconnue comme
identique par le stock à cet instant.

Cette gate ne qualifie aucun chargement, retrait, cutter, purge, runout, retry,
reprise ou fin d'impression. Elle n'autorise aucune pose. Elle ouvre seulement
la préparation hors imprimante du propriétaire K1 Control contre cette réponse
enregistrée ; chaque primitive physique restera une gate séparée avec Thomas
devant la K1.
