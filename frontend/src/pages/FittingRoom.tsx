import {
  ArrowLeft, Check, ChevronRight, Cpu, Download, LoaderCircle, Maximize2, PersonStanding, RotateCcw, Shirt, Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type AiModel, type Item, type Person, type Product, type Status } from "../api";
import { EMPTY_FLOW, loadFlow, saveFlow, type Flow } from "../flow";
import { Slip } from "../Slip";
import { DropZone } from "../Upload";
import { Empty, ErrorNote, ItemStatusLabel, PageTitle, useAction, usePolled, words } from "../ui";
import { openViewer } from "../Viewer";

const STEPS = ["Person", "Garment", "AI model", "Review"] as const;

const MODES = {
  full: {
    label: "Full body",
    needs: "Head to feet in the photo",
    tips: ["Stand facing the camera, arms a little away from your body.", "Your whole body visible, feet included.", "Plain background, good even light."],
    use: "For trousers, skirts, dresses and whole outfits.",
  },
  half: {
    label: "Half body",
    needs: "Head to waist or hips in the photo",
    tips: ["Face the camera with your shoulders and chest clearly visible.", "Waist or hips in the frame.", "Plain background, good even light."],
    use: "For shirts, T-shirts, sweaters and jackets.",
  },
} as const;

const CATEGORY_CHOICES = [
  { id: "top", label: "Upper body", note: "Shirts, T-shirts, sweaters, hoodies" },
  { id: "outerwear", label: "Upper body, jacket", note: "Jackets and coats worn over a top" },
  { id: "bottom", label: "Lower body", note: "Trousers, jeans, skirts, shorts" },
  { id: "dress", label: "Dress / one-piece", note: "Dresses and jumpsuits" },
] as const;

const PHOTO_TYPES = {
  "flat-lay": { label: "Flat-lay", note: "The garment on its own: laid flat, on a hanger or a mannequin, on a plain background." },
  model: { label: "Model-worn", note: "A person wearing the garment, as in a shop catalogue." },
} as const;

const categoryLabel = (id: string) => CATEGORY_CHOICES.find((c) => c.id === id)?.label ?? words(id);
/** One name per model, the same on every page. */
const modelLabel = (m: Pick<AiModel, "name">) => m.name;
const busy = (item?: Item) => item?.status === "queued" || item?.status === "running";

/** Why this model cannot dress this person in this garment, or null when it can. */
function blocker(model: AiModel, person: Person | null, product: Product | undefined, photoType: string | null) {
  if (product && !model.categories.includes(product.category)) return `Cannot dress ${categoryLabel(product.category).toLowerCase()} garments.`;
  if (person && !model.person_modes.includes(person.framing)) return `Does not support ${person.framing}-body photos.`;
  if (photoType && model.photo_types.length && !model.photo_types.includes(photoType)) {
    return `Works with ${model.photo_types.map((t) => PHOTO_TYPES[t as keyof typeof PHOTO_TYPES]?.label.toLowerCase() ?? t).join(" or ")} garment photos only.`;
  }
  return null;
}

