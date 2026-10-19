import { useEffect, useRef, useState } from "react";

interface ImageViewerProps {
  src: string;
  alt: string;
  artifactId: string;
  onClose(): void;
  onImageError(): void;
}

export default function ImageViewer({
  src, alt, artifactId, onClose, onImageError,
}: ImageViewerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [zoom, setZoom] = useState(100);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="image-viewer"
      aria-labelledby="image-viewer-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="image-viewer-header">
        <div>
          <p className="eyebrow">Synthetic evidence</p>
          <h2 id="image-viewer-title">Image viewer</h2>
          <p className="muted">{artifactId}</p>
        </div>
        <button type="button" className="viewer-close" onClick={onClose} autoFocus>
          Close
        </button>
      </div>
      <div className="viewer-controls" aria-label="Image zoom controls">
        <button type="button" onClick={() => setZoom((value) => Math.max(100, value - 25))}
          disabled={zoom === 100}>
          Zoom out
        </button>
        <span aria-live="polite">{zoom}%</span>
        <button type="button" onClick={() => setZoom((value) => Math.min(400, value + 25))}
          disabled={zoom === 400}>
          Zoom in
        </button>
        <button type="button" onClick={() => setZoom(100)} disabled={zoom === 100}>
          Reset
        </button>
      </div>
      <div className="viewer-viewport">
        <img
          src={src}
          alt={alt}
          style={{ width: `${zoom}%` }}
          onError={onImageError}
        />
      </div>
    </dialog>
  );
}
