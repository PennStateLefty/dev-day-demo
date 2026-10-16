import { useEffect, useState } from "react";
import type { Session } from "./auth";
import type { Artifact } from "./types";

export default function EvidencePreview({
  session, claimId,
}: { session: Session; claimId: string }) {
  const [images, setImages] = useState<{ artifact: Artifact; url: string }[]>([]);
  const [status, setStatus] = useState("Loading evidence…");
  useEffect(() => {
    const controller = new AbortController();
    const urls: string[] = [];
    setImages([]);
    setStatus("Loading evidence…");
    async function load() {
      const response = await session.request(`/api/claims/${claimId}/artifacts`, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Evidence metadata could not be loaded.");
      const artifacts = await response.json() as Artifact[];
      const photos = artifacts.filter((item) => item.artifactType === "damage_photo");
      const loaded = [];
      for (const artifact of photos) {
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
      }
      if (!controller.signal.aborted) {
        setImages(loaded);
        setStatus(photos.length ? "" : "No damage photo is linked to this claim.");
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

  return <section aria-label="Synthetic image evidence">
    <h3>Damage evidence</h3>
    <p className="muted">AI-generated synthetic evidence — not a real claimant photograph.</p>
    {status && <p role="status">{status}</p>}
    {images.map(({ artifact, url }) => <figure key={artifact.artifactId}>
      <img src={url} alt={artifact.description ?? "Synthetic vehicle evidence"}
        style={{ maxWidth: "100%", maxHeight: "360px", objectFit: "contain" }} />
      <figcaption>{artifact.artifactId} · AI-generated synthetic evidence</figcaption>
    </figure>)}
  </section>;
}
