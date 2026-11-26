# Running FitShot with Docker

One image holds everything: the app, FASHN VTON 1.5, CatVTON, ComfyUI and every model they use. The models are downloaded while the image builds, so the first build takes a while, and after that nothing is fetched at run time.

## What you need

- Linux, or Windows 11 with WSL 2 and Docker Desktop.
- An NVIDIA GPU with 8 GB or more, a recent driver, and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Docker Desktop on Windows includes GPU support through WSL 2.
- About 30 GB of free disk for the build and a good internet connection.
- 16 GB of RAM or more.

## Run it

```bash
git clone https://github.com/abdullahhhomer/Fitshot.git
cd Fitshot
cp .env.example .env        # optional: add GEMINI_API_KEY for the vision checks
docker compose up --build
```

Open <http://127.0.0.1:8000> when the log shows the app is running. The first try-on takes longer while FASHN loads onto the GPU.

Stop it with `Ctrl+C`, or `docker compose down`. Your photos, results and database are kept in the `fitshot-data` volume and survive rebuilds. `docker compose down -v` deletes them.

## What the build downloads

| Part | About | Used for |
|---|---|---|
| ComfyUI, InstantID, RealVisXL, OpenPose, antelopev2 | 14 GB with its Python environment | Making built-in people's photos |
| CatVTON and its weights | 6 GB with its Python environment | Second try-on model (non-commercial licence) |
| FASHN VTON 1.5 weights | 2.6 GB | Default try-on model |
| InsightFace, MediaPipe, rembg | 0.5 GB | The Inspection checks |

To leave ComfyUI out (about 14 GB less, but built-in people's photos can't be made):

```bash
docker compose build --build-arg WITH_COMFYUI=0
docker compose up
```

The build uses the same `scripts/setup_*.sh` as the Windows setup, so both install the same models.

## Settings

Everything in `.env.example` works here too. Two differences from the Windows setup:

- `DEFAULT_GENERATOR` defaults to `fashn`, the local model, so it works without any API key.
- The app is published on `127.0.0.1:8000` only, so other computers can't reach it. Read [DEPLOY.md](DEPLOY.md) and set `FITSHOT_ACCESS_KEY` before changing that.

## Without a GPU

The app starts, but the local try-on models can't run. Online models still work: FASHN on Hugging Face with `HF_TOKEN`, or Nano Banana with `GEMINI_API_KEY`.
