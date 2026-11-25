# FitShot progress

Last updated: 2026-11-24

## Working now

- [x] Backend: QA gate, retries, review queue, bulk CSV, export, cost tracking
- [x] App UI: every screen, light and dark themes, phone layout, independent design review fixes
- [x] Gemini key in `.env`: the free vision check for hands and garment structure works
- [x] ComfyUI on the local GPU, with all 17 GB of models
- [x] Synthetic test images in `samples/` (see `samples/README.md` for where images come from)
- [x] Garment detection works on white, striped and dark garments
- [x] **Face-refine pass**: face match went from 0.22–0.33 to **0.72** on the first try
- [x] **Free try-on (CatVTON)** installed, running as a local service and connected as a generator
- [x] **Real end-to-end photoshoots**, all free, about 6 minutes for 3 garments
- [x] **New look, "Lookbook":** cobalt rail, magazine-cover headlines (Anybody), image-first photo grid, and an Inspection card with a cobalt header and a cover-burst status sticker. Light and dark themes, phone layout with a bottom bar. Documented in `DESIGN.md`.
- [x] **Fitting room (new home page):** pick a garment, see your model wearing it, Try it on with a chosen scene and pose, then approve, retry or reject on the Inspection card. A real try-on came back Verified in 63 seconds.
- [x] **Try it on yourself:** upload one photo of yourself in the fitting room (consent and 18+ confirmed), then try any garment on it. Phone-shaped photos are padded, not stretched. **Remove my photo** deletes the photo and every look made from it. Tested end to end: a 9:16 photo came back Verified in about 3 minutes.
- [x] **Add garment from the fitting room:** the Add garment tile opens the garment form and returns you to the fitting room.
- [x] **Ready for Vercel:** the app can talk to a FitShot on another address, with an access key and CORS. Rehearsed locally: the private screen appears, a wrong key is refused, the right key loads everything. Steps in `DEPLOY.md`.
- [x] `run.cmd` tested: it serves the app on port 8000 and shows the first-run screen
- [x] Design cleanups: stray colors tokenized, 44px icon buttons, 3:1 field borders, one panel-head style
- [x] 51 backend tests pass
- [x] **Live camera:** Take a photo in the fitting room, with a body outline and a 5-second timer. With a garment picked, your photo is tried on straight away. Tested end to end with a fake camera fed a synthetic stand-in: photo taken, accepted, try-on finished in about 3 minutes.
- [x] `start-all.cmd` opens ComfyUI, CatVTON and FitShot in one go; `run.cmd` now rebuilds the screens on every start
- [x] **Side by side:** pick several generators and each makes a look, shown next to each other. The worker has two lanes: the local GPU lane (ComfyUI, CatVTON take turns) and a cloud lane that runs at the same time
- [x] **Only the clothes change on your own photo:** the face guard stops at the chin, so hoods and collars are replaced; the edit area follows your real outline, so your build stays the same

## Latest results

Before and after: `D:\Devdaa\fitshot-e2e-out4\first_vs_now.png` (flat garment, first run, latest run)

| Garment | First run | Latest run |
|---|---|---|
| Navy tee | Too light, white hem showing (review) | **Verified**, every check passed, color ΔE 4.4 |
| Stripe tee | Stripes washed out (Gemini failed it) | **Verified**, stripes intact, color ΔE 3.4 |
| Olive jacket | Too khaki, white hem (review) | **Held for review**: Gemini correctly saw the lower pockets are missing |

What changed between runs:

- The garment goes to CatVTON at full size (768×1024) instead of a 512 thumbnail
- A wider edit area (torso to hips) leaves no white base tee behind
- The garment is blended in at full resolution, so the face, hands and background stay sharp and exactly as approved
- A new "pattern faded" rule fails a striped garment that loses its contrast (the local check had missed this)
- Skin is compared with the approved shot instead of the headshot
- Hands that the dressing never touched inherit your approval of the shot. Gemini had given the same hands different verdicts on different photos.
- Gemini judge calls retry when the free tier answers "busy"

## Still to do

