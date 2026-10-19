import { useEffect, useState } from "react";
import type { Session } from "./auth";
import type { Artifact } from "./types";
import ImageViewer from "./ImageViewer";

interface EvidenceImage {
  artifact: Artifact;
  url: string;
}

export default function EvidencePreview({
  session, claimId,
}: { session: Session; claimId: string }) {
  const [images, setImages] = useState<EvidenceImage[]>([]);
  const [unavailable, setUnavailable] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [viewerOpen, setViewerOpen] = useState(false);
  const [decodeFailures, setDecodeFailures] = useState<string[]>([]);
  const [status, setStatus] = useState("Loading evidence…");
  useEffect(() => {
    const controller = new AbortController();
    const urls: string[] = [];
    setImages([]);
    setUnavailable([]);
    setSelectedId("");
    setViewerOpen(false);
    setDecodeFailures([]);
    setStatus("Loading evidence…");
    async function load() {
      const response = await session.request(`/api/claims/${claimId}/artifacts`, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Evidence metadata could not be loaded.");
      const artifacts = await response.json() as Artifact[];
      const photos = artifacts.filter((item) => item.artifactType === "damage_photo");
      if (!photos.length) {
        setStatus("No damage photo is linked to this claim.");
        return;
      }
      const loaded: EvidenceImage[] = [];
      const failed: Artifact[] = [];
      for (const artifact of photos) {
        try {
          const content = await session.request(
            `/api/claims/${claimId}/artifacts/${artifact.artifactId}/content`,
            { signal: controller.signal },
          );
          if (!content.ok) throw new Error("Linked evidence image is unavailable.");
          const blob = await content.blob();
          if (controller.signal.aborted) return;
          const url = URL.createObjectURL(blob);
          urls.push(url);
          loaded.push({ artifact, url });
        } catch {
          if (controller.signal.aborted) return;
          failed.push(artifact);
        }
      }
      if (!controller.signal.aborted) {
        setImages(loaded);
        setUnavailable(failed);
        setSelectedId(loaded[0]?.artifact.artifactId ?? "");
        setStatus(
          failed.length
            ? `Could not load ${failed.length} of ${photos.length} damage photos.`
            : "",
        );
      }
    }
    load().catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setStatus(reason instanceof Error ? reason.message : "Evidence preview unavailable.");
      }
    });
    return () => {
      controller.abort();
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [session, claimId]);

  const visibleImages = images.filter(
    ({ artifact }) => !decodeFailures.includes(artifact.artifactId),
  );
  const selectedImage = visibleImages.find(({ artifact }) => artifact.artifactId === selectedId)
    ?? visibleImages[0];

  function markImageUnavailable(artifactId: string) {
    setDecodeFailures((failures) =>
      failures.includes(artifactId) ? failures : [...failures, artifactId]);
    setViewerOpen(false);
    setSelectedId((current) => current === artifactId
      ? visibleImages.find(({ artifact }) => artifact.artifactId !== artifactId)?.artifact.artifactId ?? ""
      : current);
  }

  return <section aria-label="Synthetic image evidence">
    <h3>Damage evidence</h3>
    <p className="muted">AI-generated synthetic evidence — not a real claimant photograph.</p>
    {status && <p role="status">{status}</p>}
    {selectedImage && (
      <div className="evidence-gallery">
        <figure className="evidence-main">
          <button
            type="button"
            className="image-open-button"
            aria-label={`Open image viewer for ${selectedImage.artifact.description ?? selectedImage.artifact.artifactId}`}
            aria-haspopup="dialog"
            onClick={() => setViewerOpen(true)}
          >
            <img
              src={selectedImage.url}
              alt={selectedImage.artifact.description ?? "Synthetic vehicle evidence"}
              onError={() => markImageUnavailable(selectedImage.artifact.artifactId)}
            />
          </button>
          <figcaption>{selectedImage.artifact.artifactId} · AI-generated synthetic evidence</figcaption>
        </figure>
        {images.length > 1 && (
          <div className="thumbnail-strip" role="group" aria-label="Damage photo thumbnails">
            {images.map(({ artifact, url }, index) => {
              const failed = decodeFailures.includes(artifact.artifactId);
              return (
                <button
                  key={artifact.artifactId}
                  type="button"
                  className={`thumbnail${selectedImage.artifact.artifactId === artifact.artifactId ? " selected" : ""}`}
                  aria-label={`View photo ${index + 1}: ${artifact.description ?? artifact.artifactId}`}
                  aria-pressed={selectedImage.artifact.artifactId === artifact.artifactId}
                  disabled={failed}
                  onClick={() => setSelectedId(artifact.artifactId)}
                >
                  <img
                    src={url}
                    alt=""
                    onError={() => markImageUnavailable(artifact.artifactId)}
                  />
                  <span>{artifact.artifactId}</span>
                </button>
              );
            })}
          </div>
        )}
        {unavailable.length + decodeFailures.length > 0 && (
          <p className="evidence-warning" role="status">
            {unavailable.length + decodeFailures.length} photo
            {unavailable.length + decodeFailures.length === 1 ? "" : "s"} unavailable.
            {unavailable.map((artifact) => ` ${artifact.artifactId}.`)}
            {decodeFailures.map((id) => ` ${id}.`)}
          </p>
        )}
      </div>
    )}
    {viewerOpen && selectedImage && (
      <ImageViewer
        key={selectedImage.artifact.artifactId}
        src={selectedImage.url}
        alt={selectedImage.artifact.description ?? "Synthetic vehicle evidence"}
        artifactId={selectedImage.artifact.artifactId}
        onClose={() => setViewerOpen(false)}
        onImageError={() => markImageUnavailable(selectedImage.artifact.artifactId)}
      />
    )}
  </section>;
}
