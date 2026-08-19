# Rapport de nettoyage — capture longue de production

Date : 2026-08-20

Capture source privée : `20260819-215124-long`

## Fichiers publiables produits

- `findings.md`
- `event-summary.csv`
- `sanitisation-report.md`

## Données volontairement exclues

- adresse réseau et alias SSH local ;
- identifiants uniques et trames brutes des deux CFS ;
- nom complet du fichier d'impression ;
- contenu du G-code ;
- journal Klipper brut ;
- chemins locaux privés ;
- informations de connexion et clés SSH.

## Transformations

- Les événements ont été réduits aux heures, états et valeurs nécessaires au diagnostic.
- Les logements CFS exacts ont été remplacés par une description fonctionnelle dans le rapport public.
- Aucune ligne brute susceptible de contenir un identifiant matériel n'a été copiée.
- Les conclusions distinguent mesure directe, déclaration humaine et interprétation.

## Contrôle

Les fichiers nettoyés ne contiennent pas d'adresse IP, d'adresse MAC, de secret, de clé publique ou privée, de numéro de série, d'identifiant matériel CFS, ni de copie de code constructeur.

La trace brute reste locale, ignorée par Git. Son empreinte SHA-256 est conservée uniquement dans le relevé privé afin de permettre un contrôle d'intégrité sans publier son contenu.
