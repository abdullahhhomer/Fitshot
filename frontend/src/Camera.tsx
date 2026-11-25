import { Camera, Timer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** A face close-up needs less time to settle than stepping back for a body photo. */
const TIMER_SECONDS = { face: 3, body: 5 };
/** Portrait 3:4, the shape every try-on is made at. */
const ASPECT = 3 / 4;

function cameraError(err: unknown) {
  const name = (err as DOMException)?.name;
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera access is blocked. Allow the camera for this site from the address bar, or choose a photo instead.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No camera was found. Choose a photo instead.";
  if (name === "NotReadableError") return "Another app is using the camera. Close it and try again, or choose a photo instead.";
  return "The camera could not start. Choose a photo instead.";
}

/**
 * Live camera with a body outline to frame against. Takes the photo after a short timer, so
 * the person can step back until their head and hips are in the outline.
 */
export function CameraCapture({
  mode = "body",
  onCapture,
  onClose,
}: {
  mode?: "face" | "body";
  onCapture: (photo: File) => void;
  onClose: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [live, setLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("The camera only opens on a secure address: https, or this computer at 127.0.0.1. Choose a photo instead.");
      return;
    }
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ audio: false, video: { facingMode: "user", width: { ideal: 1920 }, height: { ideal: 1080 } } })
      .then((media) => {
        if (cancelled) return media.getTracks().forEach((t) => t.stop());
        stream.current = media;
        if (video.current) {
          video.current.srcObject = media;
          void video.current.play().catch(() => undefined);
        }
      })
      .catch((err) => !cancelled && setError(cameraError(err)));
    return () => {
      cancelled = true;
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = null;
    };
  }, []);

  const snap = () => {
    const v = video.current;
    if (!v?.videoWidth) return;
    // The same centred 3:4 area the frame shows, mirrored like the preview the person framed with.
    const width = Math.min(v.videoWidth, Math.round(v.videoHeight * ASPECT));
    const height = Math.min(v.videoHeight, Math.round(v.videoWidth / ASPECT));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(v, (v.videoWidth - width) / 2, (v.videoHeight - height) / 2, width, height, 0, 0, width, height);
    canvas.toBlob(
      (blob) => blob && onCapture(new File([blob], `${mode}-${Date.now()}.jpg`, { type: "image/jpeg" })),
      "image/jpeg",
      0.92,
    );
  };

  useEffect(() => {
    if (count === null) return;
    if (count === 0) {
      setCount(null);
      snap();
      return;
    }
    const tick = window.setTimeout(() => setCount(count - 1), 1000);
    return () => window.clearTimeout(tick);
  }, [count]);

  if (error) {
    return (
      <div className="camera camera-off">
        <p className="note error" role="alert">{error}</p>
        <button type="button" className="btn small quiet" onClick={onClose}>Close camera</button>
      </div>
    );
  }

  return (
    <div className="camera">
      <div className="camera-frame">
        <video ref={video} muted playsInline onLoadedData={() => setLive(true)} aria-label="Live camera view" />
        <svg className="camera-guide" viewBox="0 0 300 400" aria-hidden>
          {mode === "face" ? (
            <path d="M150 64a74 94 0 1 1 0 188a74 94 0 1 1 0-188ZM10 400c12-62 70-96 140-100c70 4 128 38 140 100" />
          ) : (
            <path d="M150 34a34 40 0 1 1 0 80a34 40 0 1 1 0-80ZM118 124c-12 4-50 10-62 26c-8 12-12 70-14 112M182 124c12 4 50 10 62 26c8 12 12 70 14 112M84 168l4 160h124l4-160" />
          )}
        </svg>
        {!live && <span className="camera-wait">Opening the camera</span>}
        {count !== null && <span className="camera-count">{count}</span>}
      </div>
      <p className="field-help" aria-live="polite">
        {count !== null
          ? `Taking the photo in ${count}. Step back and stand still.`
          : mode === "face"
            ? "Bring your face into the oval and look at the camera."
            : "Stand back until your body fits the outline: head to hips, or your whole body."}
      </p>
      <div className="camera-actions">
        {count === null ? (
          <>
            <button type="button" className="btn primary" disabled={!live} onClick={() => setCount(TIMER_SECONDS[mode])}>
              <Timer size={16} aria-hidden /> Take photo in {TIMER_SECONDS[mode]} s
            </button>
            <button type="button" className="btn quiet" disabled={!live} onClick={snap}>
              <Camera size={16} aria-hidden /> Take it now
            </button>
          </>
        ) : (
          <button type="button" className="btn quiet" onClick={() => setCount(null)}>Stop the timer</button>
        )}
        <button type="button" className="icon-btn plain" onClick={onClose} aria-label="Close camera">
          <X size={18} />
        </button>
      </div>
    </div>
  );
}
