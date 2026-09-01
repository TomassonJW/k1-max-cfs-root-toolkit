from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectAuthorityPolicyTests(unittest.TestCase):
    def test_agents_defines_goal_based_authority(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        section = agents.split("## Autorité par objectif", 1)[1]
        section = section.split("## Hard prohibitions", 1)[0]
        self.assertIn("Un Goal actif", section)
        self.assertIn("Aucune\nphrase `GO ...` exacte", section)
        self.assertIn("contrôles techniques internes", section)
        self.assertIn("Une action physique n'est couverte que", section)

    def test_current_handoff_never_requests_a_literal_gate(self):
        handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        current_name = "HANDOFF-CUTTER-SENSOR-PAUSE-2026-09-01.md"
        self.assertIn(current_name, handoff)
        current = (ROOT / current_name).read_text(encoding="utf-8")
        normalized_current = " ".join(current.split())
        self.assertNotIn("autoriser littéralement", current)
        self.assertIn("2/7", current)
        self.assertIn("ATTENDRE_GO", current)
        self.assertIn("aucun identifiant technique n'est à recopier", normalized_current)
        self.assertIn("cut_pos : 0→1→0", current)
        self.assertIn("qualification manuelle du capteur", current)
        self.assertIn("source reste visible", current)
        self.assertIn("non archiv", current)

    def test_adr_and_decision_preserve_technical_safety_controls(self):
        adr = (
            ROOT
            / "docs"
            / "adr"
            / "ADR-014-autorite-par-objectif-et-autonomie-agent.md"
        ).read_text(encoding="utf-8")
        decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        self.assertIn("Statut : accepté explicitement par Thomas", adr)
        for control in ("backup", "empreintes", "validation indépendante", "rollback"):
            self.assertIn(control, adr)
        self.assertIn("## D-054", decisions)
        self.assertIn("contrôles techniques", decisions)

    def test_internal_gate_tokens_remain_script_assertions(self):
        deployer = (
            ROOT
            / "scripts"
            / "deploy-k1-control-calibration-ui-navigation-v1.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-CALIBRATION-UI-NAVIGATION-V1", deployer)
        self.assertIn("-Gate", deployer)

    def test_four_macro_goals_end_the_project_without_hidden_required_phase(self):
        goals = (ROOT / "GOALS.md").read_text(encoding="utf-8")
        normalized_goals = " ".join(goals.split())
        self.assertIn("quatre Goals pour terminer le projet", normalized_goals)
        self.assertIn("Quand ce Goal passe, le projet est **terminé**", normalized_goals)
        self.assertIn("aucune gate obligatoire ne reste ouverte", normalized_goals)
        self.assertNotIn("## Horizons après ces quatre Goals", goals)
        self.assertNotIn("Gate G5 reste obligatoire", goals)


if __name__ == "__main__":
    unittest.main()
