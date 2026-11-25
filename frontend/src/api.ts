export type GateStatus = "pass" | "review" | "fail";
export type ItemStatus = "queued" | "running" | "passed" | "review" | "approved" | "rejected" | "failed";

export interface Status {
  generators: Record<string, { ready: boolean; detail: string; dresses: boolean }>;
  judge_ready: boolean;
  default_generator: string;
  max_attempts: number;
  scenes: string[];
  poses: string[];
  categories: string[];
}

export interface BrandModel {
  id: string;
  name: string;
  url: string;
  created_at: string;
  approved_shots: Record<string, number>;
  kind: "brand" | "self";
}

export interface Shot {
  id: string;
  model_id: string;
  scene: string;
  pose: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  url: string;
  qa: { identity: { status: GateStatus; score: number | null; reason: string } } | null;
}

export interface LogoBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  created_at: string;
  url: string;
  back_url: string | null;
  logo_box: LogoBox | null;
  photo_type: "flat-lay" | "model" | null;
}

/** A setting a try-on model accepts, as declared by its adapter. */
export interface ModelSetting {
  key: string;
  label: string;
  minimum: number;
  maximum: number;
  step: number;
  default: number;
  help: string;
}

export type AiModelStatus = "not added" | "downloading" | "ready" | "unavailable" | "error";

/** An AI try-on model from the registry (not a person and not a photo). */
export interface AiModel {
  id: string;
  name: string;
  version: string;
  description: string;
  categories: string[];
  person_modes: string[];
  photo_types: string[];
  hardware: string;
  limitations: string;
  location: "local" | "online";
  license: string;
  default_path: string | null;
  size_gb: number;
  download: boolean;
  setup_hint: string;
  settings: ModelSetting[];
  supported: boolean;
  added: boolean;
  status: AiModelStatus;
  detail: string;
  progress?: number | null;
  is_default: boolean;
  validated: boolean;
  available?: boolean;
  path: string | null;
}

/** A person photo to dress: a built-in brand-model photo or a live upload. */
export interface Person {
  shot_id: string;
  model_id: string;
  name: string;
  kind: "brand" | "self";
  url: string;
  scene: string;
  pose: string;
  framing: "full" | "half";
  fits: string[];
  created_at: string;
}

export interface Gate {
  name: string;
  status: GateStatus;
  score: number | null;
  reason: string;
  hint: string;
}

export interface QA {
  status: GateStatus;
  gates: Gate[];
  calibrated: boolean;
  attempt: number;
  face_restored: boolean;
}

export interface Item {
  id: string;
  job_id: string;
  product_id: string;
  shot_id: string;
  status: ItemStatus;
  attempts: number;
  error: string | null;
  updated_at: string;
  not_before?: string | null;
  url: string | null;
  qa: QA | null;
  sku: string;
  product_name: string;
  product_url: string | null;
  pose: string;
  shot_url: string | null;
  generator: string;
  scene: string;
  has_logo: boolean;
  usd: number;
  settings: Record<string, number | string>;
  model_id: string | null;
  person_name: string | null;
  person_kind: "brand" | "self" | null;
  framing: "full" | "half" | null;
  created_at: string | null;
}

export interface Job {
  id: string;
  kind: "single" | "bulk";
  model_id: string;
  scene: string;
  generator: string;
  created_at: string;
  counts: Partial<Record<ItemStatus, number>>;
  total: number;
  accepted: number;
  done: boolean;
  usd: number;
  usd_per_accepted: number | null;
}

export interface JobDetail extends Job {
  items: Item[];
}

export interface Costs {
  total_usd: number;
  accepted_images: number;
  usd_per_accepted: number | null;
  products: number;
  usd_per_product: number | null;
  by_operation: { operation: string; calls: number; usd: number }[];
  by_product: { id: string; sku: string; name: string; accepted: number; usd: number }[];
  photoshoot_reference: { low: number; high: number; source: string };
}

function errorText(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? fallback).join(" ");
  }
  return fallback;
}

/** Empty when the server also serves this app; set VITE_API_BASE when the app is hosted elsewhere. */
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const KEY_STORE = "fitshot-access-key";
export const LOCKED_EVENT = "fitshot:locked";

export function accessKey(): string {
  try {
    return localStorage.getItem(KEY_STORE) ?? "";
  } catch {
    return "";
  }
}

export function setAccessKey(key: string) {
  try {
    if (key) localStorage.setItem(KEY_STORE, key);
    else localStorage.removeItem(KEY_STORE);
  } catch {
    /* Without storage the key lasts until the page reloads. */
  }
}

/** A server URL for links and images, which cannot send headers, so the key rides along. */
export function apiUrl(path: string): string {
  const url = BASE + path;
  const key = accessKey();
  return key ? `${url}${url.includes("?") ? "&" : "?"}key=${encodeURIComponent(key)}` : url;
}

