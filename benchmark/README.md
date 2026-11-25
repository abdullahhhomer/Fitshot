# Try-on benchmark

Compares FASHN VTON 1.5 and CatVTON on the same inputs, seed 42. FASHN runs on this PC when
`run-fashn.cmd` is running (no quota), otherwise on Hugging Face.
Every person here is synthetic.

```powershell
cd backend
uv run python ../benchmark/run.py                # both generators, all scenarios
uv run python ../benchmark/run.py --only fashn   # finish FASHN after its quota resets
```

Existing outputs are kept unless `--force` is given, because FASHN uses the daily Hugging Face
GPU quota of `HF_TOKEN` (about 9 images a day on a free account).

## Inputs (`inputs/`)

| File | Origin |
|---|---|
| `person_full_hoodie.png` | ComfyUI shot of the synthetic brand model's reference face, prompted with a black zip hoodie |
| `person_half_hoodie.png` | The same image cropped to head-to-hips |
| `person_pose_hand_on_hip.png` | Approved hand-on-hip shot of the synthetic brand model |
| `garment_*_flatlay.png` (tees, jacket) | `samples/` |
| `garment_navy_tee_model_worn.png` | An approved FitShot try-on of the synthetic model in the navy tee |
| `garment_beige_chinos_flatlay.png`, `garment_red_polka_dress_flatlay.png` | Generated with the local ComfyUI checkpoint |

## Results (`results/`)

`REPORT.md` (timings, GPU memory, QA scores), `sheet.jpg` (all images side by side),
`metrics.json`, and one folder of outputs per generator.

Scores are FitShot's own QA gates without the Gemini judge. Face identity scores about 1.0 for
both generators because both keep the original face, so judge identity by eye. For a
model-worn garment the pattern score compares against the whole model photo, so it reads low
even when the garment is right.
