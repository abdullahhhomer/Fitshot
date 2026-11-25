# FitShot: Verified AI Product Photoshoots

> Status: draft for discussion, 2026-11-23. Improves on [Instructions.md](Instructions.md), which is unchanged.
> Prices and model dates come mostly from third-party pages. Confirm them on the provider pages before relying on them.

## 1. The idea

**Generating a try-on image is now a commodity. Knowing that the image is safe to publish is not.**

Hosted try-on APIs already cost roughly $0.04 to $0.075 per image, so "we put clothes on an AI model" is not a differentiator. FitShot's position is:

> Upload a garment and get catalog photos of your brand's model, each with a **QA report** proving the product, face, body and skin tone stayed correct. Anything that fails is repaired or sent to a person. It is never silently published.

For a portfolio, this shows the skill hiring managers look for: measuring and controlling generative output, not only calling an API.

## 2. What changes from the original brief

| Area | Original | Improved | Why |
|---|---|---|---|
| Garment accuracy | A stated feature with no check | **A dedicated garment check** | The garment is what the customer buys. A wrong color or logo is the costliest failure. |
| Pipeline | Generate the whole image, retry on failure | **Approved shot library + garment-only edit** | Face, pose and scene are approved once and reused. |
| Hand check | MediaPipe flags extra fingers | **MediaPipe for pose, hand crops + vision-model judge for fingers** | MediaPipe always fits 21 landmarks per hand, so it cannot count a sixth finger. |
| Skin tone | Compare face color to reference | **Compare after white balance, with per-scene tolerance** | Sunset and studio light legitimately change raw pixel color. |
| Thresholds | One fixed similarity cutoff | **Calibrated on a labeled set** | Scores shift with pose, lighting and generator. |
| Retry | Regenerate | **Failure-specific repair, max 3 attempts, then human review** | Prevents runaway cost and endless loops. |
| Cost | Cost per image | **Cost per *accepted* image** | Retries are part of the true cost. |
| Input | One flat photo | **Front required, back optional** | Without a back photo, the back of the garment is invented. |
| Licensing | Not addressed | **Portfolio-safe now, swappable later** | Several suggested models are non-commercial (section 7). |
| Selfie mode | Any shopper selfie | **Consent, no retention, catalog items only** | Face data is sensitive and the feature can be abused (section 7). |

## 3. Core workflow

```text
SETUP (once per brand)
  Create synthetic model -> generate shot library (poses x scenes)
  -> QA + human approval -> store approved shots, masks, face embedding centroid

PRODUCTION (per garment)
  Garment photo(s)
     |
  Preprocess: cut out, detect category, extract colors, mark logo
     |
  Pick approved shots for the chosen scene
     |
  Garment-only edit (Nano Banana or try-on model)
     |
  Paste original face and uncovered hands back through a mask
     |
  QA gate: garment | identity | anatomy | skin tone
     |
     +-- pass ------> catalog export + QA report
     +-- fail ------> targeted repair (max 3 attempts total)
     +-- still fails -> human review queue
```

**Why the shot library is the key decision**

- Identity is largely preserved by construction, because the approved face is restored after the edit.
- Anatomy problems are caught once at approval instead of on every product.
- Every product in a store shares the same poses and framing, which is what a consistent catalog looks like.
- The known risk is garments that change what is visible, such as a short sleeve revealing an arm the base shot had covered. The benchmark must measure this.

## 4. QA gates

Each gate returns `pass`, `review` or `fail`, a score, and a reason shown in the UI.

| Gate | Method | Repair on failure |
|---|---|---|
| **Garment color** | Segment garment, compare dominant colors in CIELAB using Delta E 2000 | Re-edit with extracted color values |
| **Pattern and fabric** | Compare DINOv2 features between garment crops | Re-edit with a closer garment crop |
| **Logo and text** | OCR plus local feature matching on the marked logo region | Restore or re-edit the logo region |
| **Garment structure** | Vision-model checklist: neckline, sleeve length, hem, buttons, pockets | Re-edit with the failed items in the prompt |
| **Identity** | Face embedding cosine similarity against the model's centroid | Restore the face from the base shot |
| **Body and pose** | MediaPipe Pose: limb ratios, joint plausibility, drift from base shot | Choose another approved shot |
| **Hands** | Hand crops judged by a vision model with structured output | Inpaint the hand or restore from base shot |
| **Skin tone** | White-balanced CIELAB comparison of face and visible skin, with scene tolerance | Color-correct, then re-check |

**Calibration:** hand-label about 200 outputs as good or bad, then choose thresholds from the score distributions. Report each gate's precision and recall. That table is one of the strongest items in the portfolio.

## 5. Features and scope

**MVP**

- Brand model creation and approved shot library
- Garment upload with 3 scenes: studio white, street, beach
- 4 to 6 outputs per garment, each with a QA report
- Auto-repair and a human review queue
- Bulk mode: CSV of 50 products in, ZIP plus results CSV out
- Cost tracker per image, product and batch

**Second phase**

- Selfie try-on, with the safeguards in section 7
- Benchmark across Nano Banana, a dedicated try-on API, and ComfyUI (SDXL + InstantID + ControlNet)
- Shopify-ready export: file naming, sizes and alt text

**Out of scope for now**

- Predicting real size or fit. Outputs show how an item looks, not how it will fit a given body.
- Video, payments, multi-tenant accounts and a live Shopify app

## 6. Technical plan

