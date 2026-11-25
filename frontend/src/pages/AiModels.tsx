import { CircleAlert, CircleCheck, Cpu, Globe, LoaderCircle, Plus, RefreshCw, Star, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type AiModel } from "../api";
import { Empty, ErrorNote, PageTitle, useAction, usePolled, words } from "../ui";

const CATEGORY_WORDS: Record<string, string> = { top: "tops", outerwear: "jackets", bottom: "trousers and skirts", dress: "dresses" };
const gb = (bytes: number) => `${(bytes / 2 ** 30).toFixed(bytes > 2 ** 30 ? 1 : 2)} GB`;

function StatusWord({ model }: { model: AiModel }) {
  const available = model.status === "ready" && model.validated;
  const [Icon, tone, label] =
    model.status === "downloading"
      ? [LoaderCircle, "muted", `Downloading ${Math.round((model.progress ?? 0) * 100)}%`]
      : available
        ? [CircleCheck, "pass", "Ready"]
        : model.status === "error"
          ? [CircleAlert, "fail", "Not installed"]
          : [CircleAlert, "check", "Unavailable"];
  return (
    <span className={`status ${tone}`}>
      <Icon size={14} aria-hidden className={model.status === "downloading" ? "spin" : undefined} /> {label}
    </span>
  );
}

function Facts({ model }: { model: AiModel }) {
  const rows: [string, ReactNode][] = [
    ["Runs", model.location === "local" ? "On this PC" : "Online"],
    ["Garments", model.categories.map((c) => CATEGORY_WORDS[c] ?? c).join(", ")],
    ["Person photos", model.person_modes.map((m) => `${m} body`).join(", ")],
    ["Garment photos", model.photo_types.length ? model.photo_types.map(words).join(", ") : "Any"],
    ["Hardware", model.hardware],
    ["Limits", model.limitations],
    ["Licence", model.license],
  ];
  if (model.location === "local" && model.path) rows.push(["Files", model.path]);
  return (
    <dl className="facts">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="selfie-dialog model-dialog" aria-label={title} onClose={onClose}>
      <div className="selfie-dialog-head">
        <h2>{title}</h2>
        <button type="button" className="icon-btn plain" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>
      </div>
      <div className="model-dialog-body">{open && children}</div>
    </dialog>
  );
}

/** Choose a model, configure where its files are (or download them), then validate it. */
function AddModel({ catalog, onDone }: { catalog: AiModel[]; onDone: () => void }) {
  const [choice, setChoice] = useState<AiModel | null>(null);
  const [path, setPath] = useState("");
  const [download, setDownload] = useState(false);
  const [result, setResult] = useState<AiModel | null>(null);
  const action = useAction();
  const watch = usePolled(
    () => (result?.status === "downloading" ? api.aiModels().then((r) => r.added.find((m) => m.id === result.id) ?? null) : Promise.resolve(result)),
    [result?.id, result?.status],
    2000,
  );
  const live = watch.data ?? result;

  if (live) {
    const available = live.status === "ready" && live.validated;
    return (
      <div className="add-result" aria-live="polite">
        <p className="add-title">{live.name}</p>
        {live.status === "downloading" ? (
          <>
            <div className="progress" role="progressbar" aria-valuenow={Math.round((live.progress ?? 0) * 100)} aria-valuemin={0} aria-valuemax={100}>
              <span style={{ width: `${Math.round((live.progress ?? 0) * 100)}%` }} />
            </div>
            <p className="field-help">{live.detail}</p>
          </>
        ) : available ? (
          <p className="add-ok"><CircleCheck size={18} aria-hidden /> Installed and checked. It is now available in the Fitting room.</p>
        ) : (
          <>
            <p className="note error" role="alert">Added, but it cannot be used yet: {live.detail}</p>
            <p className="field-help">{live.setup_hint} It stays out of the Fitting room until it passes this check.</p>
            <button type="button" className="btn" disabled={action.busy} onClick={() => void action.run(async () => setResult(await api.validateAiModel(live.id)))}>
              <RefreshCw size={15} aria-hidden /> Check again
            </button>
          </>
        )}
        <ErrorNote message={action.error} />
        <button type="button" className="btn primary" onClick={onDone}>Done</button>
      </div>
    );
  }

  if (!choice) {
    return (
      <div className="catalog-list">
        {!catalog.length && <p className="muted">Every supported model is already added.</p>}
        {catalog.map((m) => (
          <button key={m.id} type="button" className="model-choice" disabled={!m.supported} onClick={() => { setChoice(m); setPath(m.default_path ?? ""); setDownload(false); }}>
            <span className="model-head">
              <span className="model-name">{m.name}</span>
              <span className="model-version">Version {m.version}</span>
              {!m.supported && <span className="tag-word">Not supported yet</span>}
            </span>
            <span className="choice-note">{m.description}</span>
            <span className="model-facts">
              <span>{m.location === "local" ? <Cpu size={13} aria-hidden /> : <Globe size={13} aria-hidden />} {m.location === "local" ? `On this PC${m.size_gb ? `, ${m.size_gb} GB` : ""}` : "Online"}</span>
            </span>
          </button>
        ))}
      </div>
    );
  }

  const add = () =>
    action.run(async () => {
      setResult(await api.addAiModel({ id: choice.id, path: choice.location === "local" ? path.trim() || undefined : undefined, download }));
    });

  return (
    <div className="configure">
      <p className="add-title">{choice.name}</p>
      <Facts model={choice} />
      {choice.location === "local" ? (
        <>
          <label className="field">
            <span className="field-label">Model files folder</span>
            <input value={path} onChange={(e) => setPath(e.target.value)} placeholder={choice.default_path ?? ""} />
            <span className="field-help">Relative to the FitShot folder, or a full path.</span>
          </label>
          {choice.download && (
            <label className="check-line">
              <input type="checkbox" checked={download} onChange={(e) => setDownload(e.target.checked)} />
              <span>Download the model files into that folder (about {choice.size_gb} GB).</span>
            </label>
          )}
        </>
      ) : null}
      <p className="field-help">{choice.setup_hint}</p>
      <ErrorNote message={action.error} />
      <div className="step-foot">
        <button type="button" className="btn quiet" onClick={() => setChoice(null)}>Back</button>
        <button type="button" className="btn primary" disabled={action.busy} onClick={() => void add()}>
          {action.busy ? "Adding and checking" : download ? "Download and add" : "Add and check"}
        </button>
      </div>
    </div>
  );
}