function Stepper({ step, done, onGo }: { step: number; done: boolean[]; onGo: (step: 1 | 2 | 3 | 4) => void }) {
  return (
    <ol className="flow-steps" aria-label="Try-on steps">
      {STEPS.map((label, index) => {
        const n = (index + 1) as 1 | 2 | 3 | 4;
        const state = n === step ? "current" : done[index] ? "done" : "todo";
        const reachable = n < step || (done.slice(0, index).every(Boolean) && n <= 4);
        return (
          <li key={label} className={`flow-step ${state}`}>
            <button type="button" onClick={() => onGo(n)} disabled={!reachable || n === step} aria-current={n === step ? "step" : undefined}>
              <span className="step-mark" aria-hidden>{state === "done" ? <Check size={14} /> : n}</span>
              <span className="step-label">{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function StepFoot({ back, next, nextLabel = "Continue", disabled, why }: { back?: () => void; next?: () => void; nextLabel?: string; disabled?: boolean; why?: string | null }) {
  return (
    <div className="step-foot">
      {back ? (
        <button type="button" className="btn quiet" onClick={back}>
          <ArrowLeft size={16} aria-hidden /> Back
        </button>
      ) : <span />}
      <div className="step-next">
        {why && <span className="field-help">{why}</span>}
        {next && (
          <button type="button" className="btn primary" disabled={disabled} onClick={next}>
            {nextLabel} <ChevronRight size={16} aria-hidden />
          </button>
        )}
      </div>
    </div>
  );
}

function PersonCard({ person, selected, onSelect, onRemove }: { person: Person; selected: boolean; onSelect: () => void; onRemove?: () => void }) {
  return (
    <div className={`person-card${selected ? " on" : ""}`}>
      <button type="button" className="person-pick" aria-pressed={selected} onClick={onSelect}>
        <span className="person-photo">
          <img src={person.url} alt={`${person.name}, ${person.framing} body`} loading="lazy" />
          {selected && <span className="person-check" aria-hidden><Check size={15} /></span>}
        </span>
        <span className="person-name">{person.name}</span>
        <span className="person-meta">
          <span className="tag-word">{person.framing === "full" ? "Full body" : "Half body"}</span>
          {person.fits.length === 4 ? "Any garment" : "Tops and jackets"}
        </span>
      </button>
      {onRemove && (
        <button type="button" className="text-button person-remove" onClick={onRemove}>
          Remove this photo
        </button>
      )}
    </div>
  );
}

/** Step 1, Live: the visitor's own photo, full or half body. */
function LivePerson({ flow, set, onPicked }: { flow: Flow; set: (patch: Partial<Flow>) => void; onPicked: (p: Person) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const upload = useAction();
  const removal = useAction();
  const photos = usePolled(api.livePhotos, []);
  const mode = MODES[flow.liveMode];

  const use = () =>
    upload.run(async () => {
      if (!file) throw new Error("Add a photo first.");
      if (!consent) throw new Error("Tick the box to confirm the photo is of you and that you are 18 or older.");
      const form = new FormData();
      form.set("photo", file);
      form.set("mode", flow.liveMode);
      form.set("consent", "true");
      const me = await api.createSelfie(form);
      const mine = (await api.livePhotos()).find((p) => p.model_id === me.id);
      if (!mine) throw new Error("The photo was saved but could not be read back. Try again.");
      setFile(null);
      onPicked(mine);
    });

  return (
    <div className="live">
      <div className="mode-choice" role="radiogroup" aria-label="Person photo mode">
        {(["full", "half"] as const).map((id) => (
          <button key={id} type="button" role="radio" aria-checked={flow.liveMode === id} className="mode-card" onClick={() => set({ liveMode: id })}>
            <PersonStanding size={22} aria-hidden className={id === "half" ? "half-icon" : undefined} />
            <span className="mode-name">{MODES[id].label}</span>
            <span className="mode-needs">{MODES[id].needs}</span>
          </button>
        ))}
      </div>
      <div className="guide">
        <p className="guide-use">{mode.use}</p>
        <ul>
          {mode.tips.map((tip) => <li key={tip}>{tip}</li>)}
        </ul>
        {flow.liveMode === "half" && <p className="field-help">Half-body photos can only wear tops and jackets: FitShot never invents the parts of you the photo does not show.</p>}
      </div>
      <DropZone
        file={file}
        onFile={(f) => {
          setFile(f);
          upload.clear();
        }}
        title={`Your ${mode.label.toLowerCase()} photo`}
        hint="Drag a photo here, choose one from your device, or take one with the camera."
        camera="body"
      />
      <label className="check-line">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>This is a photo of me, and I'm 18 or older.</span>
      </label>
      <p className="field-help">Your photo is saved in FitShot's data folder on this computer, and you can remove it any time. Online models (marked "online") send it to their service to be processed.</p>
      <ErrorNote message={upload.error} />
      <button type="button" className="btn primary" disabled={upload.busy || !file} onClick={() => void use()}>
        {upload.busy ? "Checking your photo" : "Use this photo"}
      </button>

      {!!photos.data?.length && (
        <section className="recent" aria-labelledby="recent-title">
          <h3 id="recent-title">Your recent photos</h3>
          <div className="person-grid">
            {photos.data.map((p) => (
              <PersonCard
                key={p.shot_id}
                person={p}
                selected={flow.person?.shot_id === p.shot_id}
                onSelect={() => onPicked(p)}
                onRemove={() =>
                  void removal.run(() => api.removeSelfie(p.model_id)).then((ok) => {
                    if (!ok) return;
                    if (flow.person?.shot_id === p.shot_id) set({ person: null });
                    void photos.refresh();
                  })
                }
              />
            ))}
          </div>
          <ErrorNote message={removal.error} />
        </section>
      )}
    </div>
  );
}

/** Step 1, Built-in: approved photos of the brand's people. */
function BuiltInPerson({ flow, onPicked }: { flow: Flow; onPicked: (p: Person) => void }) {
  const people = usePolled(api.people, []);
  if (!people.data) return <p className="muted" aria-busy="true">Loading people</p>;
  if (!people.data.length) {
    return (
      <Empty mark="Cast" title="No built-in people yet" level={3} action={<a className="btn" href="#/people">Add a person</a>}>
        <p>Built-in people are approved photos of your brand's models. Add one on the People page, or use the Live tab with your own photo.</p>
      </Empty>
    );
  }
  return (
    <div className="person-grid">
      {people.data.map((p) => (
        <PersonCard key={p.shot_id} person={{ ...p, name: `${p.name}, ${words(p.pose)}` }} selected={flow.person?.shot_id === p.shot_id} onSelect={() => onPicked(p)} />
      ))}
    </div>
  );
}

/** Step 2: a garment from the catalogue or a new upload, with its category and photo type. */
function GarmentStep({ flow, set, products, onAdded }: { flow: Flow; set: (patch: Partial<Flow>) => void; products: Product[]; onAdded: () => Promise<unknown> }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("top");
  const upload = useAction();
  const fits = flow.person?.fits ?? ["top", "outerwear", "bottom", "dress"];
  const chosen = products.find((p) => p.id === flow.productId);

  const add = () =>
    upload.run(async () => {
      if (!file) throw new Error("Add a garment photo first.");
      const form = new FormData();
      form.set("sku", `UP-${Date.now().toString(36).toUpperCase().slice(-5)}`);
      form.set("name", name.trim() || file.name.replace(/\.[^.]+$/, "").slice(0, 100) || "Uploaded garment");
      form.set("category", category);
      form.set("front", file);
      const product = await api.createProduct(form);
      await onAdded();
      setFile(null);
      setName("");
      set({ productId: product.id, photoType: product.photo_type ?? "flat-lay" });
    });

  return (
    <div className="garment-step">
      <section className="garment-upload" aria-labelledby="upload-title">
        <h3 id="upload-title">Upload a garment</h3>
        <DropZone file={file} onFile={(f) => { setFile(f); upload.clear(); }} title="Garment photo" hint="A shop photo works best: flat-lay or worn by a model." />
        {file && (
          <div className="garment-fields">
            <label className="field">
              <span className="field-label">Name (optional)</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder={file.name.replace(/\.[^.]+$/, "")} maxLength={100} />
            </label>
            <div className="field">
              <span className="field-label">Category</span>
              <div className="choice-list" role="radiogroup" aria-label="Garment category">
                {CATEGORY_CHOICES.map((c) => {
                  const ok = fits.includes(c.id);
                  return (
                    <button key={c.id} type="button" role="radio" aria-checked={category === c.id} disabled={!ok} className="choice" onClick={() => setCategory(c.id)}>
                      <span className="choice-name">{c.label}</span>
                      <span className="choice-note">{ok ? c.note : "Needs a full-body photo"}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <ErrorNote message={upload.error} />
            <button type="button" className="btn primary" disabled={upload.busy} onClick={() => void add()}>
              {upload.busy ? "Adding the garment" : "Use this garment"}
            </button>
          </div>
        )}
      </section>

      <section aria-labelledby="catalog-title">
        <h3 id="catalog-title">Or pick one of your garments</h3>
        {products.length ? (
          <div className="look-grid wide">
            {products.map((p) => {
              const ok = fits.includes(p.category);
              return (
                <button
                  key={p.id}
                  type="button"
                  className={`look-card${p.id === flow.productId ? " on" : ""}`}
                  aria-pressed={p.id === flow.productId}
                  disabled={!ok}
                  title={ok ? undefined : "This photo shows the upper body only"}
                  onClick={() => set({ productId: p.id, photoType: p.photo_type ?? "flat-lay" })}
                >
                  <img src={p.url} alt="" loading="lazy" />
                  <span className="look-name"><b>{p.sku}</b> {p.name}</span>
                  <span className="look-cat">{ok ? categoryLabel(p.category) : "Needs a full-body photo"}</span>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="muted">No garments yet. Upload one above.</p>
        )}
      </section>

      {chosen && (
        <section className="photo-type" aria-labelledby="type-title">
          <h3 id="type-title">What kind of garment photo is it?</h3>
          <p className="field-help">
            FitShot detected <b>{PHOTO_TYPES[(chosen.photo_type ?? "flat-lay") as keyof typeof PHOTO_TYPES].label.toLowerCase()}</b>. Change it if that is wrong.
          </p>
          <div className="choice-list two" role="radiogroup" aria-label="Garment photo type">
            {(Object.keys(PHOTO_TYPES) as (keyof typeof PHOTO_TYPES)[]).map((id) => (
              <button key={id} type="button" role="radio" aria-checked={flow.photoType === id} className="choice" onClick={() => set({ photoType: id })}>
                <span className="choice-name">{PHOTO_TYPES[id].label}</span>
                <span className="choice-note">{PHOTO_TYPES[id].note}</span>
              </button>
            ))}
          </div>
          {chosen.photo_type && flow.photoType && flow.photoType !== chosen.photo_type && (
            <p className="note warn" role="status">
              {flow.photoType === "model"
                ? "No person was found in this garment photo. Model-worn mode cuts the garment out of a person, so with a flat-lay photo it pastes the whole picture on. FitShot will run it as flat-lay."
                : "A person was found wearing this garment. As a flat-lay, the model may copy the whole photo, person included. Choose model-worn unless you are sure."}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

/** Step 3: an available AI model from the registry. */
function ModelStep({ flow, set, models, product }: { flow: Flow; set: (patch: Partial<Flow>) => void; models: AiModel[]; product?: Product }) {
  const available = models.filter((m) => m.available);
  const waiting = models.filter((m) => !m.available);
  const picked = models.find((m) => m.id === flow.modelId);
  if (!available.length) {
    return (
      <Empty mark="Add" title="No AI model is ready" level={3} action={<a className="btn primary" href="#/models">Add a model</a>}>
        <p>
          {waiting.length
            ? `${waiting.map((m) => modelLabel(m)).join(", ")} ${waiting.length === 1 ? "is" : "are"} added but not ready. Open Models to see why.`
            : "Add a try-on model on the Models page. FASHN VTON 1.5 gives the most realistic results."}
        </p>
      </Empty>
    );
  }
  return (
    <div className="model-step">
      {picked && !picked.available && (
        <p className="note error" role="alert">
          {modelLabel(picked)} is no longer available: {picked.detail} Choose another model.
        </p>
      )}
      <div className="model-choices" role="radiogroup" aria-label="AI model">
        {available.map((m) => {
          const why = blocker(m, flow.person, product, flow.photoType);
          return (
            <button key={m.id} type="button" role="radio" aria-checked={flow.modelId === m.id} disabled={!!why} className="model-choice" onClick={() => set({ modelId: m.id, settings: {} })}>
              <span className="model-head">
                <span className="model-name">{m.name}</span>
                <span className="model-version">Version {m.version}</span>
                {m.is_default && <span className="tag-word">Default</span>}
              </span>
              <span className="model-facts">
                <span><Cpu size={13} aria-hidden /> {m.location === "local" ? "Runs on this PC" : "Online"}</span>
                <span>{m.categories.map(categoryLabel).join(", ")}</span>
              </span>
              <span className="choice-note">{why ?? m.limitations}</span>
            </button>
          );
        })}
      </div>
      {!!waiting.length && (
        <p className="field-help">
          Not ready: {waiting.map((m) => `${modelLabel(m)} (${m.detail})`).join("; ")} <a href="#/models">Manage models</a>
        </p>
      )}
    </div>
  );
}

function Summary({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="summary">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The result of one generation: progress while it runs, then before/after and its inspection. */
function ResultView({ flow, status, model, product, onEdit, onChange }: {
  flow: Flow; status: Status; model?: AiModel; product?: Product;
  onEdit: (step: 1 | 2 | 3 | 4) => void; onChange: () => void;
}) {
  const job = usePolled(() => (flow.jobId ? api.job(flow.jobId) : Promise.resolve(null)), [flow.jobId], 2000);
  const item = job.data?.items[0];
  const retry = useAction();
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!busy(item)) return;
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, [item?.status]);
  const name = model ? modelLabel(model) : flow.modelId ?? "the model";
  const seconds = Math.max(0, Math.round((now - started) / 1000));

  if (!item) return <p className="muted" aria-busy="true">Starting the try-on with {name}</p>;
  const done = !busy(item) && item.url;
  const images = [
    ...(item.url ? [{ src: item.url, alt: `${flow.person?.name} wearing ${item.product_name}`, caption: `${item.sku} ${item.product_name}, ${name}` }] : []),
    ...(flow.person ? [{ src: flow.person.url, alt: `Original photo of ${flow.person.name}`, caption: "Original photo" }] : []),
  ];

  return (
    <div className="result">
      <div className="result-main">
        <div className="compare-pair">
          <figure>
            <span className="compare-photo-frame">{flow.person && <img src={flow.person.url} alt={`Original photo of ${flow.person.name}`} />}</span>
            <figcaption>Before</figcaption>
          </figure>
          <figure>
            <span className="compare-photo-frame">
              {done ? (
                <button type="button" className="stage-open" onClick={() => openViewer(images)} aria-label="View the result large">
                  <img src={item.url!} alt={`${flow.person?.name} wearing ${item.product_name}`} />
                </button>
              ) : (
                flow.person && <img className="waiting" src={flow.person.url} alt="" />
              )}
              {busy(item) && (
                <span className="stage-flag" role="status">
                  <LoaderCircle size={16} className="spin" aria-hidden />{" "}
                  {item.not_before
                    ? "Waiting for the free Hugging Face quota to reset."
                    : item.status === "queued"
                      ? `Waiting for the GPU, ${seconds} s`
                      : `${name} is trying it on and FitShot is checking it, ${seconds} s`}
                </span>
              )}
            </span>
            <figcaption>
              After, with {name} <ItemStatusLabel status={item.status} />
            </figcaption>
          </figure>
        </div>
        {item.status === "failed" && (
          <div className="result-failed">
            <ErrorNote message={item.error ?? "The try-on failed."} />
            <div className="result-actions">
              <button type="button" className="btn primary" disabled={retry.busy} onClick={() => void retry.run(() => api.retry(item.id)).then(() => job.refresh())}>
                <RotateCcw size={15} aria-hidden /> Try again
              </button>
              <button type="button" className="btn quiet" onClick={() => onEdit(3)}>Choose another model</button>
            </div>
            <ErrorNote message={retry.error} />
          </div>
        )}
        <div className="result-actions">
          {done && (
            <>
              <button type="button" className="btn" onClick={() => openViewer(images)}>
                <Maximize2 size={15} aria-hidden /> View large
              </button>
              <a className="btn" href={item.url!} download={`${item.sku}-${flow.modelId}.png`}>
                <Download size={15} aria-hidden /> Download
              </a>
            </>
          )}
          <button type="button" className="btn quiet" onClick={() => onEdit(4)}>Different settings</button>
          <button type="button" className="btn quiet" onClick={() => onEdit(3)}>Another model</button>
          <button type="button" className="btn quiet" onClick={() => onEdit(2)}>Another garment</button>
          <a className="text-button" href="#/results">All results</a>
        </div>
        <p className="field-help">
          Saved in Results with the model and settings it was made with. Another try-on never replaces this one.
          {product && ` ${product.sku}, ${categoryLabel(product.category).toLowerCase()}.`}
        </p>
      </div>
      <aside className="result-side">
        <Slip key={item.id} item={item} generators={status.generators} showEvidence={false} onChange={() => { void job.refresh(); onChange(); }} onDeleted={() => onEdit(4)} />
      </aside>
    </div>
  );
}

export function FittingRoom({ status, onChange }: { status: Status; onChange: () => void }) {
  const [flow, setFlow] = useState<Flow>(loadFlow);
  const set = (patch: Partial<Flow>) => setFlow((current) => ({ ...current, ...patch }));
  useEffect(() => saveFlow(flow), [flow]);

  const products = usePolled(api.products, []);
  const models = usePolled(api.aiModels, [], 10000);
  const start = useAction();
  const added = models.data?.added ?? [];
  const product = products.data?.find((p) => p.id === flow.productId);
  const model = added.find((m) => m.id === flow.modelId);

  // The default model is chosen for you once, never swapped in silently later.
  useEffect(() => {
    if (flow.modelId || !models.data) return;
    const preferred = added.find((m) => m.is_default && m.available) ?? added.find((m) => m.available);
    if (preferred) set({ modelId: preferred.id });
  }, [models.data, flow.modelId]);

  const modelWhy = model ? (model.available ? blocker(model, flow.person, product, flow.photoType) : `${modelLabel(model)} is not available: ${model.detail}`) : "Choose a model.";
  const done = [!!flow.person, !!product, !!model && !modelWhy, false];
  const go = (step: Flow["step"]) => set({ step });
  const settings = useMemo(
    () => Object.fromEntries((model?.settings ?? []).map((s) => [s.key, flow.settings[s.key] ?? s.default])),
    [model, flow.settings],
  );

  const generate = () =>
    start.run(async () => {
      if (!flow.person || !product || !model) throw new Error("Choose a person, a garment and a model first.");
      const options: Record<string, number | string> = { ...settings };
      if (flow.photoType && model.photo_types.length > 1) options.photo_type = flow.photoType;
      const job = await api.startJob({
        product_ids: [product.id], model_id: flow.person.model_id, scene: flow.person.scene, shot_id: flow.person.shot_id,
        generator: model.id, num_images: 1, settings: options,
      });
      set({ jobId: job.id, step: 5 });
      onChange();
    });

  const pickPerson = (person: Person) => {
    // A new person may not suit the garment chosen before (a half-body photo and trousers).
    const keep = product && person.fits.includes(product.category);
    set({ person, step: 2, ...(keep ? {} : { productId: null, photoType: null }) });
  };

  return (
    <div className="page fitting">
      <div className="page-head">
        <div>
          <PageTitle>Fitting room</PageTitle>
          <p>Choose a person, a garment and an AI model, check the summary, then try it on.</p>
        </div>
        {flow.step !== 1 && (
          <button type="button" className="btn quiet" onClick={() => setFlow({ ...EMPTY_FLOW, modelId: flow.modelId })}>
            Start over
          </button>
        )}
      </div>

      {flow.step !== 5 && <Stepper step={flow.step} done={done} onGo={go} />}

      {flow.step === 1 && (
        <section className="step-panel" aria-labelledby="step-person">
          <h2 id="step-person">Who is wearing it?</h2>
          <div className="big-tabs" role="tablist" aria-label="Person source">
            <button type="button" role="tab" aria-selected={flow.source === "live"} onClick={() => set({ source: "live" })}>
              <span className="big-tab-name">Live</span>
              <span className="big-tab-note">Your own photo</span>
            </button>
            <button type="button" role="tab" aria-selected={flow.source === "builtin"} onClick={() => set({ source: "builtin" })}>
              <span className="big-tab-name">Built-in models</span>
              <span className="big-tab-note">Your brand's people</span>
            </button>
          </div>
          <div role="tabpanel" aria-label={flow.source === "live" ? "Live" : "Built-in models"}>
            {flow.source === "live" ? <LivePerson flow={flow} set={set} onPicked={pickPerson} /> : <BuiltInPerson flow={flow} onPicked={pickPerson} />}
          </div>
          <StepFoot next={() => go(2)} disabled={!flow.person} why={flow.person ? `Selected: ${flow.person.name}` : "Choose or upload a person photo."} />
        </section>
      )}

      {flow.step === 2 && (
        <section className="step-panel" aria-labelledby="step-garment">
          <h2 id="step-garment">Which garment?</h2>
          <GarmentStep flow={flow} set={set} products={products.data ?? []} onAdded={products.refresh} />
          <StepFoot back={() => go(1)} next={() => go(3)} disabled={!product} why={product ? `Selected: ${product.sku} ${product.name}` : "Upload or pick a garment."} />
        </section>
      )}

      {flow.step === 3 && (
        <section className="step-panel" aria-labelledby="step-model">
          <h2 id="step-model">Which AI model?</h2>
          {models.data ? <ModelStep flow={flow} set={set} models={added} product={product} /> : <p className="muted" aria-busy="true">Loading models</p>}
          <StepFoot back={() => go(2)} next={() => go(4)} disabled={!!modelWhy} why={modelWhy} />
        </section>
      )}

      {flow.step === 4 && (
        <section className="step-panel" aria-labelledby="step-review">
          <h2 id="step-review">Check and try it on</h2>
          <div className="review-grid">
            <div className="review-photos">
              <figure>
                {flow.person ? <img src={flow.person.url} alt={`${flow.person.name}`} /> : <span className="no-photo">No person</span>}
                <figcaption><PersonStanding size={14} aria-hidden /> Person</figcaption>
              </figure>
              <figure>
                {product ? <img src={product.url} alt={product.name} /> : <span className="no-photo">No garment</span>}
                <figcaption><Shirt size={14} aria-hidden /> Garment</figcaption>
              </figure>
            </div>
            <div className="review-facts">
              <Summary
                rows={[
                  ["Person", flow.person ? `${flow.person.name} (${flow.person.kind === "self" ? "live photo" : "built-in"})` : "Not chosen"],
                  ["Photo mode", flow.person ? (flow.person.framing === "full" ? "Full body" : "Half body") : "-"],
                  ["Garment", product ? `${product.sku} ${product.name}` : "Not chosen"],
                  ["Category", product ? categoryLabel(product.category) : "-"],
                  ["Garment photo", flow.photoType ? PHOTO_TYPES[flow.photoType].label : "-"],
                  ["AI model", model ? `${modelLabel(model)}, ${model.location === "local" ? "runs on this PC" : "online"}` : "Not chosen"],
                ]}
              />
              {model && model.settings.length > 0 && (
                <div className="settings">
                  <h3>Settings for {model.name}</h3>
                  {model.settings.map((s) => (
                    <label key={s.key} className="setting">
                      <span className="setting-head">
                        <span className="field-label">{s.label}</span>
                        <output>{settings[s.key]}</output>
                      </span>
                      <input
                        type="range"
                        min={s.minimum}
                        max={s.maximum}
                        step={s.step}
                        value={settings[s.key]}
                        onChange={(e) => set({ settings: { ...flow.settings, [s.key]: Number(e.target.value) } })}
                      />
                      <span className="field-help">{s.help}</span>
                    </label>
                  ))}
                </div>
              )}
              {model?.location === "online" && <p className="field-help">This model runs online: the person and garment photos are sent to its service.</p>}
              {modelWhy && <p className="note error" role="alert">{modelWhy}</p>}
              <ErrorNote message={start.error} />
              <div className="step-foot">
                <button type="button" className="btn quiet" onClick={() => go(3)}>
                  <ArrowLeft size={16} aria-hidden /> Back to edit
                </button>
                <button type="button" className="btn try-on" disabled={start.busy || !!modelWhy || !flow.person || !product} onClick={() => void generate()}>
                  <Sparkles size={17} aria-hidden /> {start.busy ? "Starting" : "Generate try-on"}
                </button>
              </div>
              <p className="field-help">FitShot shows how the garment looks on the photo. It does not predict real size or fit.</p>
            </div>
          </div>
        </section>
      )}

      {flow.step === 5 && flow.jobId && (
        <ResultView flow={flow} status={status} model={model} product={product} onEdit={go} onChange={onChange} />
      )}
      {flow.step === 5 && !flow.jobId && (
        <StepFoot back={() => go(4)} why="No try-on is running." />
      )}
    </div>
  );
}
