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
        current_header = "\n".join(handoff.splitlines()[:25])
        self.assertNotIn("autoriser littéralement", current_header)
        self.assertIn("préparer hors imprimante la campagne quatre sous-grilles", current_header)
        self.assertIn("Aucun `GO` exact", current_header)

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


if __name__ == "__main__":
    unittest.main()
