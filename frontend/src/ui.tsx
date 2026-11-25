import { Ban, Check, CircleAlert, Clock, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Item, ItemStatus } from "./api";
import { Burst } from "./marks";

export const ITEM_LABEL: Record<ItemStatus, string> = {
  queued: "Queued",
  running: "Checking",
  passed: "Verified",
  review: "Needs your check",
  approved: "Approved by you",
  rejected: "Rejected",
  failed: "Failed",
};

const ITEM_TONE: Record<ItemStatus, string> = {
  queued: "idle",
  running: "idle",
  passed: "pass",
  review: "check",
  approved: "pass",
  rejected: "fail",
  failed: "fail",
};

const ITEM_ICON: Record<ItemStatus, typeof Check> = {
  queued: Clock,
  running: LoaderCircle,
  passed: Check,
  review: CircleAlert,
  approved: Check,
  rejected: Ban,
  failed: X,
};

export function ItemStatusLabel({ status }: { status: ItemStatus }) {
  const Icon = ITEM_ICON[status];
  return (
    <span className={`status ${ITEM_TONE[status]}`}>
      <Icon size={14} aria-hidden className={status === "running" ? "spin" : undefined} />
      {ITEM_LABEL[status]}
    </span>
  );
}

export const words = (value: string) => {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export const money = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "Not yet";
  return `$${value.toFixed(value !== 0 && value < 10 ? 3 : 2)}`;
};

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export function useHashRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const change = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return route;
}

export function usePolled<T>(load: () => Promise<T>, deps: unknown[], interval = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stable = useCallback(load, deps);

  const refresh = useCallback(async () => {
    const ticket = ++latest.current;
    try {
      const value = await stable();
      if (ticket === latest.current) {
        setData(value);
        setError(null);
      }
    } catch (err) {
      if (ticket === latest.current) setError((err as Error).message);
    }
  }, [stable]);

  useEffect(() => {
    setData(null);
    void refresh();
    if (!interval) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, interval);
    return () => window.clearInterval(timer);
  }, [refresh, interval]);

  return { data, error, refresh };
}

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const change = () => setMatches(media.matches);
    change();
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, [query]);
  return matches;
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run, clear: () => setError(null) };
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="note error" role="alert">
      <TriangleAlert size={16} aria-hidden />
      <span>{message}</span>
    </p>
  );
}

export function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {help && <span className="field-help">{help}</span>}
    </label>
  );
}

export function GridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="photo-grid" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div className="tile skeleton" key={i} />
      ))}
    </div>
  );
}

export function PhotoTile({ item, selected, onSelect }: { item: Item; selected: boolean; onSelect: () => void }) {
  return (
    <button className={`tile${selected ? " selected" : ""}`} onClick={onSelect} aria-pressed={selected}>
      <span className="tile-photo">
        {item.url ? (
          <img src={item.url} alt={`${item.product_name}, ${words(item.pose)}`} loading="lazy" />
        ) : item.shot_url && (item.status === "queued" || item.status === "running") ? (
          <img className="waiting" src={item.shot_url} alt="" loading="lazy" />
        ) : (
          <span className="no-photo">No photo</span>
        )}
      </span>
      <span className="tile-cap">
        <span className="tile-name">
          <b>{item.sku}</b> {words(item.pose)}
        </span>
        <ItemStatusLabel status={item.status} />
      </span>
    </button>
  );
}

const GENERATOR_LABELS: Record<string, string> = {
  fashn: "FASHN VTON 1.5 (this PC)",
  fashn_hosted: "FASHN VTON 1.5 (Hugging Face)",
  nano_banana: "Nano Banana (Gemini)",
  comfyui: "ComfyUI (person photos)",
  catvton: "CatVTON",
};

export const generatorLabel = (name: string) => GENERATOR_LABELS[name] ?? words(name);

/** A cover-line page title. */
export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="title">{children}</h1>;
}

/** An empty state: a cover burst, a headline, one sentence and one next step. */
export function Empty({
  mark,
  title,
  children,
  action,
  level = 2,
}: {
  mark: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className={`empty${level === 3 ? " compact" : ""}`}>
      <Burst tone="volt" className="empty-burst">{mark}</Burst>
      <div className="empty-body">
        <Heading>{title}</Heading>
        {children}
        {action && <div className="empty-action">{action}</div>}
      </div>
    </div>
  );
}