/** Confirm removal; offer to delete only files that belong to this model alone. */
function RemoveModel({ model, others, onDone }: { model: AiModel; others: AiModel[]; onDone: () => void }) {
  const files = usePolled(() => api.aiModelFiles(model.id), [model.id]);
  const [deleteFiles, setDeleteFiles] = useState(false);
  const action = useAction();
  const nextDefault = others.find((m) => m.id !== model.id);
  const total = (files.data ?? []).reduce((sum, f) => sum + f.bytes, 0);
  return (
    <div className="remove-model">
      <p>
        Remove <b>{model.name}</b> from FitShot? It will no longer be offered in the Fitting room. Past results made with it stay in Results.
      </p>
      {model.is_default && (
        <p className="note warn">
          This is your default model. {nextDefault ? `${nextDefault.name} becomes the default.` : "No other model is added, so the Fitting room will ask you to add one."}
        </p>
      )}
      {!!files.data?.length && (
        <label className="check-line">
          <input type="checkbox" checked={deleteFiles} onChange={(e) => setDeleteFiles(e.target.checked)} />
          <span>
            Also delete its files ({gb(total)}): {files.data.map((f) => f.path).join(", ")}. Shared Python environments and other models' files are never deleted.
          </span>
        </label>
      )}
      <ErrorNote message={action.error} />
      <div className="step-foot">
        <button type="button" className="btn quiet" onClick={onDone}>Keep it</button>
        <button type="button" className="btn danger" disabled={action.busy} onClick={() => void action.run(() => api.removeAiModel(model.id, deleteFiles)).then((ok) => ok && onDone())}>
          <Trash2 size={15} aria-hidden /> {action.busy ? "Removing" : "Remove model"}
        </button>
      </div>
    </div>
  );
}

export function AiModels() {
  const models = usePolled(api.aiModels, [], 5000);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<AiModel | null>(null);
  const action = useAction();
  const added = models.data?.added ?? [];
  const refresh = () => void models.refresh();

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>Models</PageTitle>
          <p>The AI models that put garments on people. Only models that are installed and pass their check appear in the Fitting room.</p>
        </div>
        <button type="button" className="btn primary" onClick={() => setAdding(true)}>
          <Plus size={16} aria-hidden /> Add model
        </button>
      </div>
      <ErrorNote message={models.error ?? action.error} />
      {models.data && !added.length && (
        <Empty mark="Add" title="No AI model added" action={<button type="button" className="btn primary" onClick={() => setAdding(true)}>Add model</button>}>
          <p>Add FASHN VTON 1.5 for the most realistic try-ons. Until a model is added and ready, the Fitting room cannot generate.</p>
        </Empty>
      )}
      <div className="model-list">
        {added.map((m) => (
          <article key={m.id} className="model-panel" aria-labelledby={`model-${m.id}`}>
            <header className="model-panel-head">
              <div>
                <h2 id={`model-${m.id}`}>{m.name}</h2>
                <p className="model-version">Version {m.version}</p>
              </div>
              <div className="model-badges">
                {m.is_default && <span className="tag-word"><Star size={12} aria-hidden /> Default</span>}
                <StatusWord model={m} />
              </div>
            </header>
            <p className="model-desc">{m.description}</p>
            {m.status !== "ready" && <p className="field-help model-why">{m.detail} {m.status !== "downloading" && m.setup_hint}</p>}
            {m.status === "downloading" && (
              <div className="progress" role="progressbar" aria-valuenow={Math.round((m.progress ?? 0) * 100)} aria-valuemin={0} aria-valuemax={100}>
                <span style={{ width: `${Math.round((m.progress ?? 0) * 100)}%` }} />
              </div>
            )}
            <Facts model={m} />
            <div className="model-actions">
              {!m.is_default && (
                <button type="button" className="btn small" disabled={action.busy || !(m.status === "ready" && m.validated)} onClick={() => void action.run(() => api.defaultAiModel(m.id)).then(refresh)}>
                  Make default
                </button>
              )}
              <button type="button" className="btn small quiet" disabled={action.busy} onClick={() => void action.run(() => api.validateAiModel(m.id)).then(refresh)}>
                <RefreshCw size={14} aria-hidden /> Check again
              </button>
              <button type="button" className="btn small quiet" onClick={() => setRemoving(m)}>
                <Trash2 size={14} aria-hidden /> Remove
              </button>
            </div>
          </article>
        ))}
      </div>

      <Dialog open={adding} title="Add a model" onClose={() => { setAdding(false); refresh(); }}>
        <AddModel catalog={models.data?.catalog ?? []} onDone={() => { setAdding(false); refresh(); }} />
      </Dialog>
      <Dialog open={!!removing} title="Remove model" onClose={() => { setRemoving(null); refresh(); }}>
        {removing && <RemoveModel model={removing} others={added} onDone={() => { setRemoving(null); refresh(); }} />}
      </Dialog>
    </div>
  );
}
