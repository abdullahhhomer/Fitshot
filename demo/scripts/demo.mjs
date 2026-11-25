// FitShot demo walkthrough: screenshots of every step, a screen recording, and step timings.
// Usage (from demo/scripts, after npm i playwright-core):
//   node demo.mjs http://127.0.0.1:8015 ../ ../../benchmark/inputs
// Needs Microsoft Edge, the app seeded by seed_demo.py, and FASHN (this PC) running.
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync, readdirSync, renameSync } from "node:fs";

const [base, demoDir, inputs] = process.argv.slice(2);
const shotsDir = `${demoDir}/screenshots`;
const rawVideo = `${demoDir}/raw-video`;
mkdirSync(shotsDir, { recursive: true });
mkdirSync(rawVideo, { recursive: true });

const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: rawVideo, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
await page.addInitScript(() => localStorage.setItem("fitshot-theme", "light"));

const t0 = Date.now();
const steps = [];
let n = 0;
const pause = (ms = 1400) => page.waitForTimeout(ms);
async function step(name, caption, { full = false } = {}) {
  n += 1;
  const file = `${String(n).padStart(2, "0")}-${name}.png`;
  await pause(600);
  await page.screenshot({ path: `${shotsDir}/${file}`, fullPage: full });
  steps.push({ n, file, caption, at: (Date.now() - t0) / 1000 });
  console.log(`${file}: ${caption}`);
  await pause(900);
}
const mark = (label) => steps.push({ n: null, file: null, caption: label, at: (Date.now() - t0) / 1000 });

// ---------- Fitting room: Live ----------
await page.goto(`${base}/#/studio`);
await page.evaluate(() => sessionStorage.removeItem("fitshot-flow"));
await page.reload();
await page.waitForSelector(".flow-steps");
await page.getByRole("tab", { name: /^Live/ }).click();
await step("fitting-room-live", "Fitting room, step 1: choose who wears it. Live uses your own photo, Full body or Half body.");
await page.getByRole("radio", { name: /Full body/ }).click();
await page.getByLabel("Your full body photo").setInputFiles(`${inputs}/person_full_hoodie.png`);
await page.getByLabel("This is a photo of me, and I'm 18 or older.").check();
await page.locator(".dropzone").scrollIntoViewIfNeeded();
await step("live-photo-added", "Drag in, choose or take a photo. FitShot checks it shows the whole body before accepting it.");
await page.getByRole("button", { name: "Use this photo" }).click();
await page.waitForSelector("#step-garment", { timeout: 90000 });
await page.evaluate(() => window.scrollTo(0, 0));
await step("garment-step", "Step 2: the garment. Upload one or pick from your catalog.");

// ---------- Garment ----------
await page.getByLabel("Garment photo").setInputFiles(`${inputs}/garment_stripe_tee_flatlay.png`);
await page.locator("input[placeholder]").first().fill("Breton stripe tee");
await page.getByRole("radio", { name: /^Upper body Shirts/ }).click();
await page.locator(".garment-upload").scrollIntoViewIfNeeded();
await step("garment-upload", "Choose the category: upper body, jacket, lower body or dress.");
await page.getByRole("button", { name: "Use this garment" }).click();
await page.waitForSelector(".photo-type", { timeout: 90000 });
await page.locator(".photo-type").scrollIntoViewIfNeeded();
await step("garment-photo-type", "FitShot detects whether the photo is a flat-lay or worn by a model. You can correct it.");

// ---------- AI model ----------
await page.getByRole("button", { name: /Continue/ }).click();
await page.waitForSelector("#step-model");
await page.locator(".model-choice", { has: page.locator(".model-name", { hasText: "FASHN VTON 1.5 (this PC)" }) }).click();
await page.evaluate(() => window.scrollTo(0, 0));
await step("ai-model", "Step 3: the AI model. Only models that are installed and checked appear, with what they can dress.");

