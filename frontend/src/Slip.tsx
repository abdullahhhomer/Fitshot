import { Check, ChevronDown, CircleAlert, GraduationCap, Maximize2, Minus, RotateCcw, Trash2, Undo2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Gate, type GateStatus, type Item, type Lesson, type Status } from "./api";
import { Burst } from "./marks";
import { ErrorNote, ITEM_LABEL, useAction, useMediaQuery, usePolled, words } from "./ui";
import { openViewer, type ViewImage } from "./Viewer";

const CHECKS: [string, string][] = [
  ["garment_color", "Garment color"],
  ["garment_pattern", "Pattern"],
  ["garment_logo", "Logo"],
  ["garment_structure", "Structure"],
  ["identity", "Face"],
  ["skin_tone", "Skin tone"],
  ["body_pose", "Body"],
  ["hands", "Hands"],
];

const RESULT: Record<string, Record<GateStatus, string>> = {
  garment_color: {
    pass: "The garment's color matches the real product.",
    review: "The color is close but may have shifted. Compare it by eye.",
    fail: "The color differs from the real product.",
  },
  garment_pattern: {
    pass: "The pattern and fabric look the same as the product.",
    review: "The pattern or fabric may have changed. Compare them by eye.",
    fail: "The pattern or fabric differs from the product.",
  },
  garment_logo: {
    pass: "The marked logo was found on the garment.",
    review: "Only part of the logo could be matched. Check it closely.",
    fail: "The marked logo couldn't be found on the garment.",
  },
  garment_structure: {
    pass: "Collar, sleeves, hem and details match the product.",
    review: "Garment details couldn't be confirmed automatically. Check them yourself.",
    fail: "A garment detail doesn't match the product.",
  },
  identity: {
    pass: "This is the same face as your brand model.",
    review: "The face is similar but may not be the same person.",
    fail: "The face doesn't match your brand model.",
  },
  skin_tone: {
    pass: "The skin tone matches your brand model.",
    review: "The skin tone may have shifted. Compare it by eye.",
    fail: "The skin tone differs from your brand model.",
  },
  body_pose: {
    pass: "Body proportions match the approved shot.",
    review: "Body proportions couldn't be confirmed. Check them yourself.",
    fail: "Body proportions changed from the approved shot.",
  },
  hands: {
    pass: "The hands look natural.",
    review: "The hands couldn't be confirmed automatically. Check them yourself.",
    fail: "The hands look wrong.",
  },
};

const PROBLEM: Record<string, string> = {
  garment_color: "The garment's color may have shifted.",
  garment_pattern: "The pattern or fabric may have changed.",
  garment_logo: "The logo may have changed.",
  garment_structure: "A garment detail may not match the product.",
  identity: "The model's face may not match.",
  skin_tone: "The model's skin tone may have shifted.",
  body_pose: "The body proportions may be off.",
  hands: "The hands need a closer look.",
};

const inProgress = (item: Item) => item.status === "queued" || item.status === "running";

function summary(item: Item): string {
  if (item.status === "queued") return "Waiting for its turn.";
  if (item.status === "running") return "Generating and inspecting this photo.";
  if (item.status === "failed") return item.error ?? "No photo could be generated.";
  if (item.status === "approved") return "You checked this photo and approved it.";
  if (item.status === "rejected") return "You rejected this photo. It won't be exported.";
  if (item.status === "passed") {
    return item.has_logo
      ? "Every check passed. This photo is ready to export."
      : "All checks passed and this photo is ready to export. No logo was marked, so logo wasn't checked.";
  }
  const gates = item.qa?.gates ?? [];
  const problem = gates.find((g) => g.status === "fail") ?? gates.find((g) => g.status === "review");
  if (!problem) return "Check this photo before publishing.";
  if (problem.reason.startsWith("Vision review")) {
    return "Hands and garment details weren't checked automatically. Look at them before approving.";
  }
  return `${PROBLEM[problem.name] ?? "Something needs a look."} Check it before publishing.`;
}

function notRunText(item: Item, name: string): string {
  if (inProgress(item)) return "Not checked yet.";
  if (!item.qa) return "No photo was generated, so this wasn't checked.";
  if (name === "garment_logo" && !item.has_logo) return "No logo was marked, so the logo wasn't checked.";
  return "Skipped because another check had already failed.";
}

