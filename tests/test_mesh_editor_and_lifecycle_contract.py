from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MeshEditorAndLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = (
            ROOT / "docs" / "23-audit-mesh-manuel-et-cycle-production-cfs.md"
        ).read_text(encoding="utf-8")
        cls.mesh_adr = (
            ROOT
            / "docs"
            / "adr"
            / "ADR-015-profils-mesh-derives-et-corrections-locales.md"
        ).read_text(encoding="utf-8")
        cls.lifecycle_adr = (
            ROOT
            / "docs"
            / "adr"
            / "ADR-016-cycle-production-orchestre-et-propriete-cfs.md"
        ).read_text(encoding="utf-8")
        cls.lifecycle_contract = (
            ROOT / "docs" / "25-contrat-cycle-impression-nettoyage-cfs-v1.md"
        ).read_text(encoding="utf-8")
        cls.nomenclature_adr = (
            ROOT
            / "docs"
            / "adr"
            / "ADR-029-nomenclature-profils-mesh-et-reference-11x11.md"
        ).read_text(encoding="utf-8")
        cls.editor_contract = json.loads(
            (
                ROOT
                / "packages"
                / "k1-control-v1"
                / "mesh-editor-offline-v1"
                / "mesh-editor-contract.json"
            ).read_text(encoding="utf-8")
        )

    def test_interpolation_is_quantified_before_manual_tuning(self):
        self.assertIn("0,009877883 mm", self.audit)
        self.assertIn("0,000689867 mm", self.audit)
        self.assertIn("L'interpolation bicubique", self.audit)
        self.assertIn("pas la cause principale", self.audit)

    def test_source_profile_and_global_z_are_immutable_boundaries(self):
        self.assertIn("profil source immuable", self.mesh_adr)
        self.assertIn("normalisée à moyenne pondérée nulle", self.mesh_adr)
        self.assertIn("le Z accepté reste un objet distinct", self.mesh_adr)
        self.assertIn("Le profil source `k1_p001_t055_r001_n11x11` reste intact", self.mesh_adr)

    def test_editor_v1_is_numeric_bounded_and_reversible(self):
        for token in (
            "grille 2D `11 × 11`",
            "`0,005` et `0,010 mm`",
            "|delta| > 0,100 mm",
            "annuler, rétablir, dupliquer, comparer, rejeter et restaurer",
            "Le glisser-déposer vertical en 3D est repoussé",
        ):
            self.assertIn(token, self.mesh_adr)

    def test_nomenclature_keeps_11x11_best_current_but_no_profile_robust(self):
        normalized_adr = " ".join(self.nomenclature_adr.split())
        self.assertIn("tous les profils actuels ont des défauts", normalized_adr)
        self.assertIn("meilleur profil observé `11 × 11`", self.nomenclature_adr)
        self.assertIn("aucun profil actuel ne le possède", self.nomenclature_adr)
        nomenclature = self.editor_contract["nomenclature"]
        self.assertTrue(nomenclature["all_current_profiles_have_edge_defects"])
        self.assertEqual(
            "k1_p001_t055_r001_n11x11",
            nomenclature["best_current_observed_profile"],
        )
        self.assertFalse(nomenclature["robust_profile_currently_exists"])

    def test_one_job_contract_replaces_duplicate_stock_entry_points(self):
        self.assertIn("KCTRL_JOB_BEGIN", self.lifecycle_adr)
        self.assertIn("ni `G28`, ni `Tn`, ni `START_PRINT`", self.lifecycle_adr)
        self.assertIn("Chauffe du plateau immédiatement", self.lifecycle_adr)
        self.assertIn("Référence Z finale unique", self.lifecycle_adr)

    def test_pause_tool_change_and_runout_are_distinct(self):
        self.assertIn("`KCTRL_PAUSE_NORMAL`", self.lifecycle_adr)
        self.assertIn("n'appelle pas `BOX_RESUME_EXTRUDE`", self.lifecycle_adr)
        self.assertIn("`KCTRL_TOOL_CHANGE`", self.lifecycle_adr)
        self.assertIn("`KCTRL_RUNOUT_RECOVERY`", self.lifecycle_adr)
        self.assertIn("Le Z modifié volontairement pendant la pause est conservé", self.lifecycle_adr)

    def test_cfs_temperature_and_orca_cutover_fail_closed(self):
        self.assertIn("n'autorise pas un `220 °C`", self.lifecycle_adr)
        self.assertIn("une simple commande `M104` ajoutée après coup", self.lifecycle_adr)
        self.assertIn("Le retrait de l'ancien `+0,27 mm` est", self.lifecycle_adr)
        self.assertIn("atomique avec cette bascule", self.lifecycle_adr)

    def test_frozen_contract_keeps_correct_filament_and_requires_visible_flow(self):
        for token in (
            "Le bon filament déjà engagé est conservé",
            "Une présence capteur ne prouve ni l'identité du filament ni son écoulement",
            "purger dans tous les cas",
            "Prouver le débit",
            "Désengager et nettoyer",
        ):
            self.assertIn(token, self.lifecycle_contract)

    def test_frozen_contract_never_assumes_t0_and_separates_transition_temperatures(self):
        self.assertIn("Aucun `T0` ou autre outil physique n'est supposé", self.lifecycle_contract)
        self.assertIn("retrait de l'ancien filament à sa température explicite", self.lifecycle_contract)
        self.assertIn("purge de transition à une température explicitement fournie", self.lifecycle_contract)
        self.assertIn("retour à la température du nouveau filament", self.lifecycle_contract)
        self.assertIn("Le CFS n'est jamais propriétaire d'une température de travail", self.lifecycle_contract)

    def test_cleaning_is_manual_only_and_no_universal_temperature(self):
        for token in (
            "nettoyage manuel obligatoire",
            "Aucun brossage automatique",
            "Thomas confirme visuellement `NOZZLE_VISIBLY_CLEAN`",
            "Elles ne sont plus une recette exécutable",
            "Il n'existe pas de `+10 °C`, `+20 °C`, `−30 °C` ou `100 °C` universel",
        ):
            self.assertIn(token, self.lifecycle_contract)

    def test_mid_print_change_and_end_policy_are_complete(self):
        for token in (
            "Aucun homing n'est effectué pendant l'impression",
            "pression d'avance",
            "La purge arrière chasse l'ancien matériau",
            "tour de purge",
            "retrait complet et rembobinage",
            "Il n'existe pas de réchauffage automatique différé",
        ):
            self.assertIn(token, self.lifecycle_contract)

    def test_editor_is_closed_next_gate_is_physical_and_precision_stays_hidden(self):
        gates = (ROOT / "GATES.md").read_text(encoding="utf-8")
        self.assertIn("### `MESH-EDITOR-OFFLINE-V1`", gates)
        self.assertIn(
            "Statut : **passée le 25 août 2026 ; aucune connexion ni mutation K1**",
            gates,
        )
        self.assertIn("### `MESH-EDGE-DIAGNOSTIC-V1`", gates)
        self.assertIn("Statut : **en cours ; passage source sans débit invalide", gates)
        self.assertIn("Elle n'autorise pas automatiquement une impression", gates)
        self.assertIn("Le mode Précision n'est exposé qu'après deux feuilles", gates)


if __name__ == "__main__":
    unittest.main()
