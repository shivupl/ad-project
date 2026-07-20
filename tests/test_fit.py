import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm
import layer2_generation.strategy_agent as sa

# 1) within-limits brief: untouched, no LLM call (llm raises to prove it isn't called)
llm.complete_json = lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM should not be called"))
brief = {"graphic": {"headline": "Deploy in 1 day", "cta": "Book a demo",
                     "metrics": ["-92% deploy time", "+96 pts GINI"]}}
out, changes = sa.fit_brief_copy(brief)
assert changes == [], f"expected no changes, got {changes}"
assert out["graphic"]["headline"] == "Deploy in 1 day"

# 2) metric count > 2: deterministic truncation, still no LLM
brief2 = {"graphic": {"headline": "Deploy in 1 day", "cta": "Book a demo",
                      "metrics": ["a", "b", "c", "d"]}}
out2, changes2 = sa.fit_brief_copy(brief2)
assert out2["graphic"]["metrics"] == ["a", "b"], out2["graphic"]["metrics"]
assert any("metrics" in c for c in changes2)

# 3) over-limit headline: LLM trims it; other fields untouched
llm.complete_json = lambda *a, **k: {"headline": "Deploy a live scorecard in 1 day"}
long = "Deploy a fully live production credit scorecard in just one single day flat"
brief3 = {"graphic": {"headline": long, "cta": "Book a demo", "metrics": []}}
out3, changes3 = sa.fit_brief_copy(brief3)
assert out3["graphic"]["headline"] == "Deploy a live scorecard in 1 day"
assert out3["graphic"]["cta"] == "Book a demo"
assert any("headline" in c for c in changes3)

# 4) over-limit + LLM failure: headline left unchanged (graceful)
llm.complete_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
out4, changes4 = sa.fit_brief_copy({"graphic": {"headline": long, "cta": "x", "metrics": []}})
assert out4["graphic"]["headline"] == long, "should keep original on failure"

print("OK: fit_brief_copy conforms to fit and degrades gracefully")
