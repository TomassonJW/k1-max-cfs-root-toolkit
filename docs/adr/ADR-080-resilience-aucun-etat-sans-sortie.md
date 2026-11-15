# ADR-080 - Aucun état sans sortie : la résilience devient une règle

Date : 15 novembre 2026. Statut : accepté ; tranche 1 construite hors
imprimante, non posée. Document 109.

## Contexte

Du 15 septembre au 15 novembre, onze familles de pannes (document 109). Chaque
correctif a fermé un chemin ; le suivant est apparu ailleurs. Presque toutes
les sorties passaient par une console, un redémarrage de Klipper ou une IA.
Thomas demande que ce ne soit plus possible.

## Décision

1. Sept principes, document 109 section 3 : aucun état sans sortie ; rien
   d'essentiel en mémoire seule ; reprendre dans la même opération d'abord ;
   retour au repos propre ; tout dans Klipper ; une installation unique ; chaque
   refus dit en clair. Un paquet qui crée un état sans sortie est refusé.
2. Le slot du filament en tête est écrit sur disque
   (`/usr/data/k1-control-v1/state/kctrl_head.json`), à chaque changement
   prouvé, et vaut attribution au départ suivant. La route du CFS lue reste la
   preuve la plus forte ; la purge au bac prouve toujours la consommation.
3. Une fin ratée ne bloque plus le lancement suivant. La porte refuse
   seulement une fin en cours, illisible, ou des chauffes non confirmées à
   zéro. `START_PRINT` remet la fin à zéro et le départ reprouve filament,
   route et géométrie.
4. Après un départ arrêté tête au bac, sortie vers Y273 à hauteur constante,
   seulement axes référencés et plateau à 30 mm au moins, sous la garde du
   bac. Les drapeaux de pause stock et l'erreur CFS gardée ne sont pas
   touchés.
5. Les poses deviennent multi-fichiers, une sauvegarde et un retour par
   fichier.

## Alternatives écartées

- Une commande de remise à zéro de la fin : encore une console.
- Redémarrer Klipper automatiquement : perd la référence et la route, interdit
  en impression.
- Réécrire la route du CFS depuis le disque : invente une route non prouvée.
- Un bouton d'acquittement obligatoire après une fin ratée : un clic de plus,
  aucune preuve de plus, le départ vérifie déjà tout.
- Effacer la pause stock sans l'erreur CFS gardée : le fichier suivant se
  mettrait en pause avant sa première ligne.

## Conséquences

- Après un redémarrage, une coupure ou un arrêt d'urgence, filament en tête,
  le départ suivant purge et part, sans `KCTRL_RETAINED_ADOPT`.
- Après une fin ou une annulation ratée, le lancement suivant part ; la page
  Bobines dit ce qui s'est passé.
- Un filament changé à la main imprimante éteinte n'est pas vu ; la purge
  refuse si le tampon ne se vide pas.
- Les paquets antérieurs épinglent les anciens `kctrl_start.py` et
  `kctrl_print_gate.py` : retour arrière de celui-ci d'abord.
- Les tranches 2 à 6 restent à construire, dans l'ordre du document 109.