function CheckRow({ name, label, gate, item }: { name: string; label: string; gate?: Gate; item: Item }) {
  const [open, setOpen] = useState(false);
  const word = !gate ? "Not run" : gate.status === "pass" ? "Pass" : gate.status === "review" ? "Check" : "Fail";
  const Icon = !gate ? Minus : gate.status === "pass" ? Check : gate.status === "review" ? CircleAlert : X;
  const result = (
    <>
      <Icon size={14} aria-hidden strokeWidth={2.4} /> {word}
    </>
  );
  const noHands = gate?.name === "hands" && gate.reason.startsWith("No hands");
  // A check with no score failed for a specific reason, so state that reason directly.
  const useReason = !!gate && (noHands || (gate.score === null && !gate.reason.startsWith("Vision review")));
  const plain = !gate ? notRunText(item, name) : useReason ? gate.reason : RESULT[name]?.[gate.status] ?? gate.reason;
  return (
    <li className={`slip-row ${gate?.status ?? "skipped"}`}>
      <button onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="slip-check">{label}</span>
        <span className="slip-word">{result}</span>
        <ChevronDown size={15} aria-hidden className={open ? "turned" : undefined} />
      </button>
      {open && (
        <div className="slip-detail">
          <p>{plain}</p>
          {gate && gate.reason !== plain && <p className="slip-measure">{gate.reason}</p>}
        </div>
      )}
    </li>
  );
}

/** The generated photo first, then the real product, for the full-screen viewer. */
export function itemImages(item: Item): ViewImage[] {
  const images: ViewImage[] = [];
  if (item.url) images.push({ src: item.url, alt: `Generated photo of ${item.product_name}`, caption: `${item.sku} ${item.product_name}, generated` });
  if (item.product_url) images.push({ src: item.product_url, alt: `Real product: ${item.product_name}`, caption: `${item.sku} ${item.product_name}, real product` });
  return images;
}

export function Evidence({ item, compact = false }: { item: Item; compact?: boolean }) {
  const images = itemImages(item);
  const view = (src: string) => openViewer(images, Math.max(images.findIndex((i) => i.src === src), 0));
  return (
    <div className="evidence">
      <figure>
        {item.product_url && (
          <button className="evidence-open" onClick={() => view(item.product_url!)} aria-label="View the real product large">
            <img src={item.product_url} alt={`Real product: ${item.product_name}`} />
          </button>
        )}
        <figcaption>Real product</figcaption>
      </figure>
      <figure>
        {item.url ? (
          <button className="evidence-open" onClick={() => view(item.url!)} aria-label="View the generated photo large">
            <img src={item.url} alt={`Generated photo of ${item.product_name}`} />
          </button>
        ) : (
          <span className="no-photo">No photo yet</span>
        )}
        <figcaption>
          {item.url ? (
            <button className="link-button" onClick={() => view(item.url!)}>
              {compact ? "View" : "View generated photo"}{" "}
              <span className="nowrap">
                large
                <Maximize2 size={12} aria-hidden />
              </span>
            </button>
          ) : (
            "Generated photo"
          )}
        </figcaption>
      </figure>
    </div>
  );
}

const LEARNED_ABOUT: Record<string, string> = {
  garment: "the garment",
  body: "the body",
  face: "the face",
  hands: "the hands",
  background: "the background",
  other: "the photo",
};

