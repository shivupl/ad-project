---
name: brand-canvas-design-v2
description: Tuned variant of brand-canvas-design. Same philosophy-first, art-directed approach; adds binding philosophy commitments, geometric discipline for monumental type, a negative-space quota, and concrete craft levers.
---

These are instructions for creating branded marketing graphics that feel like art objects rather than templates — while never sacrificing the brand system or the marketing message. Output is always a single self-contained HTML file at an exact canvas size, ready for screenshot rendering.

Complete this in two steps:
1. Brand Design Philosophy (written first, briefly, before any code)
2. Express it on the canvas (the HTML/CSS file)

---

## STEP 1 — BRAND DESIGN PHILOSOPHY

Before writing a single line of HTML, write a short design philosophy (2-4 paragraphs). This is a private artistic manifesto for this one graphic — it is thinking, not deliverable copy. Write it as an HTML comment placed immediately after `<!DOCTYPE html>` (never as prose outside the file).

### What the philosophy must be built FROM

Unlike pure art, this philosophy is not free invention. It must be derived from three fixed inputs:

1. **The brand system** — the exact colors, fonts, and logo provided. The philosophy interprets them: is this palette clinical or warm? Does this typeface whisper or declare? What world does this brand live in?
2. **The brand personality** — tone adjectives and target audience provided. "Authoritative, precise" for enterprise lenders demands a different aesthetic than "playful, glowing" for a skincare brand.
3. **The message** — the single most important idea in the brief (usually the headline or hero stat). The philosophy decides how that idea becomes *form*: a 1-day deployment speed might become velocity expressed through diagonal momentum; radiant skin might become luminance expressed through layered translucency and glow.

### How to articulate it

**Name the movement** (1-2 words), rooted in the brand — e.g. "Kinetic Trust" for a fintech speed story, "Botanical Minimalism" for a clean-beauty brand.

**Write 2-4 paragraphs** covering how the philosophy manifests through space, color, scale, rhythm, and composition — using the brand's actual palette and typography as the raw material. Each design aspect mentioned once; no redundancy.

**End the philosophy with three binding commitments** the code MUST visibly honor — this is what makes the manifesto real instead of decorative:

```
COMMITMENTS:
1. Gesture: <the one dominant visual gesture, in one sentence>
2. Palette logic: <which brand color dominates, which accents, and why>
3. Silence: <where the negative space lives on this canvas>
```

If the finished HTML does not deliver all three, it has failed the brief.

### The subtle conceptual thread

Find the conceptual DNA of the message and weave it invisibly into the composition. The product's core value should be *felt* in the form before a single word is read: speed as directional energy, security as enclosure and weight, growth as ascending rhythm, purity as negative space. Someone who knows the brand should sense it intuitively; everyone else simply experiences a masterful composition. Never literal, always sophisticated.

---

## STEP 2 — CANVAS CREATION

With the philosophy established, express it as a single self-contained HTML file.

### Non-negotiable pipeline constraints

These override artistic freedom. Every graphic must:

- **Exact canvas size**: use the dimensions specified in the brief (`canvas` field, e.g. 1080x1080; default 1200x627 if unspecified). Fixed pixel dimensions on the root container — never viewport-relative.
- **Self-contained**: no external images or dependencies. Google Fonts via `@import` is the only permitted external resource. The logo is embedded as the base64 data provided.
- **Exact brand colors**: the provided hex values, used as CSS variables. The philosophy interprets the palette; it never replaces it. Derived tints/shades/alphas of brand colors are allowed for atmosphere; foreign hues are not.
- **Brand fonts**: the provided font families. If none are provided, choose distinctive Google Fonts that serve the philosophy — never Arial, Inter, Roboto, or system defaults.
- **All provided copy appears verbatim**: headline, stat hero, contrast line, subtext, metrics, CTA — whichever fields the brief provides must appear, unaltered. This skill treats them as visual material, it never edits or omits them.
- **Logo placement**: as specified in the brief (default top-left, max-height 36px), with clear space around it.
- **No animation, no hover states, no interactivity** — the file will be rendered to a static image.
- **Nothing overlaps unintentionally, nothing falls off the canvas.** Every element within bounds with breathing room. Non-negotiable for professional production.

### The visual-first hierarchy

This is where this skill departs from data-forward layout:

- **One dominant visual gesture** carries the composition — a monumental typographic element, a commanding color field, a sculptural arrangement of form. Everything else is subordinate.
- **Text as visual architecture — with owned geometry**: the headline or hero stat is not placed *on* the design — it *is* the design. Scale it fearlessly, but monumental type must OWN its footprint: before committing to a font size, reason about the rendered width of the actual words at that size, decide deliberately whether the line breaks (and where), and reserve that exact space in the layout. A hero that wraps by accident and lands on the copy below it is the single most common failure of this style. When in doubt: one line, `white-space: nowrap`, sized to fit with margin to spare — or a deliberate multi-line composition where every break is chosen.
- **Secondary copy (metrics, subtext, CTA) recedes**: small, precise, positioned like clinical annotations or quiet labels — present and legible, never competing with the gesture.
- **The silence quota**: at least a third of the canvas stays quiet — no text, no competing marks, only atmosphere. Visual-first design dies the moment every region is filled. The negative space is a design element; place it deliberately (that is commitment #3).
- **Atmosphere over flatness**: build depth with layered gradients, geometric structure, pattern, translucency, and grain — always derived from the brand palette. A flat solid background is a failure of imagination.
- **Repetition and system**: repeating marks, ruled lines, systematic patterns reward sustained viewing and signal painstaking craft. Borrow the visual language of systematic observation — as if this graphic were a diagram from an imaginary discipline studying the brand's promise.

### Craft levers (use these, not vibes)

Craftsmanship is executed through specific decisions, not effort adjectives:

- **Spacing rhythm**: every margin, gap, and padding sits on one modular scale (e.g. 8 → 16 → 24 → 40 → 64). No arbitrary values.
- **Optical alignment**: align to the glyphs, not the boxes — large display type needs negative left margin to sit optically flush; punctuation hangs.
- **Two families maximum**, three sizes of display hierarchy maximum. Weight and spacing do the work between them.
- **Letter-spacing regimes**: tight (-0.02 to -0.04em) on monumental display; generous (+0.08 to +0.2em) on small uppercase labels; body untouched.
- **Numerals**: hero stats use the display face; supporting figures use `font-variant-numeric: tabular-nums` so digits align like instrumentation.
- **One accent moment**: the brand accent color appears where the eye must land — and almost nowhere else.

### Craftsmanship standard

To achieve human-crafted quality: make it appear as though someone at the top of their field labored over every detail. Composition, spacing, optical alignment, color calibration, typographic rhythm — everything at expert level. The result should be undeniably impressive at full size and still striking at thumbnail scale.

---

## FINAL STEP — THE REFINEMENT PASS

The user ALREADY said: "It isn't perfect enough. It must be pristine — a masterpiece of craftsmanship."

Take a second pass over the completed HTML. Do NOT add more graphics or new elements. Instead refine what exists: tighten optical spacing, calibrate color relationships, perfect the typographic scale, verify nothing overlaps and every margin breathes. Re-read your three COMMITMENTS and confirm each is visibly delivered. If the instinct is to draw a new shape, STOP and ask instead: "How can I make what's already here more of a piece of art?"

Verify against the constraints one final time: exact canvas size, exact hex values, all copy verbatim, logo placed correctly, fully self-contained. Then output the single HTML file.
