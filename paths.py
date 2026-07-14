from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SKILLS_DIR = ROOT / "skills"
FRONTEND_DESIGN_SKILL = SKILLS_DIR / "frontend_design_skill.md"
LINKEDIN_STRATEGY_SKILL = SKILLS_DIR / "linkedin_strategy_skill.md"

DATA_DIR.mkdir(exist_ok=True)
