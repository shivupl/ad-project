import anthropic
import os
from dotenv import load_dotenv
import base64
import json
from extract_brand import brand_to_prompt
from strat_agent import generate_brief, brief_to_post_content, brief_to_caption


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

topic = "CreditX deployment speed"
# topic = "why lenders still take 9-12 months to build credit scorecards"
product_name = "CreditX"

with open("brain_finbots.json") as f:
    brain = json.load(f)

brief = generate_brief(topic, brain, product_name=product_name)
caption = brief_to_caption(brief)
post_content = brief_to_post_content(brief, logo_b64)

with open("caption.txt", "w") as f:
    f.write(caption)

print("--- LINKEDIN CAPTION ---")
print(caption)
print("\n--- GRAPHIC CONTENT ---")
print(post_content)


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