// ---------- Review and generate ----------
await page.getByRole("button", { name: /Continue/ }).click();
await page.waitForSelector("#step-review");
await page.evaluate(() => window.scrollTo(0, 0));
await step("review", "Step 4: review the person, garment, photo type, category, model and its settings.");
await page.locator(".settings").scrollIntoViewIfNeeded();
await step("review-settings", "Each model brings its own settings. FASHN: quality steps and garment guidance.");
await page.getByRole("button", { name: /Generate try-on/ }).click();
await page.waitForSelector(".result .compare-pair", { timeout: 60000 });
await page.evaluate(() => window.scrollTo(0, 0));
await step("generating", "Generating on this PC. The progress names the model, and FitShot checks the photo when it is done.");
mark("wait-start");
await page.waitForFunction(() => !document.querySelector(".result [role=status]"), null, { timeout: 900000, polling: 2000 });
mark("wait-end");
await pause(1500);
await step("result", "The result: before and after side by side, with the Inspection card checking garment, face, skin, body and hands.");

// ---------- Viewer, Inspection, Teach ----------
await page.getByRole("button", { name: "View large" }).first().click();
await page.waitForSelector("dialog.viewer[open] img");
await step("view-large", "View large: full screen, actual size, open on its own or download.");
await page.keyboard.press("Escape");
await pause(600);
const teach = page.getByRole("button", { name: /Tell FitShot what's wrong/ });
if (await teach.count()) {
  await teach.click();
  await page.locator(".teach textarea").fill("The stripes should be a little thinner and the neckline a crew neck.");
  await page.locator(".teach").scrollIntoViewIfNeeded();
  await step("teach", "Tell FitShot what's wrong in your own words. It learns a check for this garment's future photos.");
  await page.getByRole("button", { name: "Cancel" }).click();
}

// ---------- Built-in people ----------
await page.getByRole("button", { name: "Start over" }).click();
await page.getByRole("tab", { name: /^Built-in models/ }).click();
await page.waitForSelector(".person-grid .person-pick");
await step("built-in-people", "Built-in models: your brand's people, each marked full or half body.");
await page.locator(".person-pick", { hasText: "Aiko" }).click();
await page.waitForSelector("#step-garment");
await page.locator(".look-card", { hasText: "DRS-005" }).click();
await page.locator(".photo-type").scrollIntoViewIfNeeded();
await step("built-in-garment", "Pick a garment from the catalog: here the red dress for Aiko.");

// ---------- Results ----------
await page.goto(`${base}/#/results`);
await page.waitForSelector(".photo-grid .tile");
await step("results", "Results: every try-on is kept, with the person, garment, model and settings it was made with.");

// ---------- Models ----------
await page.goto(`${base}/#/models`);
await page.waitForSelector(".model-panel");
await step("models", "Models: the AI models in use, their status, hardware needs and limits.");
await page.getByRole("button", { name: "Add model" }).first().click();
await page.waitForSelector(".catalog-list");
await step("add-model", "Add model: pick from the supported models, configure or download, and it is checked before use.");
await page.keyboard.press("Escape");
await pause(500);
await page.locator(".model-panel", { hasText: "CatVTON" }).getByRole("button", { name: "Remove" }).click();
await page.waitForSelector(".remove-model");
await step("remove-model", "Removing asks first, warns about the default, and never deletes shared files.");
await page.getByRole("button", { name: "Keep it" }).click();

// ---------- Studio tools ----------
await page.goto(`${base}/#/people`);
await pause(1800);
await step("people", "People: the brand's built-in people and their approved photos.");
await page.goto(`${base}/#/review`);
await pause(1800);
await step("review-queue", "Review: photos FitShot could not verify on its own wait here for a person.");
await page.goto(`${base}/#/costs`);
await pause(1800);
await step("costs", "Costs: what each accepted photo really cost, retries included.");

// ---------- Dark theme and phone ----------
await page.evaluate(() => localStorage.setItem("fitshot-theme", "dark"));
await page.goto(`${base}/#/results`);
await page.waitForSelector(".photo-grid .tile");
await step("dark-results", "Dark pages: the same app, photos still on a neutral ground.");
await page.evaluate(() => localStorage.setItem("fitshot-theme", "light"));
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${base}/#/studio`);
await pause(1500);
await step("phone", "On a phone: the same steps, with Try on, Models, Results, Review and More in the bottom bar.");

await context.close();
await browser.close();
const video = readdirSync(rawVideo).find((f) => f.endsWith(".webm"));
if (video) renameSync(`${rawVideo}/${video}`, `${rawVideo}/walkthrough.webm`);
writeFileSync(`${demoDir}/steps.json`, JSON.stringify(steps, null, 2));
console.log("done", steps.filter((s) => s.file).length, "screenshots");
