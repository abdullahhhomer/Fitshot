# FitShot images: what you need and where to get them

FitShot does not need a training dataset. It uses pretrained models. You only supply two kinds of input image.

## 1. One brand model face

A clear, front-facing photo with exactly one face. FitShot creates the full-body shots from it.

| Source | Use it? | Notes |
|---|---|---|
| AI-generated face | **Yes, best for a portfolio** | `model_a.png` here was generated locally. It is not a real person. |
| A real adult who agreed in writing | Yes | Keep their consent. |
| Photos of celebrities, influencers or strangers | **No** | No consent, and it creates legal risk. |

## 2. Garment photos

One front photo per product, laid flat or on a hanger, on a plain light background. A back photo is optional.

| Source | Use it? | Notes |
|---|---|---|
| Your own clothes, photographed with a phone | **Yes, best for a real demo** | Lay the item flat on a bedsheet or wall in daylight, shoot straight down, and fill most of the frame. |
| A brand's own product photos | Yes, with their permission | This matches the real customer workflow. |
| AI-generated garments | Yes, for testing | `garment_*.png` here were generated locally. Small labels inside the collar contain invented text. |
| Free stock sites such as Unsplash or Pexels | Check each license | Avoid photos showing other brands' logos. |
| Photos taken from online shops | **No** | Those photos are copyrighted. |

## Files in this folder

All of these were generated locally with RealVisXL on 2026-11-23 and show no real person.

| File | What it is |
|---|---|
| `model_a.png` | Synthetic brand model reference face |
| `garment_navy_tee.png` | Plain navy t-shirt, solid color test |
| `garment_stripe_tee.png` | White and navy striped t-shirt, pattern test |
| `garment_olive_jacket.png` | Olive work jacket with buttons and pockets, outerwear test |

## Optional later: a labeled evaluation set

To tune the pass and fail limits properly, FitShot needs about 200 of its own outputs, each marked good or bad by a person. That set comes from running FitShot, not from downloading anything. Public try-on research datasets exist, but they usually require a request form and allow research use only.
