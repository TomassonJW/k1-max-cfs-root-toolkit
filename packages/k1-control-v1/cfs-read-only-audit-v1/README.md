# CFS-READ-ONLY-AUDIT-V1

Ce paquet observe la pile CFS exacte sans envoyer de G-code et sans modifier
la K1. Il sépare quatre niveaux de preuve :

1. présence à un capteur ;
2. identité du matériau ;
3. route outil logique, CFS et slot physique ;
4. débit réellement visible à la buse.

Le collecteur public est
`scripts/run-k1-control-cfs-read-only-audit-v1.ps1`. Les captures restent sous
`inventory/raw/` et ne sont pas publiées. `analyze_capture.py` contrôle les
empreintes avant/après, l'état sûr de la K1 et le verdict de cette capture.

Ce paquet n'autorise ni chargement, ni coupe, ni purge, ni impression. Une
future preuve de débit est une gate physique séparée.
