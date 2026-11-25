"""Seed a demo copy of FitShot with synthetic people and garments only.

Usage: python demo/scripts/seed_demo.py [api-base]   (default http://127.0.0.1:8015/api)
Run it against an app started with its own DATA_DIR, never your real studio data.
"""
import sys
import time
from pathlib import Path

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8015/api"
ROOT = Path(__file__).resolve().parents[2]
PEOPLE = ROOT / "demo" / "inputs" / "people"
SAMPLES, BENCH = ROOT / "samples", ROOT / "benchmark" / "inputs"
client = httpx.Client(timeout=300)

for _ in range(40):
    try:
        client.get(f"{API}/status").raise_for_status()
        break
    except httpx.HTTPError:
        time.sleep(2)


def person(name, reference, shots):
    if any(m["name"] == name for m in client.get(f"{API}/models").json()):
        return
    model = client.post(f"{API}/models", data={"name": name, "rights_confirmed": "true"},
                        files={"reference": ("ref.png", open(reference, "rb").read(), "image/png")})
    model.raise_for_status()
    for path, pose in shots:
        shot = client.post(f"{API}/models/{model.json()['id']}/shots/upload", data={"scene": "studio", "pose": pose},
                           files={"image": ("shot.png", open(path, "rb").read(), "image/png")})
        shot.raise_for_status()
        client.patch(f"{API}/shots/{shot.json()['id']}", json={"status": "approved"}).raise_for_status()
    print("person:", name)


person("Mara (synthetic)", PEOPLE / "mara.png",
       [(PEOPLE / "mara_front.png", "front"), (PEOPLE / "mara_hand_on_hip.png", "hand_on_hip")])
for key, name in (("rohan", "Rohan (synthetic)"), ("daniel", "Daniel (synthetic)"), ("aiko", "Aiko (synthetic)")):
    person(name, PEOPLE / f"{key}.png", [(PEOPLE / f"{key}.png", "front")])

existing = {p["sku"] for p in client.get(f"{API}/products").json()}
for sku, name, category, path in (
    ("NVY-001", "Navy crew tee", "top", f"{SAMPLES}/garment_navy_tee.png"),
    ("STR-002", "Breton stripe tee", "top", f"{SAMPLES}/garment_stripe_tee.png"),
    ("OLV-003", "Olive work jacket", "outerwear", f"{SAMPLES}/garment_olive_jacket.png"),
    ("CHN-004", "Beige chinos", "bottom", f"{BENCH}/garment_beige_chinos_flatlay.png"),
    ("DRS-005", "Red polka dress", "dress", f"{BENCH}/garment_red_polka_dress_flatlay.png"),
):
    if sku in existing:
        continue
    client.post(f"{API}/products", data={"sku": sku, "name": name, "category": category},
                files={"front": ("g.png", open(path, "rb").read(), "image/png")}).raise_for_status()
    print("garment:", sku)

# Only the models in use, as in the real app.
models = client.get(f"{API}/ai-models").json()["added"]
if any(m["id"] == "fashn_hosted" for m in models):
    client.delete(f"{API}/ai-models/fashn_hosted").raise_for_status()
print("models:", [m["name"] for m in client.get(f"{API}/ai-models").json()["added"]])

# Two earlier try-ons, so Results shows a history.
if not client.get(f"{API}/results").json():
    people = {p["name"]: p for p in client.get(f"{API}/people").json()}
    products = {p["sku"]: p for p in client.get(f"{API}/products").json()}
    for who, sku in (("Daniel (synthetic)", "NVY-001"), ("Aiko (synthetic)", "DRS-005")):
        p = people[who]
        job = client.post(f"{API}/jobs", json={
            "product_ids": [products[sku]["id"]], "model_id": p["model_id"], "scene": p["scene"], "shot_id": p["shot_id"],
            "generator": "fashn", "num_images": 1, "settings": {"steps": 30, "guidance": 1.5},
        })
        job.raise_for_status()
        print("started:", who, sku)
    t0 = time.time()
    while any(r["status"] in ("queued", "running") for r in client.get(f"{API}/results").json()):
        time.sleep(5)
    print(f"history ready in {time.time() - t0:.0f}s:", [(r["person_name"], r["sku"], r["status"]) for r in client.get(f"{API}/results").json()])