- [ ] Olive jacket: lower pockets are lost, and the edit area below the hem can leave marks on the trousers
- [ ] Run a check on hands when a model shot is created (today you are the hand check when you approve a shot)
- [ ] Tune pass and fail limits on more real outputs (the navy tee passes at ΔE 4.4 but still looks slightly lighter than the flat photo)
- [ ] Deploy: you run the Vercel and tunnel steps in `DEPLOY.md` (needs your Vercel login)
- [ ] Try it on yourself again with the fixes (your first try showed the hood problem, now fixed on a synthetic hoodie test)
- [x] **Sleeves and hands:** Gemini reads each garment's sleeve length once; for shorter sleeves ComfyUI first turns the covered arms into bare skin, then the garment goes on. Hands, bare forearms and trousers are guarded from the edit. Tested on a synthetic hoodie: CatVTON gives short sleeves, bare arms, hands and trousers intact
- [x] **Parallel where the hardware allows:** two looks in flight (one on the GPU while the other is checked on the CPU), a GPU lock so ComfyUI and CatVTON never overlap, a cloud lane, bare arms reused per photo, one lock per QA model. Three shirts on one photo: 9 CatVTON images (3 attempts each) in 500 s, bare arms made twice instead of 9 times (now once)
- [x] **View large:** full-screen viewer with actual size, open on its own, download and arrow-key browsing
- [x] **Teach FitShot:** write what's wrong; Gemini turns it into a sleeve correction, a prompt fix and an inspector check for that garment, applied to every later photo. Lessons can be forgotten
- [x] **Nano Banana failure explained:** the free Gemini key has 0 image quota (`limit: 0`). FitShot now says so plainly, does not retry, and marks the generator unavailable
- [x] **FASHN VTON 1.5 is the default try-on**, on Hugging Face Spaces with your HF token (no local download). Benchmark in `benchmark/`: of the 5 scenarios it ran, FASHN was clearly better in 4 (striped tee, navy tee, model-worn tee full and half body) and tied on trousers. CatVTON stays as the offline fallback
- [x] **ComfyUI dressing retired** (it drifted in colour); ComfyUI now only makes brand model photos. Its IP-Adapter model, CLIP vision model and custom node were removed (3.2 GB)
- [x] **Face and body photos, in either order:** face close-up (identity) and half- or full-body photo (try-on); checked to be the same person. Tested with a synthetic face close-up and a headless body photo
- [x] **Delete any look**, and rejected looks hidden from the strip unless shown
- [x] **FASHN VTON 1.5 runs on this PC** (run-fashn.cmd): no daily limit, photos stay here. RTX 5060 8 GB: model ~3 GB GPU, whole card 4.1-5.6 GB peak, ~60 s per image. All 7 benchmark scenarios pass the colour check; FASHN clearly beat CatVTON on 5 of 7 (striped tee, navy tee, both model-worn tees, and the dress CatVTON broke), tied on trousers, and was mixed on the jacket (right colour, but drawn open over bare skin). CatVTON kept as a fallback. GPU hand-off verified both ways (one model on the GPU at a time)
- [x] **Restructured around Fitting room, Models and Results.** Central AI model registry (add, download, validate, default, remove with safety checks), a four-step Fitting room (Live full/half body or Built-in person, garment with photo type and category, AI model, review with model settings, result), Results history with model and settings, People for built-in people. All four user journeys tested in the browser
- [x] Every page lists only the models in use (from the registry), with one name per model; three synthetic built-in people added (two men, one woman, different ethnicities), generated locally
- [ ] Jackets over a top: FASHN can draw the jacket open with nothing underneath (benchmark scenario 7); the inspector does not catch it yet
- [x] **Free quota used up = wait, not fail:** FASHN looks wait and retry hourly until the quota resets
- [x] **Either photo is enough:** face only (FitShot makes a full-body photo from it, standard build) or body only
- [ ] Remaining small drift in `DESIGN.md`: small buttons at 36px, the select arrow's fixed color
- [ ] Use approve and reject decisions to tune the QA limits (the notes teach per garment; limits are still global)
- [ ] Before and after gallery for the portfolio
- [ ] Loom demo (you record this)

## Known limits

- Image generation is not free on the Gemini API, so FitShot generates locally on your GPU at no cost.
- A model shot takes about 2 minutes and a try-on about 1 to 2.5 minutes on this laptop.
- The free Gemini tier is sometimes busy. A judge call that still fails after retries sends the photo to review, never to Verified.
- CatVTON, InsightFace and InstantID allow non-commercial use only, which is fine for a portfolio.