| Layer | Choice | Note |
|---|---|---|
| Generation | Nano Banana 2.1 through the Gemini API | Keep the model ID in config, because these models retire quickly |
| Comparison | One hosted try-on API + one ComfyUI workflow | Run behind the same `Generator` interface |
| QA | Python: InsightFace, MediaPipe, a garment segmenter, DINOv2, OpenCV | Each gate is an independent module |
| Vision judge | A low-cost vision model with JSON output | Used only for hands and garment structure |
| Backend | FastAPI + SQLite + a background worker | A job table is enough; no Redis needed yet |
| Frontend | React + Vite | Stronger portfolio piece than Streamlit |
| Storage | Local files behind a storage interface | Can move to S3 or R2 later |
| Compute | QA on the local RTX 5060 (8 GB), ComfyUI on rented GPU | SDXL + InstantID + ControlNet will be tight on 8 GB |

**Proposed structure**

```text
fitshot/
  backend/
    api/          # FastAPI routes
    generators/   # nano_banana, tryon_api, comfyui
    qa/           # garment, identity, anatomy, skin, gate
    pipeline/     # preprocess, compose, repair, jobs
    cost/         # per-call ledger
  frontend/       # React app
  workflows/      # ComfyUI JSON
  eval/           # golden set, labels, calibration, benchmark
  gallery/        # before/after portfolio output
```

## 7. Licensing, privacy and disclosure

**Licensing.** These are fine for a portfolio but block a commercial launch unless replaced or licensed:

- **InsightFace pretrained models** (including `buffalo_l` and `antelopev2`) are for non-commercial research unless a commercial license is purchased.
- **InstantID** code is Apache-licensed, but it depends on those face models.
- **IDM-VTON** is CC BY-NC-SA 4.0, and CatVTON is reported to use the same license.

Keeping these behind interfaces means a commercial version can swap them without a rewrite.

**Selfie mode safeguards**

- Require explicit consent, and process the selfie without storing it or its embedding after the session.
- **Only allow items from a brand's catalog**, so it cannot be used to dress a stranger's photo in arbitrary clothing.
- Exclude swimwear and lingerie, and block images of minors or more than one person.
- Face embeddings can count as biometric data under laws such as GDPR and Illinois BIPA. Get legal advice before any public launch.

**Disclosure.** EU AI Act Article 50 transparency duties began applying on 2 August 2026. How they apply to non-deceptive synthetic model photos is not settled in the sources reviewed, so FitShot should embed provenance metadata and offer an "AI-generated" label by default.

## 8. Cost model

Example using an assumed **60% first-pass rate** and about **$0.0504 per 2K image**, with up to 3 attempts:

| Metric, 50 products x 4 images | Value |
|---|---|
| Image slots | 200 |
| Expected generations | about 312 |
| Generation cost | about **$15.72** |
| Pass automatically | about 187 |
| Sent to human review | about 13 |
| Cost per accepted image | about **$0.084** |

This excludes vision-judge calls, GPU time and review labor. The real pass rate will come from the benchmark. The brief's $500 to $3,000 photoshoot figure needs a citable source before it appears in the demo.

## 9. Build milestones

| # | Milestone | Done when |
|---|---|---|
| 0 | **Golden set + eval harness** | 10 garments (solid, stripe, print, logo, dress, jacket), 3 synthetic models, 3 scenes |
| 1 | **Baseline generation** | A script produces on-model images for the full set |
| 2 | **Shot library + garment edit** | Approved shots work, and the face is restored after editing |
| 3 | **QA gates** | All gates run and thresholds are calibrated on labeled data |
| 4 | **Repair + review loop** | Failures are repaired or queued, with a retry cap |
| 5 | **App UI** | The full single-product flow works in the browser |
| 6 | **Bulk + cost tracker** | A 50-product CSV completes and resumes after interruption |
| 7 | **Benchmark** | Nano Banana vs try-on API vs ComfyUI on the same golden set |
| 8 | **Selfie mode + gallery + Loom** | Safeguards are in, and the portfolio assets are published |

## 10. Success targets

Starting targets, to be revised after the first benchmark:

- At least 90% of published images pass human review on garment accuracy
- At least 80% of images accepted within 3 attempts
- QA catches at least 90% of hand-labeled bad images
- Under $0.15 per accepted image
- A 50-product batch finishes unattended

## 11. Loom demo (3 minutes)

1. **0:00** The problem: AI try-on looks good until the logo or color is wrong.
2. **0:20** Upload a plain shirt, pick the brand model and "street" scene.
3. **0:50** Four outputs appear with QA reports.
4. **1:20** **A real failure:** a changed logo or bad hand is caught, repaired, and passes.
5. **1:50** Benchmark table: which generator won on which garment type.
6. **2:15** Bulk run and cost per accepted image vs a photoshoot.
7. **2:40** Selfie mode on a second item, with the consent step visible.

## 12. Decisions (2026-11-23)

1. **Goal:** a working MVP.
2. **Deadline:** 2026-11-24, so the build follows the one-day scope below.
3. **ComfyUI:** required, as a real hands-on workflow.
4. **Selfie mode:** deferred until the core pipeline works.

### One-day MVP scope

**In:** brand model and approved shots, garment upload, Nano Banana generation, QA gates with auto-retry, review queue, CSV bulk mode, cost tracker, React UI, and one SDXL + InstantID + ControlNet ComfyUI workflow behind the same `Generator` interface.

**Deferred:** selfie mode, full three-way benchmark, 200-image threshold calibration, Shopify export, Loom recording.
