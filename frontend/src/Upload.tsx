import { Camera, ImagePlus, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CameraCapture } from "./Camera";

export function usePreview(file: File | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return url;
}

interface DropZoneProps {
  file: File | null;
  onFile: (file: File | null) => void;
  title: string;
  hint: string;
  /** Offer the camera too, framed for a face or a body. */
  camera?: "face" | "body";
}

/** Drag a photo in, choose one, or take one; then preview, replace or remove it. */
export function DropZone({ file, onFile, title, hint, camera }: DropZoneProps) {
  const [over, setOver] = useState(false);
  const [shooting, setShooting] = useState(false);
  const [wrongType, setWrongType] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const preview = usePreview(file);

  const take = (picked: File | undefined | null) => {
    if (!picked) return;
    if (!picked.type.startsWith("image/")) {
      setWrongType(true);
      return;
    }
    setWrongType(false);
    onFile(picked);
  };

  if (shooting && camera) {
    return (
      <CameraCapture
        mode={camera}
        onCapture={(photo) => {
          take(photo);
          setShooting(false);
        }}
        onClose={() => setShooting(false)}
      />
    );
  }

  return (
    <div
      className={`dropzone${over ? " over" : ""}${file ? " filled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        take(event.dataTransfer.files?.[0]);
      }}
    >
      <div className="dropzone-image">
        {preview ? <img src={preview} alt={`${title}, preview`} /> : <ImagePlus size={28} aria-hidden />}
      </div>
      <div className="dropzone-text">
        <p className="dropzone-title">{file ? "Photo added" : title}</p>
        <p className="field-help">{file ? `${file.name}. Drop another photo here to replace it.` : hint}</p>
        {wrongType && (
          <p className="note error" role="alert">
            That file is not an image. Use a JPG, PNG or WebP photo.
          </p>
        )}
        <div className="dropzone-actions">
          <button type="button" className="btn small" onClick={() => input.current?.click()}>
            <Upload size={14} aria-hidden /> {file ? "Replace" : "Choose a photo"}
          </button>
          {camera && (
            <button type="button" className="btn small quiet" onClick={() => setShooting(true)}>
              <Camera size={14} aria-hidden /> Take a photo
            </button>
          )}
          {file && (
            <button type="button" className="btn small quiet" onClick={() => onFile(null)}>
              <X size={14} aria-hidden /> Remove
            </button>
          )}
        </div>
      </div>
      <input
        ref={input}
        className="visually-hidden"
        type="file"
        accept="image/*"
        tabIndex={-1}
        aria-label={title}
        onChange={(event) => {
          take(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </div>
  );
}
