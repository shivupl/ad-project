import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from layer2_generation.strategy_agent import brief_to_summary

brief = {"post_type": "stat_callout",
         "graphic": {"headline": "Deploy in 1 day", "stat_hero": "1 Day",
                     "contrast_line": "vs 9-12 months", "subtext": "No code.",
                     "metrics": ["-92% deploy", "+96 GINI"], "cta": "Book a demo"},
         "caption": {"hook": "Scorecards used to take months."}}
s = brief_to_summary(brief)
for token in ["Stat Callout", "Deploy in 1 day", "1 Day", "vs 9-12 months",
              "-92% deploy", "Book a demo", "Scorecards used to take months"]:
    assert token in s, f"missing {token!r} in summary"
print("OK: brief_to_summary renders the key fields")
