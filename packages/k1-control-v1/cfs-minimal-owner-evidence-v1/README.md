# CFS Minimal Owner Evidence V1

Statut : **gate close en KO borné ; preuve de retrait ajoutée ; aucun message
appelable et aucun transport**.

Cette mission a exploité uniquement des preuves déjà locales et des références
publiques en lecture seule. Elle n'a établi aucune connexion avec la K1 et n'a
jamais chargé, importé ou exécuté le module MIPS capturé.

Le principal résultat est positif mais étroit : un ancien journal contient un
cycle constructeur de retrait sur `T1A`, avec deux requêtes `RETRUDE_PROCESS`,
leurs réponses réussies, un timeout hôte de 150 secondes et le passage du
capteur local de « filament présent » à « libre ».

Ce résultat ne suffit pas à rendre les trames appelables. Il manque toujours la
preuve d'exclusion du propriétaire constructeur, les autres slots, le second
CFS, la coupe et la purge isolées, ainsi que les règles sûres après timeout et
reconnexion.

## Contenu

- `contract.json` : verdict, portée et liste appelable vide ;
- `evidence-map.json` : carte nettoyée des preuves locales et références
  publiques ;
- `verify_private_evidence.py` : vérificateur local sans transport ni chargement
  binaire ;
- `PASSIVE-CAPTURE-PROTOCOL.md` : protocole préparé pour une gate physique
  ultérieure, non autorisée par ce paquet ;
- `RESULT.md` : clôture opérationnelle.

## Vérification locale

Depuis la racine du dépôt :

```powershell
python packages\k1-control-v1\cfs-minimal-owner-evidence-v1\verify_private_evidence.py
```

Le marqueur vert confirme uniquement la cohérence des preuves historiques et
du refus. Il ne qualifie aucun envoi vers la K1.
