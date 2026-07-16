---
name: brand-canvas-design
description: Create visually-led, art-directed marketing graphics as self-contained HTML/CSS files using a design-philosophy-first approach. Use this skill whenever generating a marketing graphic where visual impact matters more than information density — brand awareness posts, launch moments, lifestyle/consumer (D2C) brands, Instagram-first content, or any brief whose design notes call for "expressive," "atmospheric," "bold," or "visual-first" treatment. Also use it when a standard data-forward layout would feel generic for the brand's personality. The graphic must still carry exact brand colors, fonts, logo, and the exact marketing copy provided (headline, stat, CTA) — this skill makes them art, it never drops them.
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

**Emphasize craftsmanship**: the final graphic must look meticulously crafted, labored over with care, the product of someone at the absolute top of their field. Not decorated — designed.

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
- **Text as visual architecture**: the headline or hero stat is not placed *on* the design — it *is* the design. Scale it fearlessly. Let context set the register: a bold fintech stat can be monumental and aggressive; a luxury brand line can be whisper-thin and surrounded by silence.
- **Secondary copy (metrics, subtext, CTA) recedes**: small, precise, positioned like clinical annotations or quiet labels — present and legible, never competing with the gesture.
- **Atmosphere over flatness**: build depth with layered gradients, geometric structure, pattern, translucency, and grain — always derived from the brand palette. A flat solid background is a failure of imagination.
- **Repetition and system**: repeating marks, ruled lines, systematic patterns reward sustained viewing and signal painstaking craft. Borrow the visual language of systematic observation — as if this graphic were a diagram from an imaginary discipline studying the brand's promise.

### Craftsmanship standard

To achieve human-crafted quality: make it appear as though someone at the top of their field labored over every detail. Composition, spacing, optical alignment, color calibration, typographic rhythm — everything at expert level. The result should be undeniably impressive at full size and still striking at thumbnail scale.

---

## FINAL STEP — THE REFINEMENT PASS

The user ALREADY said: "It isn't perfect enough. It must be pristine — a masterpiece of craftsmanship."

Take a second pass over the completed HTML. Do NOT add more graphics or new elements. Instead refine what exists: tighten optical spacing, calibrate color relationships, perfect the typographic scale, verify nothing overlaps and every margin breathes. If the instinct is to draw a new shape, STOP and ask instead: "How can I make what's already here more of a piece of art?"

Verify against the constraints one final time: exact canvas size, exact hex values, all copy verbatim, logo placed correctly, fully self-contained. Then output the single HTML file.
