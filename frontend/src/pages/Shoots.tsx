import { ArrowLeft, Check, ChevronRight, Download, Plus, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, apiUrl, type BrandModel, type Item, type ItemStatus, type Product, type Status } from "../api";
import { SlipDock } from "../Slip";
import { Empty, ErrorNote, Field, GridSkeleton, PageTitle, PhotoTile, generatorLabel, money, shortDate, useAction, usePolled, words } from "../ui";

const CSV_TEMPLATE =
  "data:text/csv;charset=utf-8," +
  encodeURIComponent("sku,name,category,image,back_image\nLIN-014,Linen camp shirt,top,lin-014-front.jpg,lin-014-back.jpg\n");

const FILTERS: { id: string; label: string; statuses: ItemStatus[] }[] = [
  { id: "all", label: "All", statuses: [] },
  { id: "ready", label: "Ready", statuses: ["passed", "approved"] },
  { id: "check", label: "Needs check", statuses: ["review"] },
  { id: "active", label: "In progress", statuses: ["queued", "running"] },
  { id: "failed", label: "Failed or rejected", statuses: ["failed", "rejected"] },
];

function Setup({ models, products }: { models: BrandModel[]; products: Product[] }) {
  const hasModel = models.length > 0;
  const hasShot = models.some((m) => Object.values(m.approved_shots).some((n) => n > 0));
  const steps = [
    { done: hasModel, label: "Add a person", href: "#/people" },
    { done: hasShot, label: "Generate and approve a photo of them", href: "#/people" },
    { done: products.length > 0, label: "Add a garment", href: "#/garments" },
  ];
  return (
    <Empty mark="Start" title="Set up your first photoshoot">
      <p>FitShot needs a model, an approved shot and a garment before it can produce catalog photos.</p>
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.label} className={step.done ? "done" : undefined}>
            {step.done && <Check size={16} aria-hidden />}
            {step.done ? <span>{step.label}</span> : <a href={step.href}>{step.label}</a>}
            {step.done && <span className="visually-hidden"> (done)</span>}
          </li>
        ))}
      </ol>
    </Empty>
  );
}

