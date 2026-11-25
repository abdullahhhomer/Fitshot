import { ChevronLeft, ChevronRight, Download, ExternalLink, Maximize2, Minimize2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface ViewImage {
  src: string;
  alt: string;
  caption: string;
}

const OPEN_EVENT = "fitshot:view";

/** Open the full-screen viewer from anywhere: a set of photos and which one to show first. */
export function openViewer(images: ViewImage[], index = 0) {
  if (images.length) window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { images, index } }));
}

const fileName = (caption: string, src: string) => {
  const ext = src.split("?")[0].split(".").pop() || "png";
  return `${caption.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "fitshot"}.${ext}`;
};

/** One viewer for the whole app, mounted once in the shell. */
export function ViewerHost() {
  const dialog = useRef<HTMLDialogElement>(null);
  const [images, setImages] = useState<ViewImage[]>([]);
  const [index, setIndex] = useState(0);
  const [actual, setActual] = useState(false);

  useEffect(() => {
    const open = (event: Event) => {
      const { images: next, index: start } = (event as CustomEvent<{ images: ViewImage[]; index: number }>).detail;
      setImages(next);
      setIndex(Math.min(Math.max(start, 0), next.length - 1));
      setActual(false);
    };
    window.addEventListener(OPEN_EVENT, open);
    return () => window.removeEventListener(OPEN_EVENT, open);
  }, []);

  useEffect(() => {
    const element = dialog.current;
    if (images.length && element && !element.open) element.showModal();
  }, [images]);

  const count = images.length;
  const step = (by: number) => {
    setIndex((i) => (i + by + count) % count);
    setActual(false);
  };
  const close = () => dialog.current?.close();
  const image = images[index];

  return (
    <dialog
      ref={dialog}
      className="viewer"
      aria-label={image ? `Photo: ${image.caption}` : "Photo viewer"}
      onClose={() => setImages([])}
      onKeyDown={(event) => {
        if (count > 1 && event.key === "ArrowRight") step(1);
        if (count > 1 && event.key === "ArrowLeft") step(-1);
      }}
    >
      {image && (
        <>
          <div className="viewer-bar">
            <p className="viewer-caption">
              {image.caption}
              {count > 1 && <span className="viewer-count"> {index + 1} of {count}</span>}
            </p>
            <div className="viewer-tools">
              <button className="viewer-btn" onClick={() => setActual(!actual)} aria-pressed={actual}>
                {actual ? <Minimize2 size={17} aria-hidden /> : <Maximize2 size={17} aria-hidden />}
                <span>{actual ? "Fit to screen" : "Actual size"}</span>
              </button>
              <a className="viewer-btn" href={image.src} target="_blank" rel="noreferrer">
                <ExternalLink size={17} aria-hidden />
                <span>Open on its own</span>
              </a>
              <a className="viewer-btn" href={image.src} download={fileName(image.caption, image.src)}>
                <Download size={17} aria-hidden />
                <span>Download</span>
              </a>
              <button className="viewer-btn icon" onClick={close} aria-label="Close viewer" autoFocus>
                <X size={20} />
              </button>
            </div>
          </div>
          <div className={`viewer-stage${actual ? " actual" : ""}`}>
            <img src={image.src} alt={image.alt} onClick={() => setActual(!actual)} />
            {count > 1 && (
              <>
                <button className="viewer-nav prev" onClick={() => step(-1)} aria-label="Previous photo">
                  <ChevronLeft size={26} />
                </button>
                <button className="viewer-nav next" onClick={() => step(1)} aria-label="Next photo">
                  <ChevronRight size={26} />
                </button>
              </>
            )}
          </div>
        </>
      )}
    </dialog>
  );
}
