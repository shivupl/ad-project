import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm
import layer2_generation.strategy_agent as sa

captured = {}

def fake_json(content, **kw):
    captured["content"] = content
    return {"caption": {}, "graphic": {}}

# stub out the LLM + the context builders so we can inspect the assembled prompt
llm.complete_json = fake_json
sa.brain_to_context = lambda brain, product_name=None, topic=None: "BRAIN"
sa.marketing_profile_to_context = lambda brand: "PROFILE"

sa.generate_brief("Topic X", {"key_metrics": []}, steer="lean on cost savings")
assert "lean on cost savings" in captured["content"], "steer text missing from prompt"

sa.generate_brief("Topic X", {"key_metrics": []})
assert "lean on cost savings" not in captured["content"], "stale steer leaked"
assert "ADDITIONAL DIRECTION" not in captured["content"], "steer block present without steer"

print("OK: steer reaches the prompt only when provided")
