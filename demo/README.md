# FitShot demo

A complete run through FitShot on this PC:
- a person tries a garment on with FASHN VTON 1.5;
- FitShot checks the photo;
- the rest of the studio: history, the AI model registry, people, the review queue, costs, the dark theme and the phone layout.

Every person in the demo is synthetic (AI-generated), and so is every garment. No real customer or staff photos were used.

## Videos

| File | Length | What it is |
|---|---|---|
| [fitshot-walkthrough.mp4](fitshot-walkthrough.mp4) | 1:19 | The real screen recording of the run, captioned step by step. The 3.7-minute generation wait plays at 10× speed. |
| [fitshot-slideshow.mp4](fitshot-slideshow.mp4) | 1:47 | The 23 screenshots below as captioned slides, 4 seconds each. |

Both videos are 1440×900 H.264 MP4, so they play in any browser, on a phone, in WhatsApp or in PowerPoint.

### Walkthrough
Click the preview for the full-quality MP4.

[![FitShot walkthrough](fitshot-walkthrough.gif)](fitshot-walkthrough.mp4)

### Slideshow
Click the preview for the full-quality MP4.

[![FitShot slideshow](fitshot-slideshow.gif)](fitshot-slideshow.mp4)

## How it was made

- **App:** a separate copy of FitShot with its own `DATA_DIR`, seeded by [scripts/seed_demo.py](scripts/seed_demo.py). Your studio data is untouched.
- **AI model:** FASHN VTON 1.5 running locally on the RTX 5060.
- **Recording:** Playwright drove Microsoft Edge through the flow ([scripts/demo.mjs](scripts/demo.mjs)), taking a screenshot at each step while recording the screen.
- **Videos:** [scripts/make_videos.py](scripts/make_videos.py) added the captions and title cards and encoded both videos.
- **Timings:** [steps.json](steps.json) holds each caption and the second it was taken.

---

## 1. Fitting room: try a garment on with your own photo

**1. Choose who wears it.** Live uses your own photo, either full body (head to feet) or half body (head to waist).
![Fitting room, Live tab](screenshots/01-fitting-room-live.png)

**2. Add the photo.** Drag it in, choose a file or take one with the camera. FitShot checks that a full-body photo really shows the whole body before accepting it. The "this is me, and I'm 18 or older" box is required.
![Photo added](screenshots/02-live-photo-added.png)

**3. Step 2: the garment.** Upload a garment photo, or pick one from the catalog.
![Garment step](screenshots/03-garment-step.png)

**4. Choose the category:** upper body, jacket, lower body or dress.
![Garment upload with category](screenshots/04-garment-upload.png)

**5. The photo type is detected.** FitShot tells a flat-lay apart from a photo of the garment worn by a model, and you can correct it. A flat-lay sent as "worn by a model" is what pasted whole shirts over people, so FitShot now overrides that.
![Garment photo type](screenshots/05-garment-photo-type.png)

**6. Step 3: the AI model.** Only models that are installed and checked appear, each with what it can dress. A model that can't dress this garment or person is greyed out and says why.
![AI model choice](screenshots/06-ai-model.png)

**7. Step 4: review.** Check the person, garment, photo type, category and model before anything runs.
![Review](screenshots/07-review.png)

**8. Model settings.** Each model brings its own settings. For FASHN these are quality steps and garment guidance.
![Review settings](screenshots/08-review-settings.png)

**9. Generating.** The progress names the model and the elapsed time. While the GPU is busy, the try-on waits its turn instead of failing.
![Generating](screenshots/09-generating.png)

**10. The result.** Before and after side by side. The Inspection card checks the garment color and pattern, the face, skin tone, body and hands; this one passed and is marked Verified.
![Result](screenshots/10-result.png)

**11. View large.** Full screen at actual size, or open the photo on its own or download it.
![View large](screenshots/11-view-large.png)

**12. Teach FitShot.** Say what's wrong in your own words. FitShot turns it into a check for this garment's future photos.
![Teach](screenshots/12-teach.png)

## 2. Fitting room: built-in people

**13. Built-in models.** Your brand's people, each marked full or half body.
![Built-in people](screenshots/13-built-in-people.png)

**14. Pick from the catalog.** Here, the red polka dress for Aiko. Half-body people can only wear tops and jackets, and the flow says so.
![Built-in garment](screenshots/14-built-in-garment.png)

## 3. Results

**15. Every try-on is kept,** with the person, garment, model and settings it was made with. From here, a photo can be downloaded, compared or re-run with different settings.
![Results](screenshots/15-results.png)

## 4. Models: the AI model registry

**16. The AI models in use,** with their status, hardware needs, licence and limits. One model is the default.
![Models](screenshots/16-models.png)

**17. Add a model.** Pick from the supported models, then point at its files or download them. It is checked before it can be used.
![Add model](screenshots/17-add-model.png)

**18. Remove a model.** FitShot asks first and warns if the model is the default. Deleting files is optional and never touches files shared with other parts of the app.
![Remove model](screenshots/18-remove-model.png)

## 5. Studio tools

**19. People:** the brand's built-in people and their approved photos.
![People](screenshots/19-people.png)

**20. Review:** photos FitShot could not verify on its own wait here for a person to approve, retry or reject.
![Review queue](screenshots/20-review-queue.png)

**21. Costs:** what each accepted photo really cost, retries included.
![Costs](screenshots/21-costs.png)

## 6. Dark theme and phone

**22. Dark theme:** the same app, with photos still shown on a neutral background so their colors read true.
![Dark theme](screenshots/22-dark-results.png)

**23. On a phone:** the same steps, with Try on, Models, Results, Review and More in the bottom bar.
![Phone](screenshots/23-phone.png)

---

## Re-making the demo

1. **Start the services:**
   - FASHN (this PC) with `run-fashn.cmd`;
   - a separate copy of the app, for example `DATA_DIR=D:\fitshot-demo-data` on port 8015.
2. **Seed the app:** `python demo/scripts/seed_demo.py`. This adds the synthetic people from [inputs/people](inputs/people) and five garments, then makes two earlier try-ons so Results has a history.
3. **Record:** from `demo/scripts`, run `npm i playwright-core`, then `node demo.mjs http://127.0.0.1:8015 ../ ../../benchmark/inputs`. Microsoft Edge must be installed.
4. **Make the videos:** `python demo/scripts/make_videos.py demo`. This needs opencv-python, numpy, Pillow and an ffmpeg with libx264; `pip install imageio-ffmpeg` provides one.