function withMedia<T>(value: T): T {
  if (typeof value === "string") return (value.startsWith("/media/") ? apiUrl(value) : value) as T;
  if (Array.isArray(value)) return value.map(withMedia) as T;
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, withMedia(v)])) as T;
  }
  return value;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const key = accessKey();
  if (key) headers.set("X-FitShot-Key", key);
  let response: Response;
  try {
    response = await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new Error("FitShot's server isn't responding. Check that it is running, then try again.");
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event(LOCKED_EVENT));
    throw new Error("This FitShot is private. Enter its access key.");
  }
  if (!response.ok) {
    const fallback = `The request failed (${response.status}).`;
    const body = await response.json().catch(() => null);
    throw new Error(errorText(body?.detail, fallback));
  }
  if (response.status === 204) return undefined as T;
  return withMedia(await response.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface Lesson {
  id: string;
  text: string;
  generator: string;
  created_at: string;
  lesson: {
    sleeves: "none" | "short" | "elbow" | "long" | null;
    fix: string;
    watch: string;
    about: string;
    learned_by: "gemini" | "as written";
  };
}

export const api = {
  status: () => request<Status>("/api/status"),
  models: () => request<BrandModel[]>("/api/models"),
  createModel: (form: FormData) => request<BrandModel>("/api/models", { method: "POST", body: form }),
  createSelfie: (form: FormData) => request<BrandModel>("/api/selfies", { method: "POST", body: form }),
  removeSelfie: (id: string) => request<void>(`/api/models/${id}`, { method: "DELETE" }),
  shots: (id: string) => request<Shot[]>(`/api/models/${id}/shots`),
  generateShot: (id: string, body: { scene: string; pose: string; generator: string }) =>
    request<Shot>(`/api/models/${id}/shots`, json("POST", body)),
  uploadShot: (id: string, form: FormData) =>
    request<Shot>(`/api/models/${id}/shots/upload`, { method: "POST", body: form }),
  decideShot: (id: string, status: "approved" | "rejected") =>
    request<Shot>(`/api/shots/${id}`, json("PATCH", { status })),
  products: () => request<Product[]>("/api/products"),
  createProduct: (form: FormData) => request<Product>("/api/products", { method: "POST", body: form }),
  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  startJob: (body: {
    product_ids: string[];
    model_id: string;
    scene: string;
    generator: string;
    num_images: number;
    shot_id?: string;
    settings?: Record<string, number | string>;
  }) =>
    request<Job>("/api/jobs", json("POST", body)),
  startBulk: (form: FormData) => request<Job>("/api/jobs/bulk", { method: "POST", body: form }),
  review: () => request<Item[]>("/api/review"),
  looks: (modelId: string, scene?: string) =>
    request<Item[]>(`/api/looks?model_id=${encodeURIComponent(modelId)}${scene ? `&scene=${encodeURIComponent(scene)}` : ""}`),
  decide: (id: string, decision: "approve" | "reject") =>
    request<Item>(`/api/items/${id}/review`, json("POST", { decision })),
  retry: (id: string) => request<Item>(`/api/items/${id}/retry`, { method: "POST" }),
  removeItem: (id: string) => request<void>(`/api/items/${id}`, { method: "DELETE" }),
  aiModels: () => request<{ added: AiModel[]; catalog: AiModel[] }>("/api/ai-models"),
  addAiModel: (body: { id: string; path?: string; download?: boolean }) => request<AiModel>("/api/ai-models", json("POST", body)),
  validateAiModel: (id: string) => request<AiModel>(`/api/ai-models/${id}/validate`, { method: "POST" }),
  defaultAiModel: (id: string) => request<AiModel>(`/api/ai-models/${id}/default`, { method: "POST" }),
  aiModelFiles: (id: string) => request<{ path: string; bytes: number }[]>(`/api/ai-models/${id}/files`),
  removeAiModel: (id: string, deleteFiles: boolean) =>
    request<{ deleted: string[] }>(`/api/ai-models/${id}?delete_files=${deleteFiles}`, { method: "DELETE" }),
  people: () => request<Person[]>("/api/people"),
  livePhotos: () => request<Person[]>("/api/live-photos"),
  results: () => request<Item[]>("/api/results"),
  reopen: (id: string) => request<Item>(`/api/items/${id}/reopen`, { method: "POST" }),
  costs: () => request<Costs>("/api/costs"),
  feedback: (id: string, text: string, retry: boolean) =>
    request<{ item: Item; lesson: Lesson }>(`/api/items/${id}/feedback`, json("POST", { text, retry })),
  lessons: (productId: string) => request<Lesson[]>(`/api/products/${productId}/lessons`),
  forgetLesson: (id: string) => request<void>(`/api/lessons/${id}`, { method: "DELETE" }),
};
