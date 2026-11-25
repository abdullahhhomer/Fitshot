import { Check, Plus, Sparkles, Upload, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, type BrandModel, type Shot, type Status } from "../api";
import { Empty, ErrorNote, Field, PageTitle, generatorLabel, useAction, usePolled, words } from "../ui";

const PHOTO_MAKERS = ["comfyui", "nano_banana"];

function NewModel({ onDone, onCancel }: { onDone: (id: string) => void; onCancel: () => void }) {
  const { busy, error, run } = useAction();
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    form.set("rights_confirmed", form.get("rights_confirmed") ? "true" : "false");
    let id = "";
    const ok = await run(async () => {
      id = (await api.createModel(form)).id;
    });
    if (ok) onDone(id);
  };
  return (
    <form className="panel" onSubmit={submit}>
      <div className="panel-head">
        <h2>Create a brand model</h2>
        <button type="button" className="icon-btn plain" onClick={onCancel} aria-label="Close form">
          <X size={18} />
        </button>
      </div>
      <div className="form-fields two">
        <Field label="Model name">
          <input name="name" required maxLength={80} placeholder="Ava" />
        </Field>
        <Field label="Reference photo" help="A clear, front-facing photo with exactly one face.">
          <input name="reference" type="file" accept="image/*" required />
        </Field>
      </div>
      <label className="check-line">
        <input type="checkbox" name="rights_confirmed" required />
        <span>This face is AI-generated, or I have this adult's consent to use it.</span>
      </label>
      <div className="form-foot">
        <ErrorNote message={error} />
        <button className="btn primary" disabled={busy}>
          {busy ? "Checking face" : "Create model"}
        </button>
      </div>
    </form>
  );
}

