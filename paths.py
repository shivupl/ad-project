from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FRONTEND_DESIGN_SKILL = ROOT / "frontend_design_skill.md"
LINKEDIN_STRATEGY_SKILL = ROOT / "linkedin_strategy_skill.md"

DATA_DIR.mkdir(exist_ok=True)
