import type { Item, Person } from "./api";

/** Where the Fitting Room is: kept for the visit, so going back never loses a choice. */
export interface Flow {
  step: 1 | 2 | 3 | 4 | 5; // 5 is the result
  source: "live" | "builtin";
  liveMode: "full" | "half";
  person: Person | null;
  productId: string | null;
  photoType: "flat-lay" | "model" | null;
  modelId: string | null;
  settings: Record<string, number>;
  jobId: string | null;
}

export const EMPTY_FLOW: Flow = {
  step: 1,
  source: "live",
  liveMode: "full",
  person: null,
  productId: null,
  photoType: null,
  modelId: null,
  settings: {},
  jobId: null,
};

const KEY = "fitshot-flow";

export function loadFlow(): Flow {
  try {
    const saved = sessionStorage.getItem(KEY);
    return saved ? { ...EMPTY_FLOW, ...(JSON.parse(saved) as Partial<Flow>) } : EMPTY_FLOW;
  } catch {
    return EMPTY_FLOW;
  }
}

export function saveFlow(flow: Flow) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(flow));
  } catch {
    /* The flow still works for this page view. */
  }
}

/** Open a past result in the Fitting Room at the review step, to try again with other settings or another model. */
export function retryFlow(item: Item) {
  const numbers = Object.fromEntries(
    Object.entries(item.settings ?? {}).filter((entry): entry is [string, number] => typeof entry[1] === "number"),
  );
  saveFlow({
    ...EMPTY_FLOW,
    step: 4,
    source: item.person_kind === "self" ? "live" : "builtin",
    liveMode: item.framing === "half" ? "half" : "full",
    person: {
      shot_id: item.shot_id,
      model_id: item.model_id ?? "",
      name: item.person_name ?? "Person",
      kind: item.person_kind ?? "brand",
      url: item.shot_url ?? "",
      scene: item.scene,
      pose: item.pose,
      framing: item.framing ?? "full",
      fits: item.framing === "half" ? ["top", "outerwear"] : ["top", "outerwear", "bottom", "dress"],
      created_at: item.created_at ?? "",
    },
    productId: item.product_id,
    photoType: (item.settings?.photo_type as Flow["photoType"]) ?? null,
    modelId: item.generator,
    settings: numbers,
  });
  window.location.hash = "#/studio";
}
