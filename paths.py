from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SKILLS_DIR = ROOT / "skills"
# Design skills (graphic generator), routed by marketing profile in _choose_design_skill:
B2B_GRAPHIC_SKILL = SKILLS_DIR / "b2b_graphic_skill.md"                    # active B2B / rational lane
B2B_MINIMAL_SKILL = SKILLS_DIR / "b2b_minimal_skill.md"                    # minimal, content-adaptive B2B option (not routed by default)
EMOTIONAL_ART_SKILL = SKILLS_DIR / "emotional_art_direction_skill.md"      # emotional / D2C / minimal lane
DATA_FORWARD_LEGACY_SKILL = SKILLS_DIR / "data_forward_legacy_skill.md"    # retired old B2B skill; kept only as a defensive fallback
# Strategy + review personas:
LINKEDIN_STRATEGY_SKILL = SKILLS_DIR / "linkedin_strategy_skill.md"
SENIOR_DESIGNER_SKILL = SKILLS_DIR / "senior_designer_skill.md"

DATA_DIR.mkdir(exist_ok=True)