function NewShoot({ status, models, products, onCancel }: { status: Status; models: BrandModel[]; products: Product[]; onCancel: () => void }) {
  const ready = Object.entries(status.generators).filter(([, g]) => g.ready && g.dresses).map(([name]) => name);
  const [mode, setMode] = useState<"pick" | "bulk">("pick");
  const [modelId, setModelId] = useState(models[0]?.id ?? "");
  const [scene, setScene] = useState(
    () => status.scenes.find((s) => (models[0]?.approved_shots[s] ?? 0) > 0) ?? status.scenes[0],
  );
  const [count, setCount] = useState(() => Math.max(Math.min(4, models[0]?.approved_shots[scene] ?? 4), 1));
  const [generator, setGenerator] = useState(ready.includes(status.default_generator) ? status.default_generator : ready[0] ?? "");
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const { busy, error, run } = useAction();

  const model = models.find((m) => m.id === modelId);
  const shotsAvailable = model?.approved_shots[scene] ?? 0;
  const perGarment = Math.min(count, shotsAvailable);
  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChosen(next);
  };

  const open = (id: string) => {
    window.location.hash = `#/shoots/${id}`;
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mode === "pick") {
      let id = "";
      const ok = await run(async () => {
        id = (await api.startJob({ product_ids: [...chosen], model_id: modelId, scene, generator, num_images: count })).id;
      });
      if (ok) open(id);
      return;
    }
    const form = new FormData(event.currentTarget);
    form.set("model_id", modelId);
    form.set("scene", scene);
    form.set("generator", generator);
    form.set("num_images", String(count));
    let id = "";
    const ok = await run(async () => {
      id = (await api.startBulk(form)).id;
    });
    if (ok) open(id);
  };

  const blocker = !ready.length
    ? "Add a Gemini key or start ComfyUI to generate photos."
    : !shotsAvailable
      ? `Approve a ${scene} shot for this model first.`
      : mode === "pick" && chosen.size === 0
        ? "Choose at least one garment."
        : null;

  return (
    <form className="panel" onSubmit={submit}>
      <div className="panel-head">
        <h2>New photoshoot</h2>
        <button type="button" className="icon-btn plain" onClick={onCancel} aria-label="Close form">
          <X size={18} />
        </button>
      </div>
      <div className="form-fields four">
        <Field label="Brand model">
          <select value={modelId} onChange={(e) => setModelId(e.target.value)}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Field>
        <Field label="Scene" help={`${shotsAvailable} approved ${shotsAvailable === 1 ? "shot" : "shots"}`}>
          <select value={scene} onChange={(e) => setScene(e.target.value)}>
            {status.scenes.map((s) => <option key={s} value={s}>{words(s)}</option>)}
          </select>
        </Field>
        <Field label="Photos per garment" help={shotsAvailable && perGarment < count ? `Limited to ${perGarment} by approved shots` : undefined}>
          <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </Field>
        <Field label="Generator">
          <select value={generator} onChange={(e) => setGenerator(e.target.value)} disabled={!ready.length}>
            {!ready.length && <option value="">None ready</option>}
            {ready.map((g) => <option key={g} value={g}>{generatorLabel(g)}</option>)}
          </select>
        </Field>
      </div>

      <div className="tabs" role="group" aria-label="Garment source">
        <button type="button" aria-pressed={mode === "pick"} onClick={() => setMode("pick")}>Choose garments</button>
        <button type="button" aria-pressed={mode === "bulk"} onClick={() => setMode("bulk")}>Bulk CSV</button>
      </div>

      {mode === "pick" ? (
        products.length ? (
          <div className="pick-grid">
            {products.map((p) => (
              <label key={p.id} className={`pick${chosen.has(p.id) ? " on" : ""}`}>
                <input type="checkbox" checked={chosen.has(p.id)} onChange={() => toggle(p.id)} />
                <img src={p.url} alt="" loading="lazy" />
                <span><b>{p.sku}</b> {p.name}</span>
              </label>
            ))}
          </div>
        ) : (
          <p className="muted">No garments yet. <a href="#/garments">Add a garment</a> or use a bulk CSV.</p>
        )
      ) : (
        <div className="form-fields two">
          <Field label="Products CSV" help="Columns: sku, name, category, image, and optional back_image.">
            <input name="csv_file" type="file" accept=".csv,text/csv" required />
          </Field>
          <Field label="Images ZIP" help="File names must match the image column.">
            <input name="images_zip" type="file" accept=".zip,application/zip" required />
          </Field>
          <a className="text-link" href={CSV_TEMPLATE} download="fitshot-products.csv">Download CSV template</a>
        </div>
      )}

      <div className="form-foot">
        <ErrorNote message={error} />
        {blocker && <span className="muted small">{blocker}</span>}
        <button className="btn primary" disabled={busy || !!blocker}>
          {busy
            ? "Starting"
            : mode === "pick" && chosen.size
              ? `Create ${chosen.size * perGarment} ${chosen.size * perGarment === 1 ? "photo" : "photos"}`
              : "Start photoshoot"}
        </button>
      </div>
    </form>
  );
}

function JobView({ jobId, status, onChange }: { jobId: string; status: Status; onChange: () => void }) {
  const { data: job, error, refresh } = usePolled(() => api.job(jobId), [jobId], 2500);
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [slipOpen, setSlipOpen] = useState(false);

  const visible: Item[] = useMemo(() => {
    const rule = FILTERS.find((f) => f.id === filter)!;
    return (job?.items ?? []).filter((i) => !rule.statuses.length || rule.statuses.includes(i.status));
  }, [job, filter]);

  // The slip always describes a photo the user can currently see.
  useEffect(() => {
    if (!job) return;
    if (!visible.some((i) => i.id === selectedId)) {
      const first = visible.find((i) => i.status === "review") ?? visible[0];
      setSelectedId(first?.id ?? null);
      if (!first) setSlipOpen(false);
    }
  }, [job, visible, selectedId]);

  const selected = visible.find((i) => i.id === selectedId);
  const changed = () => {
    void refresh();
    onChange();
  };

  if (error && !job) {
    return (
      <div className="page">
        <a className="back" href="#/shoots"><ArrowLeft size={15} aria-hidden /> Photoshoots</a>
        <ErrorNote message={error} />
      </div>
    );
  }
  if (!job) {
    return (
      <div className="page">
        <GridSkeleton />
      </div>
    );
  }

  const waiting = job.counts.review ?? 0;
  const active = (job.counts.queued ?? 0) + (job.counts.running ?? 0);

  return (
    <div className={`workspace${selected ? " has-slip" : ""}`}>
      <div className="page">
        <a className="back" href="#/shoots"><ArrowLeft size={15} aria-hidden /> Photoshoots</a>
        <div className="page-head">
          <div>
            <PageTitle>{words(job.scene)} photoshoot</PageTitle>
            <p>
              {job.total} photos, {job.accepted} ready
              {waiting ? `, ${waiting} waiting for you` : ""}
              {active ? `, ${active} in progress` : ""}
            </p>
          </div>
          {job.accepted > 0 ? (
            <a className="btn primary" href={apiUrl(`/api/jobs/${job.id}/export`)} download>
              <Download size={16} aria-hidden /> Export {job.accepted} {job.accepted === 1 ? "photo" : "photos"}
            </a>
          ) : (
            <button className="btn primary" disabled title="Approve or verify a photo first">
              <Download size={16} aria-hidden /> Export
            </button>
          )}
        </div>

        {active > 0 && (
          <div className="progress" role="progressbar" aria-label="Photoshoot progress" aria-valuemin={0} aria-valuemax={job.total} aria-valuenow={job.total - active}>
            <span style={{ width: `${((job.total - active) / job.total) * 100}%` }} />
          </div>
        )}

        <div className="tabs" role="group" aria-label="Filter photos">
          {FILTERS.map((f) => {
            const n = f.statuses.length ? f.statuses.reduce((sum, s) => sum + (job.counts[s] ?? 0), 0) : job.total;
            return (
              <button key={f.id} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                {f.label} <span className="tab-count">{n}</span>
              </button>
            );
          })}
        </div>

        {visible.length === 0 ? (
          <p className="muted">No photos match this filter.</p>
        ) : (
          <div className="photo-grid">
            {visible.map((item) => (
              <PhotoTile
                key={item.id}
                item={item}
                selected={item.id === selectedId}
                onSelect={() => {
                  setSelectedId(item.id);
                  setSlipOpen(true);
                }}
              />
            ))}
          </div>
        )}
        <p className="cost-foot">
          Spent {money(job.usd)}
          {job.usd_per_accepted !== null ? `, ${money(job.usd_per_accepted)} per accepted photo` : ""}.
        </p>
      </div>
      <SlipDock item={selected} open={slipOpen} generators={status.generators} onChange={changed} onClose={() => setSlipOpen(false)} />
    </div>
  );
}

