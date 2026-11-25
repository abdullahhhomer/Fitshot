# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated within the project brief's options: React + Vite frontend, FastAPI backend, SQLite, served locally.

## Users

The primary user is a small clothing brand owner. They are not technical, often run the label themselves, and need catalog photos they can publish to Shopify or Instagram without paying for a photoshoot for every collection.

## Product Purpose

FitShot turns a flat garment photo into catalog photos of the brand's consistent virtual model. Success means the owner can trust what they publish: every accepted image has been checked, and anything uncertain is shown to them before it can be exported.

## Positioning

Generating try-on images is a commodity. FitShot's mechanism is verification: each photo carries a report on the garment, face, body, hands and skin tone, failures are retried with specific fixes, and uncertain images go to a person instead of being silently published.

## Operating Context

The workflow is: create a brand model, approve its shots per scene, add garments, run a single or CSV bulk photoshoot, inspect results, resolve the review queue, export accepted images, and read the cost per accepted image.

## Capabilities and Constraints

- Scenes: studio, street, beach. Garment categories: top, outerwear, bottom, dress.
- Generators: Nano Banana through the Gemini API, and a ComfyUI workflow.
- QA thresholds are provisional and have not been calibrated on labeled outputs. The interface must not imply otherwise.
- Without a vision review, an image can never pass automatically.
- Try it on yourself: a visitor can upload one photo of themselves (head to at least hips, consent and 18+ confirmed) and try garments on it in the fitting room. The photo stays on the machine running FitShot and can be removed, with every look made from it, at any time.
- The app does not predict real size or fit.
- Exported images are recorded as AI-generated.

## Brand Commitments

The product name is FitShot. No logo, palette or typeface has been established.

## Evidence on Hand

No real customer data, testimonials, benchmark results or generated catalog exist yet. The $500 to $3,000 photoshoot figure is an unsourced estimate from the project brief and must be labeled as an estimate wherever it appears.

## Product Principles

1. Never let an unverified image look verified.
2. Explain QA in plain language first, with the measured score one step away.
3. A person makes the final call on anything uncertain.
4. Show the true cost, including retries.

## Accessibility & Inclusion

Status must never rely on color alone. The product shows people of all skin tones, so its interface must not distort how photos and skin colors are perceived.
