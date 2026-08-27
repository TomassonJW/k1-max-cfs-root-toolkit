# ADR-026 — Séparer la traduction K1 du garde de retrait

Date : 2026-08-27

Statut : accepté

## Contexte

Le préflight live a identifié les champs réels nécessaires au garde. Son
vérificateur savait déjà les lire, mais il était lié aux captures privées et à
leur format de preuve. Le contrôleur, lui, doit rester indépendant de la forme
Moonraker et de tout transport.

## Options

### 1. Faire lire directement la réponse K1 par le garde

Refusé. Le contrôleur mélangerait alors preuve de sécurité, forme du firmware et
futur transport. Chaque évolution de réponse pourrait modifier le chemin
d'effet.

### 2. Réutiliser le vérificateur de capture privée

Refusé. Ce module contrôle des empreintes, des blocs de journal et des sources
privées. Ce n'est pas une interface stable pour le garde.

### 3. Ajouter un adaptateur pur et fermé

Retenu. Une fonction sans réseau ni processus extrait uniquement huit champs
fonctionnels depuis une réponse déjà nettoyée. Elle ignore les champs inconnus,
refuse les données manquantes, incohérentes ou ambiguës et ne peut produire
aucune commande.

## Décision

Le garde conserve son format abstrait. L'adaptateur devient l'unique frontière
entre une future réponse K1 nettoyée et ce format. Une route absente ou un CFS
déconnecté sont traduits pour que le garde les refuse avec sa règle normale.
Plusieurs routes, un slot actif sur une unité déconnectée, une unité hors du
couple `T1/T2` ou une température invalide sont refusés par l'adaptateur.

## Conséquences

- le contrôleur reste testable sans firmware ni transport ;
- la forme K1 est centralisée dans un petit module ;
- les exemples publics restent synthétiques et sans identité matérielle ;
- aucune réponse privée n'entre dans Git ;
- une future validation live devra nettoyer avant traduction et ne devra pas
  appeler le chemin d'effet du garde ;
- aucune connexion, pose ou action physique n'est autorisée par cette décision.
