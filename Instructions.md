FitShot: AI Product Photoshoots for Small Clothing Brands
Category: AI image generation (identity-consistent people, virtual try-on)

Business value: A small clothing brand spends $500 to $3,000+ on one photoshoot (model, photographer, studio, editing), and has to repeat it for every new collection. FitShot lets the brand upload a flat photo of a garment and get catalog-ready photos of the same virtual model wearing it, in different poses and settings, for a few cents per image. The same model face across the whole store keeps the brand look consistent.

What it does: Upload a garment photo (shirt, dress, jacket), pick a saved brand model and a scene (studio white, street, beach), and get 4 to 6 realistic on-model photos ready for Shopify or Instagram.

Job types it matches: AI fashion / styling platforms, selfie styling, virtual try-on, identity-consistent image generation, e-commerce product imagery, Stable Diffusion / ComfyUI, Gemini / Nano Banana.

Features

Saved brand model: create one virtual model once and reuse the same face across every product
Selfie mode: a shopper uploads a selfie and sees themselves wearing the item
Garment accuracy: color, pattern, logo and fabric stay true to the real product
Identity check (the CV part): compare face embeddings between the reference and each output; regenerate if similarity drops below a threshold
Anatomy check: pose detection flags extra fingers, broken limbs or odd proportions, and regenerates
Skin tone check: compare skin color in the face region with the reference so it doesn't drift
Bulk mode: a CSV of 50 products in, a full catalog set out
Cost tracker: cost per image and per product, compared with a traditional photoshoot
Tech stack

Nano Banana (Gemini image API) for fast try-on with reference images
SDXL + IP-Adapter FaceID / InstantID for identity, ControlNet (OpenPose) for pose, in a ComfyUI workflow
Open-source virtual try-on model (e.g. IDM-VTON) to compare garment accuracy
InsightFace for face embeddings (identity score), MediaPipe for pose and hand checks
Python, FastAPI, React or Streamlit; fal.ai or Replicate for hosted GPU
Build steps

Collect 10 garment photos and 2 to 3 reference faces (generated or with consent)
Get Nano Banana try-on working: face + garment + scene prompt → on-model photo
Build the ComfyUI version with InstantID + ControlNet for comparison
Add the identity, anatomy and skin tone checks with auto-regenerate
Add bulk mode and the cost tracker
Save a before/after gallery (input garment + face → outputs) for the portfolio
Loom demo (3 min)
Upload a plain shirt photo → pick brand model + "street" scene → 4 on-model photos → show identity score and anatomy check passing (and one failed image being regenerated) → selfie mode on a second item → cost per image vs photoshoot cost.

Why it's worth building: Fashion and e-commerce image jobs (like the GIA styling platform role) always ask for a portfolio with real input/output examples and how you handled identity, anatomy and consistency. This project answers all three, and the CV-based checks are a strong differentiator.