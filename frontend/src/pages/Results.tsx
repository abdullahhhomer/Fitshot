import { Download, Maximize2, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { api, type Item, type Status } from "../api";
import { retryFlow } from "../flow";
import { Slip } from "../Slip";
import { Empty, ErrorNote, GridSkeleton, PageTitle, PhotoTile, generatorLabel, shortDate, usePolled, words } from "../ui";
import { openViewer } from "../Viewer";

const DECISIONS: [string, string, (i: Item) => boolean][] = [
  ["all", "All", () => true],
  ["ready", "Verified or approved", (i) => i.status === "passed" || i.status === "approved"],
  ["check", "Needs your check", (i) => i.status === "review"],
  ["rejected", "Rejected or failed", (i) => i.status === "rejected" || i.status === "failed"],
];

function Detail({ item, status, onChange }: { item: Item; status: Status; onChange: () => void }) {
  const images = [
    ...(item.url ? [{ src: item.url, alt: `${item.person_name} wearing ${item.product_name}`, caption: `${item.sku} ${item.product_name}, ${generatorLabel(item.generator)}` }] : []),
    ...(item.shot_url ? [{ src: item.shot_url, alt: `Original photo of ${item.person_name}`, caption: "Original photo" }] : []),
  ];
  const settings = Object.entries(item.settings ?? {});
  return (
    <aside className="result-detail" aria-label={`Result ${item.sku}`}>
      <div className="compare-pair">
        <figure>
          <span className="compare-photo-frame">{item.shot_url && <img src={item.shot_url} alt={`Original photo of ${item.person_name}`} />}</span>
          <figcaption>Before</figcaption>
        </figure>
        <figure>
          <span className="compare-photo-frame">
            {item.url ? (
              <button type="button" className="stage-open" onClick={() => openViewer(images)} aria-label="View the result large">
                <img src={item.url} alt={`${item.person_name} wearing ${item.product_name}`} />
              </button>
            ) : (
              <span className="no-photo">No photo</span>
            )}
          </span>
          <figcaption>After</figcaption>
        </figure>
      </div>
      <dl className="summary">
        <div><dt>Person</dt><dd>{item.person_name} ({item.person_kind === "self" ? "live photo" : "built-in"}{item.framing ? `, ${item.framing} body` : ""})</dd></div>
        <div><dt>Garment</dt><dd>{item.sku} {item.product_name}</dd></div>
        <div><dt>AI model</dt><dd>{generatorLabel(item.generator)}</dd></div>
        <div><dt>Settings</dt><dd>{settings.length ? settings.map(([k, v]) => `${words(k)} ${v}`).join(", ") : "Model defaults"}</dd></div>
        <div><dt>Made</dt><dd>{item.created_at ? shortDate(item.created_at) : "-"}</dd></div>
      </dl>
      <div className="result-actions">
        {item.url && (
          <>
            <button type="button" className="btn small" onClick={() => openViewer(images)}><Maximize2 size={14} aria-hidden /> View large</button>
            <a className="btn small" href={item.url} download={`${item.sku}-${item.generator}.png`}><Download size={14} aria-hidden /> Download</a>
          </>
        )}
        <button type="button" className="btn small quiet" onClick={() => retryFlow(item)}><RotateCcw size={14} aria-hidden /> Try again in the Fitting room</button>
      </div>
      <Slip key={item.id} item={item} generators={status.generators} showEvidence={false} onChange={onChange} />
    </aside>
  );
}

export function Results({ status }: { status: Status }) {
  const results = usePolled(api.results, [], 5000);
  const [decision, setDecision] = useState("all");
  const [model, setModel] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const all = results.data ?? [];
  const models = useMemo(() => [...new Set(all.map((i) => i.generator))], [all]);
  const test = DECISIONS.find(([id]) => id === decision)?.[2] ?? (() => true);
  const shown = all.filter((i) => test(i) && (model === "all" || i.generator === model));
  const selected = all.find((i) => i.id === selectedId) ?? shown[0];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>Results</PageTitle>
          <p>Every try-on, newest first, with the person, garment, model and settings it was made with.</p>
        </div>
        <a className="btn primary" href="#/studio">New try-on</a>
      </div>
      <ErrorNote message={results.error} />
      {!results.data ? (
        <GridSkeleton />
      ) : !all.length ? (
        <Empty mark="Go" title="No try-ons yet" action={<a className="btn primary" href="#/studio">Open the Fitting room</a>}>
          <p>Results appear here as soon as you generate a try-on, and every one is kept.</p>
        </Empty>
      ) : (
        <div className="results-layout">
          <div>
            <div className="tabs" role="group" aria-label="Decision">
              {DECISIONS.map(([id, label, check]) => (
                <button key={id} aria-pressed={decision === id} onClick={() => setDecision(id)}>
                  {label} <span className="tab-count">{all.filter(check).length}</span>
                </button>
              ))}
            </div>
            {models.length > 1 && (
              <div className="tabs compact" role="group" aria-label="AI model">
                <button aria-pressed={model === "all"} onClick={() => setModel("all")}>Every model</button>
                {models.map((m) => (
                  <button key={m} aria-pressed={model === m} onClick={() => setModel(m)}>{generatorLabel(m)}</button>
                ))}
              </div>
            )}
            {shown.length ? (
              <div className="photo-grid">
                {shown.map((item) => (
                  <PhotoTile key={item.id} item={item} selected={item.id === selected?.id} onSelect={() => setSelectedId(item.id)} />
                ))}
              </div>
            ) : (
              <p className="muted">Nothing matches these filters.</p>
            )}
          </div>
          {selected && <Detail item={selected} status={status} onChange={() => void results.refresh()} />}
        </div>
      )}
    </div>
  );
}
