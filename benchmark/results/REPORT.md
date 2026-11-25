# Try-on benchmark

Seed 42. Synthetic people only. Checks are FitShot's QA gates (no Gemini judge).

| Scenario | Generator | Time (s) | GPU peak (MiB) | Output | Color | Pattern | Face | Skin | Body |
|---|---|---|---|---|---|---|---|---|---|
| Full body + flat-lay striped tee | fashn | 80.5 | 5646 | 896x1152 | pass (4.99) | pass (0.97) | pass (1.00) | pass (0.84) | pass (0.08) |
| Full body + flat-lay striped tee | catvton | 109.8 | 7067 | 896x1152 | pass (6.84) | review (0.95) | pass (1.00) | pass (0.38) | pass (0.06) |
| Half body + flat-lay tee | fashn | 59.6 | 4118 | 896x645 | pass (1.14) | pass (0.73) | pass (0.99) | pass (0.87) | pass (0.13) |
| Half body + flat-lay tee | catvton | 101.8 | 7176 | 896x645 | pass (4.97) | pass (0.84) | pass (1.00) | pass (0.58) | pass (0.17) |
| Full body + model-worn tee | fashn | 60.1 | 4118 | 896x1152 | pass (7.46) | review (0.62) | pass (0.99) | pass (0.36) | pass (0.07) |
| Full body + model-worn tee | catvton | 47.1 | 3789 | 896x1152 | review (14.42) | review (0.68) | pass (0.99) | pass (1.06) | pass (0.05) |
| Half body + model-worn tee | fashn | 59.5 | 4118 | 896x645 | pass (7.14) | review (0.62) | pass (1.00) | pass (0.95) | pass (0.15) |
| Half body + model-worn tee | catvton | 45.9 | 4341 | 896x645 | pass (8.46) | review (0.66) | pass (1.00) | pass (0.58) | pass (0.15) |
| Full body + flat-lay trousers | fashn | 58.8 | 4118 | 896x1152 | pass (3.28) | pass (0.97) | pass (1.00) | pass (0.95) | pass (0.07) |
| Full body + flat-lay trousers | catvton | 45.5 | 4341 | 896x1152 | pass (4.24) | review (0.71) | pass (1.00) | pass (0.95) | pass (0.07) |
| Full body + flat-lay patterned dress | fashn | 59.0 | 4118 | 896x1152 | pass (5.40) | pass (0.99) | pass (1.00) | pass (6.10) | pass (0.18) |
| Full body + flat-lay patterned dress | catvton | 102.4 | 7067 | 896x1152 | fail (15.14) | pass (0.73) | pass (1.00) | pass (1.43) | pass (0.17) |
| Hand-on-hip pose + flat-lay jacket | fashn | 59.0 | 4118 | 896x1152 | pass (2.30) | pass (0.87) | pass (0.99) | pass (0.89) | pass (0.10) |
| Hand-on-hip pose + flat-lay jacket | catvton | 45.9 | 4341 | 896x1152 | pass (8.77) | pass (0.77) | pass (1.00) | pass (0.61) | pass (0.07) |

Color is a Delta E distance (lower is closer). Pattern and Face are similarities (higher is closer). Body is limb-length drift (lower is closer). GPU peak is the whole GPU, read with nvidia-smi; for FASHN the work runs on Hugging Face, so the local figure is what other programs already held.

See sheet.jpg for the images side by side.
