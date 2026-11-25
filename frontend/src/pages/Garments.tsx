import { Plus, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type PointerEvent } from "react";
import { api, type LogoBox, type Status } from "../api";
import { Empty, ErrorNote, Field, PageTitle, useAction, usePolled, words } from "../ui";

function LogoMarker({ src, box, onChange }: { src: string; box: LogoBox | null; onChange: (box: LogoBox | null) => void }) {
  const area = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  const point = (event: PointerEvent) => {
    const rect = area.current!.getBoundingClientRect();
    return {
      x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
      y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1),
    };
  };
  const down = (event: PointerEvent) => {
    event.preventDefault();
    area.current!.setPointerCapture(event.pointerId);
    start.current = point(event);
    onChange(null);
  };
  const move = (event: PointerEvent) => {
    if (!start.current) return;
    const p = point(event);
    onChange({
      x: Math.min(start.current.x, p.x),
      y: Math.min(start.current.y, p.y),
      w: Math.abs(p.x - start.current.x),
      h: Math.abs(p.y - start.current.y),
    });
  };
  const up = () => {
    start.current = null;
    if (box && (box.w < 0.02 || box.h < 0.02)) onChange(null);
  };

  return (
    <div className="logo-marker" ref={area} onPointerDown={down} onPointerMove={move} onPointerUp={up}>
      <img src={src} alt="Garment preview. Drag across the logo to mark it." draggable={false} />
      {box && (
        <span
          className="logo-box"
          style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.w * 100}%`, height: `${box.h * 100}%` }}
        />
      )}
    </div>
  );
}

function AddGarment({ status, onDone, onCancel }: { status: Status; onDone: () => void; onCancel: () => void }) {
  const [front, setFront] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [box, setBox] = useState<LogoBox | null>(null);
  const { busy, error, run } = useAction();

  useEffect(() => {
    if (!front) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(front);
    setPreview(url);
    setBox(null);
    return () => URL.revokeObjectURL(url);
  }, [front]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const back = form.get("back");
    if (back instanceof File && back.size === 0) form.delete("back");
    if (box) form.set("logo_box", JSON.stringify(box));
    if (await run(() => api.createProduct(form))) onDone();
  };

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <div className="panel-head">
        <h2>Add a garment</h2>
        <button type="button" className="icon-btn plain" onClick={onCancel} aria-label="Close form">
          <X size={18} />
        </button>
      </div>
      <div className="form-fields">
        <Field label="SKU">
          <input name="sku" required maxLength={64} placeholder="LIN-014" />
        </Field>
        <Field label="Name">
          <input name="name" required maxLength={120} placeholder="Linen camp shirt" />
        </Field>
        <Field label="Category">
          <select name="category" defaultValue={status.categories[0]}>
            {status.categories.map((c) => (
              <option key={c} value={c}>{words(c)}</option>
            ))}
          </select>
        </Field>
        <Field label="Front photo" help="A flat photo on a plain background works best.">
          <input name="front" type="file" accept="image/*" required onChange={(e) => setFront(e.target.files?.[0] ?? null)} />
        </Field>
        <Field label="Back photo (optional)" help="Helps the generator see the garment's back. FitShot's poses all face forward.">
          <input name="back" type="file" accept="image/*" />
        </Field>
      </div>
      <div>
        {preview ? (
          <>
            <span className="field-label">Mark the logo (optional)</span>
            <LogoMarker src={preview} box={box} onChange={setBox} />
            <span className="field-help">{box ? "Logo marked. Drag again to change it." : "Drag across the logo so FitShot can check it."}</span>
          </>
        ) : (
          <div className="preview-empty">Choose a front photo to preview it here.</div>
        )}
      </div>
      <div className="form-foot">
        <ErrorNote message={error} />
        <button className="btn primary" disabled={busy}>
          {busy ? "Saving" : "Save garment"}
        </button>
      </div>
    </form>
  );
}

export function Garments({ status, fromStudio = false }: { status: Status; fromStudio?: boolean }) {
  const { data, error, refresh } = usePolled(api.products, []);
  const [adding, setAdding] = useState(fromStudio);
  const finish = () => {
    setAdding(false);
    if (fromStudio) window.location.hash = "#/studio";
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>Garments</PageTitle>
          <p>{data ? `${data.length} ${data.length === 1 ? "garment" : "garments"} in your catalog` : "Loading garments"}</p>
        </div>
        {!adding && (
          <button className="btn primary" onClick={() => setAdding(true)}>
            <Plus size={16} aria-hidden /> Add garment
          </button>
        )}
      </div>
      <ErrorNote message={error} />
      {adding && (
        <AddGarment
          status={status}
          onCancel={finish}
          onDone={() => {
            void refresh();
            finish();
          }}
        />
      )}
      {data?.length === 0 && !adding && (
        <Empty
          mark="Add"
          title="Add your first garment"
          action={
            <button className="btn primary" onClick={() => setAdding(true)}>
              <Plus size={16} aria-hidden /> Add garment
            </button>
          }
        >
          <p>Upload a flat photo of a shirt, dress or jacket. FitShot compares every generated photo against it.</p>
        </Empty>
      )}
      {!!data?.length && (
        <div className="catalog-grid">
          {data.map((p) => (
            <article className="catalog-item" key={p.id}>
              <img src={p.url} alt={p.name} loading="lazy" />
              <h2>{p.name}</h2>
              <p>
                {p.sku}, {words(p.category)}
                {p.logo_box ? ", logo marked" : ""}
              </p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
