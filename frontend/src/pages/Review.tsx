import { ClipboardCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Status } from "../api";
import { Evidence, SlipDock } from "../Slip";
import { Empty, ErrorNote, GridSkeleton, PageTitle, usePolled, words } from "../ui";

export function Review({ status, onChange }: { status: Status; onChange: () => void }) {
  const { data, error, refresh } = usePolled(api.review, [], 4000);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [slipOpen, setSlipOpen] = useState(false);

  useEffect(() => {
    if (!data) return;
    if (!data.some((item) => item.id === selectedId)) setSelectedId(data[0]?.id ?? null);
    if (!data.length) setSlipOpen(false);
  }, [data, selectedId]);

  const selected = data?.find((item) => item.id === selectedId);
  const changed = () => {
    void refresh();
    onChange();
  };

  return (
    <div className={`workspace${selected ? " has-slip" : ""}`}>
      <div className="page">
        <div className="page-head">
          <div>
            <PageTitle>Review</PageTitle>
            <p>{data ? (data.length ? `${data.length} ${data.length === 1 ? "photo needs" : "photos need"} your decision` : "Nothing is waiting for you") : "Loading photos"}</p>
          </div>
          {selected && (
            <button className="btn primary open-slip" onClick={() => setSlipOpen(true)}>
              <ClipboardCheck size={16} aria-hidden /> Open inspection
            </button>
          )}
        </div>
        <ErrorNote message={error} />
        {!data ? (
          <GridSkeleton />
        ) : data.length === 0 ? (
          <Empty
            mark="Clear"
            title="You're all caught up"
            action={
              <a className="btn" href="#/shoots">
                Go to photoshoots
              </a>
            }
          >
            <p>Photos that FitShot can't verify on its own will appear here for you to approve, retry or reject.</p>
          </Empty>
        ) : (
          <>
            {selected && <Evidence item={selected} />}
            <div className="queue-strip" role="group" aria-label="Photos waiting for review">
              {data.map((item) => (
                <button key={item.id} aria-pressed={item.id === selectedId} onClick={() => setSelectedId(item.id)}>
                  {item.url ? <img src={item.url} alt="" loading="lazy" /> : <span className="no-photo">None</span>}
                  <span>
                    <b>{item.sku}</b> {words(item.pose)}
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      <SlipDock item={selected} open={slipOpen} generators={status.generators} evidenceInPage onChange={changed} onClose={() => setSlipOpen(false)} />
    </div>
  );
}
