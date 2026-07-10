import anthropic
import os
from dotenv import load_dotenv
import base64
import json
from extract_brand import brand_to_prompt
from strat_agent import generate_brief, brief_to_post_content


load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
skill = open("SKILL2.md").read()
# skill = open("SKILL.md").read()


system_prompt = f"""{skill}
You are generating a marketing graphic as a self-contained HTML file.

CRITICAL OUTPUT RULES:
- Output ONLY raw HTML — no markdown, no backticks, no explanation
- The graphic must be exactly 1200x627px (LinkedIn format)
- Everything must be self-contained — no external images
- Google Fonts via @import is allowed
- All content must be visible without scrolling
- Do not truncate — output the complete HTML file including closing tags
"""

# Load logo as base64
with open("logo.png", "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode()



with open("brand_finbotsai.json") as f:
    profile = json.load(f)


# Brand prompt
brand = brand_to_prompt(profile)


post_content = f"""
Embed this exact logo in the HTML as a base64 data URI:
<img src="data:image/png;base64,{logo_b64}" alt="finbots.ai" style="max-height:36px" />

POST TYPE: Stat callout
EXACT COPY — do not change any wording:
- Stat hero: "1 Day"
- Contrast line: "vs 9–12 months industry average"
- Headline: "Build and deploy credit scorecards in a day"
- Subtext: "finbots.ai CreditX automates the entire scorecard pipeline — from raw data to deployed model"
- Supporting metrics (show all three):
  · >20% increase in loan approvals
  · >15% decrease in loss rates
  · <0.03 sec decision time
- CTA: "Book a demo → finbots.ai"
"""


## LLM Call
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    system=system_prompt,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": logo_b64
                    }
                },
                {
                    "type": "text",
                    "text": (
                        f"Embed this exact logo in the HTML (do not change the base64):\n"
                        f'<img src="data:image/png;base64,{logo_b64}" alt="Veloris" '
                        f'style="max-height:36px" />\n\n'
                        + brand
                        + post_content
                    )
                }
            ]
        }
    ]
)

html = response.content[0].text

with open("output.html", "w") as f:
    f.write(html)

print("Done — open output.html in browser")