/** Write what is wrong. FitShot turns it into a lesson for this garment and, by default, tries again. */
function Teach({ item, generatorReady, onChange }: { item: Item; generatorReady: boolean; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [learned, setLearned] = useState<Lesson | null>(null);
  const { busy, error, run } = useAction();
  const lessons = usePolled(() => api.lessons(item.product_id), [item.product_id, learned?.id], 0);
  const forget = useAction();

  const send = (retry: boolean) =>
    run(async () => {
      const result = await api.feedback(item.id, text.trim(), retry);
      setLearned(result.lesson);
      setText("");
      setOpen(false);
      onChange();
    });

  const saved = lessons.data ?? [];
  return (
    <div className="teach">
      {!open ? (
        <button className="btn slip-outline teach-open" onClick={() => setOpen(true)}>
          <GraduationCap size={16} aria-hidden /> Tell FitShot what's wrong
        </button>
      ) : (
        <form
          className="teach-form"
          onSubmit={(event) => {
            event.preventDefault();
            void send(generatorReady);
          }}
        >
          <label className="teach-label" htmlFor={`teach-${item.id}`}>
            What's wrong with this photo?
          </label>
          <textarea
            id={`teach-${item.id}`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="For example: the sleeves should be short, and the collar is missing."
            autoFocus
          />
          <p className="slip-foot">
            Any language is fine. FitShot remembers it for {item.sku}: later photos are made with it and checked for it.
          </p>
          <ErrorNote message={error} />
          <div className="teach-actions">
            <button className="btn slip-primary" disabled={busy || text.trim().length < 3 || !generatorReady}>
              {busy ? "Learning" : "Learn and try again"}
            </button>
            <button type="button" className="btn slip-outline" disabled={busy || text.trim().length < 3} onClick={() => void send(false)}>
              Only learn
            </button>
            <button type="button" className="text-button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {learned && (
        <p className="teach-learned" role="status">
          Learned about {LEARNED_ABOUT[learned.lesson.about] ?? "the photo"}
          {learned.lesson.sleeves ? `: sleeves are ${learned.lesson.sleeves}` : ""}.
          {learned.lesson.watch ? ` The inspector will now check: ${learned.lesson.watch}` : ""}
        </p>
      )}

      {saved.length > 0 && (
        <details className="lessons">
          <summary>
            FitShot remembers {saved.length} {saved.length === 1 ? "note" : "notes"} for {item.sku}
          </summary>
          <ul>
            {saved.map((entry) => (
              <li key={entry.id}>
                <p className="lesson-text">“{entry.text}”</p>
                <p className="lesson-use">
                  {entry.lesson.sleeves && <>Sleeves: {entry.lesson.sleeves}. </>}
                  {entry.lesson.fix && <>Makes it: {entry.lesson.fix} </>}
                  {entry.lesson.watch && <>Checks: {entry.lesson.watch}</>}
                </p>
                <button
                  className="text-button"
                  disabled={forget.busy}
                  onClick={() => void forget.run(() => api.forgetLesson(entry.id)).then((ok) => { if (ok) void lessons.refresh(); })}
                >
                  Forget this
                </button>
              </li>
            ))}
          </ul>
          <ErrorNote message={forget.error} />
        </details>
      )}
    </div>
  );
}

interface SlipProps {
  item: Item;
  generators: Status["generators"];
  showEvidence: boolean;
  onChange: () => void;
  onClose?: () => void;
  /** Called after the look is deleted; defaults to onChange. */
  onDeleted?: () => void;
}

/** Delete a finished look, after a second press to confirm. */
function DeleteLook({ item, onDeleted }: { item: Item; onDeleted: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const { busy, error, run } = useAction();
  if (inProgress(item)) return null;
  return (
    <div className="delete-look">
      {confirm ? (
        <>
          <span className="small">Delete this photo for good?</span>
          <button className="btn small danger" disabled={busy} onClick={() => void run(() => api.removeItem(item.id)).then((ok) => { if (ok) onDeleted(); })}>
            <Trash2 size={14} aria-hidden /> Delete
          </button>
          <button className="btn small quiet" onClick={() => setConfirm(false)}>Keep</button>
        </>
      ) : (
        <button className="text-button" onClick={() => setConfirm(true)}>
          <Trash2 size={13} aria-hidden /> Delete photo
        </button>
      )}
      <ErrorNote message={error} />
    </div>
  );
}

export function Slip({ item, generators, showEvidence, onChange, onClose, onDeleted }: SlipProps) {
  const { busy, error, run } = useAction();
  const gates = new Map(inProgress(item) ? [] : item.qa?.gates.map((g) => [g.name, g]));
  const canDecide = item.status === "review";
  const canUndo = item.status === "approved" || item.status === "rejected";
  const canRetry = ["review", "rejected", "failed"].includes(item.status);
  const generatorReady = generators[item.generator]?.ready ?? false;
  const stampTone = item.status === "passed" || item.status === "approved" ? "good" : item.status === "review" ? "warn" : item.status === "failed" || item.status === "rejected" ? "bad" : "idle";

  const act = (action: () => Promise<unknown>) => run(action).then((ok) => ok && onChange());
  const retryButton = canRetry && (
    <button
      className="btn slip-outline"
      disabled={busy || !generatorReady}
      title={generatorReady ? undefined : "Start the image generator to retry"}
      onClick={() => act(() => api.retry(item.id))}
    >
      <RotateCcw size={15} aria-hidden /> Retry
    </button>
  );

  return (
    <section className="slip" aria-label={`Inspection for ${item.sku}`}>
      <div className="slip-head">
        <h2>Inspection</h2>
        {onClose && (
          <button className="icon-btn" onClick={onClose} aria-label="Close inspection slip">
            <X size={18} />
          </button>
        )}
      </div>
      <div className="slip-cover">
        <p className="slip-id">
          <b>{item.sku}</b> {words(item.pose)}
        </p>
        <Burst key={item.status} tone={stampTone} className="stamp">
          {ITEM_LABEL[item.status]}
        </Burst>
      </div>
      <p className="slip-summary">{summary(item)}</p>
      {item.status === "review" && item.error && <ErrorNote message={item.error} />}

      {showEvidence && <Evidence item={item} compact />}

      <ul className="slip-rows">
        {CHECKS.map(([name, label]) => (
          <CheckRow key={name} name={name} label={label} gate={gates.get(name)} item={item} />
        ))}
      </ul>

      <ErrorNote message={error} />

      {(canDecide || canRetry || canUndo) && (
        <div className="slip-actions">
          {canDecide && (
            <button className="btn slip-primary" disabled={busy} onClick={() => act(() => api.decide(item.id, "approve"))}>
              <Check size={16} aria-hidden /> Approve photo
            </button>
          )}
          <div className="slip-secondary">
            {canUndo && (
              <button className="btn slip-outline" disabled={busy} onClick={() => act(() => api.reopen(item.id))}>
                <Undo2 size={15} aria-hidden /> {item.status === "approved" ? "Undo approval" : "Undo rejection"}
              </button>
            )}
            {retryButton}
            {canDecide && (
              <button className="btn slip-outline" disabled={busy} onClick={() => act(() => api.decide(item.id, "reject"))}>
                <X size={15} aria-hidden /> Reject
              </button>
            )}
          </div>
        </div>
      )}

      {!inProgress(item) && item.url && <Teach item={item} generatorReady={generatorReady} onChange={onChange} />}
      <DeleteLook item={item} onDeleted={onDeleted ?? onChange} />

      <p className="slip-foot">
        {canRetry && !generatorReady && "Retry needs the image generator running. "}
        {item.attempts > 0 && `${item.attempts} ${item.attempts === 1 ? "attempt" : "attempts"}, $${item.usd.toFixed(3)}. `}
        Check limits are still being tuned, so use your own eye too.
      </p>
    </section>
  );
}

interface DockProps {
  item?: Item;
  open: boolean;
  generators: Status["generators"];
  evidenceInPage?: boolean;
  onChange: () => void;
  onClose: () => void;
}

/** Docked beside the work on wide screens, a real modal dialog on narrow ones. */
export function SlipDock({ item, open, generators, evidenceInPage = false, onChange, onClose }: DockProps) {
  const narrow = useMediaQuery("(max-width: 1040px)");
  const dialog = useRef<HTMLDialogElement>(null);
  const hasItem = !!item;

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open, narrow, hasItem]);

  if (!item) return null;
  if (!narrow) {
    return (
      <aside className="slip-dock">
        <Slip key={item.id} item={item} generators={generators} showEvidence={!evidenceInPage} onChange={onChange} />
      </aside>
    );
  }
  return (
    <dialog ref={dialog} className="slip-dialog" onClose={onClose} aria-label={`Inspection for ${item.sku}`}>
      {/* The dialog covers the page, so it must always show the photos being judged. */}
      {open && <Slip key={item.id} item={item} generators={generators} showEvidence onChange={onChange} onClose={onClose} />}
    </dialog>
  );
}