export function Shoots({ status, jobId, onChange }: { status: Status; jobId?: string; onChange: () => void }) {
  const jobs = usePolled(api.jobs, [jobId], jobId ? 0 : 4000);
  const models = usePolled(() => api.models().then((list) => list.filter((m) => m.kind !== "self")), [jobId]);
  const products = usePolled(api.products, [jobId]);
  const [creating, setCreating] = useState(false);

  if (jobId) return <JobView key={jobId} jobId={jobId} status={status} onChange={onChange} />;

  const loading = !jobs.data || !models.data || !products.data;
  const canStart = !!models.data?.some((m) => Object.values(m.approved_shots).some((n) => n > 0));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>Photoshoots</PageTitle>
          <p>Every photo is inspected before it can be exported.</p>
        </div>
        {!creating && canStart && (
          <button className="btn primary" onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden /> New photoshoot
          </button>
        )}
      </div>
      <ErrorNote message={jobs.error ?? models.error ?? products.error} />
      {loading ? (
        <GridSkeleton />
      ) : (
        <>
          {creating && <NewShoot status={status} models={models.data!} products={products.data!} onCancel={() => setCreating(false)} />}
          {jobs.data!.length === 0 && !creating && (
            canStart && products.data!.length > 0 ? (
              <Empty
                mark="Go"
                title="Ready for your first photoshoot"
                action={
                  <button className="btn primary" onClick={() => setCreating(true)}>
                    <Plus size={16} aria-hidden /> New photoshoot
                  </button>
                }
              >
                <p>Choose garments and a scene. FitShot will generate and inspect each photo.</p>
              </Empty>
            ) : (
              <Setup models={models.data!} products={products.data!} />
            )
          )}
          {jobs.data!.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Photoshoot</th>
                    <th scope="col" className="hide-sm">Started</th>
                    <th scope="col" className="num">Ready</th>
                    <th scope="col" className="num">Your check</th>
                    <th scope="col" className="num hide-sm">Spent</th>
                    <th scope="col"><span className="visually-hidden">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.data!.map((job) => {
                    const waiting = job.counts.review ?? 0;
                    return (
                      <tr key={job.id} className="row-link">
                        <td><a href={`#/shoots/${job.id}`}><b>{words(job.scene)}</b>, {job.total} photos{job.kind === "bulk" ? ", bulk" : ""}</a></td>
                        <td className="hide-sm">{shortDate(job.created_at)}</td>
                        <td className="num">{job.accepted} of {job.total}</td>
                        <td className="num">{waiting ? <span className="need-you">{waiting} {waiting === 1 ? "needs" : "need"} you</span> : "None"}</td>
                        <td className="num hide-sm">{money(job.usd)}</td>
                        <td className="chevron"><ChevronRight size={17} aria-hidden /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
