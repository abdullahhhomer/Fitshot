# Deploying FitShot with Vercel

FitShot has two halves:

| Half | What it needs | Where it runs |
|---|---|---|
| The app you click (React) | Static files | **Vercel** |
| The engine (FastAPI, SQLite, ComfyUI, CatVTON, face and pose models) | An NVIDIA GPU, about 20 GB of models, a disk that keeps your photos, and a worker that runs for minutes | **Your PC**, reached through a secure tunnel |

Vercel can't run the engine: it has no GPU, its functions are limited to 250 MB and short run times, and it has no lasting disk. So Vercel hosts the app, and the app talks to your PC over HTTPS.

```text
phone or laptop ──► https://your-app.vercel.app      (Vercel: the React app)
                         │  API calls with your access key
                         ▼
                 https://xyz.trycloudflare.com      (Cloudflare Tunnel)
                         ▼
                 your PC: FitShot on :8000, ComfyUI on :8188, CatVTON on :8190
```

Your PC must be on and running FitShot for the Vercel site to work.

## 1. Lock your FitShot

Once FitShot is reachable from the internet, anyone with the link could upload photos or use your GPU. Add these lines to `.env` in the project folder:

```ini
# A long random secret. Anyone with it can use your FitShot.
FITSHOT_ACCESS_KEY=paste-a-long-random-string-here
# Your Vercel address. Fill this in after step 3, then restart FitShot.
FITSHOT_CORS_ORIGINS=https://your-app.vercel.app
```

To make a random key in PowerShell:

```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | % {[char]$_})
```

With the key set, every API call and every photo needs it. The Vercel site asks for it once and remembers it in that browser.

## 2. Start FitShot and open a tunnel

Start the three local services, each in its own window:

```powershell
.\run-comfyui.cmd
.\run-catvton.cmd
.\run.cmd
```

Install Cloudflare's tunnel tool once:

```powershell
winget install --id Cloudflare.cloudflared
```

Then open a tunnel to FitShot:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints an address like `https://xyz-abc.trycloudflare.com`. Keep this window open.

Quick tunnels get a new address every time they start. For a permanent address, create a named tunnel on a domain you own (see Cloudflare's "Create a locally-managed tunnel" guide). After that, the address stays the same and you set it in Vercel only once.

## 3. Deploy the app to Vercel

From the `frontend` folder:

```powershell
cd frontend
npx vercel login
npx vercel link
npx vercel env add VITE_API_BASE production
```

When it asks for a value, paste the tunnel address from step 2, with no trailing slash. Then deploy:

```powershell
npx vercel --prod
```

`frontend/vercel.json` already tells Vercel how to build it (Vite, `npm run build`, output in `dist`). If you import the repository in the Vercel dashboard instead, set **Root Directory** to `frontend` and add the `VITE_API_BASE` environment variable there.

Vercel prints your site address. Put it in `FITSHOT_CORS_ORIGINS` (step 1) and restart `run.cmd`.

## 4. Open it

Visit your Vercel address. FitShot asks for the access key. Enter the `FITSHOT_ACCESS_KEY` value and it opens the fitting room.

## When the tunnel address changes

A quick tunnel gets a new address on every restart. When that happens, update the variable and redeploy:

```powershell
cd frontend
npx vercel env rm VITE_API_BASE production
npx vercel env add VITE_API_BASE production
npx vercel --prod
```

A named tunnel (step 2) avoids this.

## Notes

- **Privacy:** your own photos ("Try it on yourself") are stored only on your PC, in `data/media`. They travel to the browser over the HTTPS tunnel, and only with the access key. To delete them, use **Remove my photo** in the fitting room.
- **Speed:** a try-on takes 1 to 3 minutes on this laptop's GPU. The site shows progress while it works.
- **Upload size:** photos are limited to 20 MB each.
- **Engine without your PC:** the engine could move to a rented GPU server, such as RunPod or a cloud VM with an NVIDIA GPU. Run the same setup scripts there, then point `VITE_API_BASE` at that server. Vercel doesn't change.
