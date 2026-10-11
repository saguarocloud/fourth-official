/** Marks model-written content. Shown wherever AI output appears, per the disclosure policy. */
export function AiTag() {
  return (
    <span className="ai-tag" title="AI-generated, verified before publishing">
      AI
    </span>
  );
}