function ShotCard({ shot, onChange }: { shot: Shot; onChange: () => void }) {
  const { busy, error, run } = useAction();
  const decide = (status: "approved" | "rejected") => run(() => api.decideShot(shot.id, status)).then((ok) => ok && onChange());
  const identity = shot.qa?.identity;
  return (
    <article className={`shot-card ${shot.status}`}>
      <div className="shot-photo">
        <img src={shot.url} alt={`${words(shot.pose)} shot`} loading="lazy" />
        {shot.status === "approved" && (
          <span className="shot-flag pass">
            <Check size={13} aria-hidden /> Approved
          </span>
        )}
        {shot.status === "rejected" && (
          <span className="shot-flag fail">
            <X size={13} aria-hidden /> Rejected
          </span>
        )}
      </div>
      <div className="shot-body">
        <h3>{words(shot.pose)}</h3>
        <p className="muted small">
          {shot.status === "approved" ? "Approved" : shot.status === "rejected" ? "Rejected" : "Waiting for approval"}
          {identity?.score != null ? `, face match ${identity.score.toFixed(2)}` : identity ? `. ${identity.reason}` : ""}
        </p>
        <ErrorNote message={error} />
        <div className="shot-actions">
          {shot.status !== "approved" && (
            <button className="btn small" disabled={busy} onClick={() => decide("approved")}>
              <Check size={14} aria-hidden /> Approve
            </button>
          )}
          {shot.status !== "rejected" && (
            <button className="btn small quiet" disabled={busy} onClick={() => decide("rejected")}>
              <X size={14} aria-hidden /> Reject
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function ModelDetail({ model, status, onChange }: { model: BrandModel; status: Status; onChange: () => void }) {
  const shots = usePolled(() => api.shots(model.id), [model.id]);
  // Only generators that really make person photos, and only when they are in use right now.
  const readyGenerators = PHOTO_MAKERS.filter((g) => status.generators[g]?.ready);
  const [scene, setScene] = useState(
    () => status.scenes.find((s) => (model.approved_shots[s] ?? 0) > 0) ?? status.scenes[0],
  );
  const [pose, setPose] = useState(status.poses[0]);
  const [generator, setGenerator] = useState(readyGenerators[0] ?? "");
  const { busy, error, run } = useAction();

  useEffect(() => {
    if (!readyGenerators.includes(generator)) setGenerator(readyGenerators[0] ?? "");
  }, [readyGenerators.join(), generator]);

  const changed = () => {
    void shots.refresh();
    onChange();
  };
  const generate = () => run(() => api.generateShot(model.id, { scene, pose, generator })).then((ok) => ok && changed());
  const upload = (file: File | undefined) => {
    if (!file) return;
    const form = new FormData();
    form.set("scene", scene);
    form.set("pose", pose);
    form.set("image", file);
    void run(() => api.uploadShot(model.id, form)).then((ok) => ok && changed());
  };

  const visible = shots.data?.filter((s) => s.scene === scene) ?? [];

  return (
    <section>
      <div className="model-hero">
        <img src={model.url} alt={`${model.name} reference`} />
        <div>
          <h2>{model.name}</h2>
          <p className="muted">
            Approved shots are reused for every product, so the same face appears across your store. Face-match limits are
            still being tuned, so trust your own eye too.
          </p>
        </div>
      </div>

      <div className="tabs" role="group" aria-label="Scene">
        {status.scenes.map((s) => (
          <button key={s} aria-pressed={s === scene} onClick={() => setScene(s)}>
            {words(s)} <span className="tab-count">{model.approved_shots[s] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="toolbar">
        <Field label="Pose">
          <select value={pose} onChange={(e) => setPose(e.target.value)}>
            {status.poses.map((p) => <option key={p} value={p}>{words(p)}</option>)}
          </select>
        </Field>
        {readyGenerators.length > 1 && (
          <Field label="Generator">
            <select value={generator} onChange={(e) => setGenerator(e.target.value)}>
              {readyGenerators.map((g) => <option key={g} value={g}>{generatorLabel(g)}</option>)}
            </select>
          </Field>
        )}
        <button className="btn primary" disabled={busy || !generator} onClick={generate} title={generator ? undefined : "Add a Gemini key or start ComfyUI first"}>
          <Sparkles size={16} aria-hidden /> {busy ? "Working" : "Generate shot"}
        </button>
        <label className={`btn${busy ? " disabled" : ""}`}>
          <Upload size={16} aria-hidden /> Upload shot
          <input className="visually-hidden" type="file" accept="image/*" disabled={busy} onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
      </div>
      <ErrorNote message={error ?? shots.error} />

      {shots.data && visible.length === 0 ? (
        <Empty mark="Shoot" title={`No ${scene} shots yet`} level={3}>
          <p>Generate or upload a full-body shot, then approve the ones you want to reuse.</p>
        </Empty>
      ) : (
        <div className="shot-grid">
          {visible.map((s) => <ShotCard key={s.id} shot={s} onChange={changed} />)}
        </div>
      )}
    </section>
  );
}

export function Models({ status, modelId }: { status: Status; modelId?: string }) {
  const { data: all, error, refresh } = usePolled(api.models, []);
  // A visitor's own photo lives in the fitting room, not among the brand models.
  const data = all?.filter((m) => m.kind !== "self");
  const [creating, setCreating] = useState(false);
  const selected = data?.find((m) => m.id === modelId) ?? data?.[0];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>People</PageTitle>
          <p>Create one virtual model and reuse the same face across your catalog.</p>
        </div>
        {!creating && (
          <button className="btn primary" onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden /> New model
          </button>
        )}
      </div>
      <ErrorNote message={error} />
      {creating && (
        <NewModel
          onCancel={() => setCreating(false)}
          onDone={(id) => {
            setCreating(false);
            void refresh();
            window.location.hash = `#/people/${id}`;
          }}
        />
      )}
      {data?.length === 0 && !creating && (
        <Empty
          mark="Cast"
          title="Create your first brand model"
          action={
            <button className="btn primary" onClick={() => setCreating(true)}>
              <Plus size={16} aria-hidden /> New model
            </button>
          }
        >
          <p>Upload a clear reference photo of a synthetic or consenting adult model.</p>
        </Empty>
      )}
      {!!data?.length && (
        <>
          {data.length > 1 && (
            <div className="tabs" role="navigation" aria-label="Brand models">
              {data.map((m) => (
                <a key={m.id} href={`#/people/${m.id}`} aria-current={m.id === selected?.id ? "page" : undefined}>
                  {m.name}
                </a>
              ))}
            </div>
          )}
          {selected && <ModelDetail key={selected.id} model={selected} status={status} onChange={refresh} />}
        </>
      )}
    </div>
  );
}
