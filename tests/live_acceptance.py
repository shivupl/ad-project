"""Live acceptance for the concept-review-gate split. 2 runs each on Finbots
(B2B), Stripe (B2B), Hims (emotional) through generate_brief -> render_from_brief
— the same halves the Streamlit page drives. Needs ANTHROPIC_API_KEY in .env."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from layer2_generation.strategy_agent import generate_brief
from layer2_generation.graphic_generator import render_from_brief

DATA = ROOT / "data"
OUT = DATA / "acceptance"; OUT.mkdir(exist_ok=True)

def finbots_logo():
    p = OUT / "finbots_wordmark.png"
    if not p.exists():
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (260, 64), (255, 255, 255, 0)); d = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except Exception: font = ImageFont.load_default()
        d.text((8, 8), "finbots", fill=(0, 188, 112, 255), font=font); img.save(p)
    return str(p)

CASES = [
    ("finbots", "brand_finbotsai.json", "brain_finbotsai_(finbotsai_pte_ltd).json",
     finbots_logo(), "Deploying a live credit scorecard in one day with CreditX"),
    ("stripe", "brand_stripe.json", "brain_stripe.json", str(DATA / "logo_stripe.png"),
     "Recover more revenue automatically with smarter payment retries"),
    ("hims", "brand_hims.json", "brain_hims_&_hers_health,_inc.json", str(DATA / "logo_hims.png"),
     "Skip the waiting room: care that comes to you"),
]

fails = []
for name, bf, brf, logo, topic in CASES:
    try:
        with open(DATA / bf) as f:
            brand = json.load(f)
        with open(DATA / brf) as f:
            brain = json.load(f)
    except Exception as e:
        print(f"{name}: LOAD FAILED {e}")
        fails.extend([f"{name}_1", f"{name}_2"])
        continue
    for i in (1, 2):
        tag = f"{name}_{i}"
        try:
            brief = generate_brief(topic, brain, brand=brand)
            assert brief, "empty brief"
            res = render_from_brief(brief, brand, logo,
                                    html_path=str(OUT / f"{tag}.html"),
                                    png_path=str(OUT / f"{tag}.png"),
                                    brief_path=str(OUT / f"{tag}.brief.json"),
                                    caption_path=str(OUT / f"{tag}.caption.txt"))
            ok = bool(res.get("png_path"))
            print(f"{tag}: skill={res.get('design_skill')} png={'yes' if ok else 'NO'} warnings={res.get('warnings')}")
            if not ok:
                fails.append(tag)
        except Exception as e:
            print(f"{tag}: EXCEPTION {e}"); fails.append(tag)

print("\nRESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
