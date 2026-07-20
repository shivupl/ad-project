---
name: marketing-graphic-design
description: Generate distinctive, production-grade marketing graphics as self-contained HTML/CSS files. Use this skill when generating social media posts, ads, banners, or any fixed-canvas marketing asset. Produces on-brand, visually striking graphics that avoid generic AI aesthetics.
---

This skill guides generation of distinctive, production-grade marketing graphics as self-contained HTML/CSS files. Every graphic must feel intentionally designed — not templated, not generic, not interchangeable.

## Design Thinking

Before writing a single line of HTML, commit to a clear visual strategy:

- **Hierarchy**: What is the ONE thing the viewer must read first? Everything else is secondary. Never let two elements compete equally for attention.
- **Tone**: Match the brand's personality precisely. A fintech brand is not a lifestyle brand. A developer tool is not a consumer app. Read the brand brief carefully and commit to a direction that fits.
- **Composition**: Where does the eye enter? Where does it travel? Where does it rest? Every element placement must be intentional.
- **Differentiation**: What makes this graphic impossible to mistake for something else? The answer must exist before you start coding.

**CRITICAL**: Bold minimalism and rich maximalism both work. Generic middle-ground does not. Commit fully to one direction and execute it with precision.

## Canvas Rules

These are non-negotiable for every generation:

- **LinkedIn post**: 1200x627px
- **Instagram / square**: 1080x1080px
- **Instagram story / vertical**: 1080x1920px
- **Twitter/X**: 1200x675px
- Default to LinkedIn format unless specified otherwise
- Set explicit width and height on the root container — never rely on viewport
- All content must be fully visible within the canvas — nothing cut off, nothing overflowing
- Body background should be neutral (`#111` or similar) to frame the canvas in browser preview

## Typography Rules

Typography is the most important design element in marketing graphics. Treat it with precision:

- **Never use**: Arial, Inter, Roboto, Helvetica, system-ui, sans-serif as a primary font
- **Always import** from Google Fonts via `@import` at the top of the `<style>` block
- **Pair two fonts maximum**: one display/headline font, one body/detail font
- **Hierarchy through size**: headline should be 2.5–4x the size of body text
- **Hierarchy through weight**: use the full weight range available (400 for body, 700–900 for headlines)
- **Never use more than 3 font sizes** in a single graphic
- **Line height**: 1.0–1.15 for large headlines, 1.4–1.6 for body text
- **Letter spacing**: tight on large headlines (–0.02em to –0.04em), loose on small caps/labels (0.08em to 0.2em)

Strong font pairings to consider (vary these, never repeat the same pair):
- Syne (display) + JetBrains Mono (detail) — technical, premium
- Playfair Display (display) + DM Sans (body) — editorial, refined
- Space Grotesk (display) + IBM Plex Mono (detail) — startup, modern
- Fraunces (display) + Outfit (body) — warm, distinctive
- Bebas Neue (display) + Mulish (body) — bold, impactful
- Cormorant Garamond (display) + Jost (body) — luxury, elegant

## Color Rules

- **Always use** the exact brand colors provided — hex values must match precisely
- **Build a full palette** from the brand colors: base, surface, border, text-primary, text-secondary, text-muted, accent
- **Use CSS variables** for every color — never hardcode hex values more than once
- **One dominant color**, one accent, dark/light neutrals — never distribute colors evenly
- **Contrast**: all text must have sufficient contrast against its background
- **Atmosphere over flatness**: use radial gradients, subtle noise, layered transparencies to create depth — never plain flat fills as the primary background

## Layout & Composition Rules

- **Fixed positioning**: use `position: absolute` with explicit coordinates for all elements — never rely on flow layout for a fixed-canvas graphic
- **Safe zones**: keep all content at least 48px from canvas edges (minimum 64px for premium feel)
- **Visual weight**: the primary element (headline or stat) should occupy 30–50% of the canvas
- **Asymmetry over symmetry**: slight asymmetry feels designed, perfect centering feels default
- **Breathing room**: generous negative space elevates perceived quality — never fill every inch
- **Rule of thirds**: place the primary element at a third intersection, not dead center
- **One visual anchor**: every graphic needs one element that grounds the composition — a large stat, a bold headline, a strong geometric shape

## Post Type Patterns

Different post types have different visual logic. Match the layout to the intent:

**Thought leadership / insight**
- Text-dominant, typography is the visual
- Large provocative headline as hero
- Minimal supporting elements
- Author or brand attribution subtle at bottom

**Stat / data callout**
- The number IS the graphic — make it enormous
- Supporting context in small text around it
- Simple background, let the number breathe
- Source or context line at bottom

**Product / feature announcement**
- Product name or feature as headline
- One key benefit as subtext
- Supporting proof points (3 max) as small chips or list
- Strong CTA

**Brand awareness**
- More atmospheric, visual-forward
- Headline can be shorter and more conceptual
- More background treatment / visual interest
- Tagline or URL as the only CTA

## Background & Atmosphere Rules

Never use a plain flat color as the only background treatment. Always add depth:

- **Dark themes**: radial gradient from a slightly lighter center, subtle grid or dot pattern at low opacity, color glow from brand accent
- **Light themes**: subtle grain texture via SVG filter, soft shadow vignette, light geometric pattern
- **Geometric elements**: use CSS borders, box-shadows, and pseudo-elements to create architectural detail
- **Layering**: stack 2–3 background layers — base color, gradient overlay, pattern — each at different opacities

## Brand Asset Rules

When a logo is provided:
- Place at top-left by default (top-right acceptable for right-weighted compositions)
- Maximum height: 36px for LinkedIn, 44px for square formats
- Embed as base64 data URI — never as an external URL
- Maintain aspect ratio — never stretch or distort
- Ensure sufficient clear space around the logo (minimum 16px)

When brand fonts are provided:
- Import them via Google Fonts `@import` — match the exact family name
- If a font is not on Google Fonts, fall back to the closest available alternative and note it

## What Never to Do

- **No animations or transitions** — graphics are static assets
- **No hover states or interactive elements** — will not survive screenshot
- **No external image URLs** — will break in offline/screenshot contexts
- **No `min-height: 100vh`** — canvas must be exactly the specified dimensions
- **No overflow** — if content doesn't fit, reduce font sizes, not canvas size
- **No generic layouts** — centered logo, centered headline, centered subtext stacked vertically is the most overused pattern — avoid it unless the brand specifically calls for it
- **No Lorem Ipsum** — use only the exact copy provided
- **No placeholder colors** — use only the exact brand colors provided
- **No truncation** — output the complete HTML file including all closing tags

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Craft Floors (added — non-negotiable, apply on top of everything above)

- **Scene first**: before choosing the look, write ONE sentence (as an HTML comment after `<!DOCTYPE html>`) naming who sees this, where, and under what light. Commit to a direction from it.
- **Contrast floor**: body text ≥ 4.5:1 against its background; large/display text ≥ 3:1. Never washed-out muted gray on a colored ground — use a darker shade of the ground's own hue (or the text color at reduced opacity), never a flat light gray that disappears.
- **Overflow guard**: reason about the rendered width of the actual headline words at the chosen size. If they can't fit one line with margin to spare, choose the line break deliberately. A display word that clips the canvas edge or collides with the copy below is an automatic fail.
- **Even line breaks**: apply the equivalent of `text-wrap: balance` — hand-break multi-line headlines so the lines are even and no single orphan word dangles on its own line.
