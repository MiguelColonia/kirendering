import { useRef, useState } from "react";
import { AlertTriangle, FileImage, Loader2, ScanLine, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { analyzePlan } from "../../api/vision";
import type { PlanInterpretation } from "../../types/vision";

type Phase = "upload" | "analyzing" | "result" | "error";

type Props = {
  projectId: string;
  onClose: () => void;
};

export function PlanAnalyzerDialog({ projectId, onClose }: Props) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<PlanInterpretation | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    if (!picked) return;
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
  }

  async function handleSubmit() {
    if (!file) return;
    setPhase("analyzing");
    setError(null);
    try {
      const interpretation = await analyzePlan(projectId, file);
      setResult(interpretation);
      setPhase("result");
    } catch {
      setError(t("plan_analyzer.error.generic"));
      setPhase("error");
    }
  }

  function handleRetry() {
    setPhase("upload");
    setResult(null);
    setError(null);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="panel-surface relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-[2rem] shadow-2xl">
        <div className="flex items-start justify-between border-b border-[color:var(--color-line)] p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("plan_analyzer.eyebrow")}
            </p>
            <h2 className="mt-1 text-xl font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
              {t("plan_analyzer.title")}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="rounded-full p-2 text-[color:var(--color-mist)] transition hover:bg-[color:var(--color-line)]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {phase === "upload" && (
            <div className="space-y-5">
              <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                {t("plan_analyzer.description")}
              </p>

              <div
                className="flex cursor-pointer flex-col items-center gap-3 rounded-[1.5rem] border-2 border-dashed border-[color:var(--color-line)] bg-white/60 p-8 transition hover:border-[color:var(--color-accent)]"
                onClick={() => inputRef.current?.click()}
              >
                {preview ? (
                  <img
                    src={preview}
                    alt="Grundrissvorschau"
                    className="max-h-48 rounded-xl object-contain"
                  />
                ) : (
                  <FileImage size={40} className="text-[color:var(--color-mist)]" />
                )}
                <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                  {file ? file.name : t("plan_analyzer.upload.action")}
                </p>
                <p className="text-xs text-[color:var(--color-mist)]">
                  {t("plan_analyzer.upload.hint")}
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,.tif,.tiff"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>

              <div className="flex items-start gap-2 rounded-[1rem] border border-[color:var(--color-line)] bg-white/60 p-4">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
                <p className="text-xs leading-6 text-[color:var(--color-mist)]">
                  {t("plan_analyzer.upload.review_notice")}
                </p>
              </div>

              <div className="flex items-start gap-2 rounded-[1rem] border border-blue-100 bg-blue-50 p-4">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-blue-500" />
                <p className="text-xs leading-6 text-blue-700">
                  {t("plan_analyzer.upload.timeout_notice")}
                </p>
              </div>

              <button
                type="button"
                disabled={!file}
                onClick={handleSubmit}
                className="w-full rounded-full bg-[color:var(--color-accent)] px-6 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
              >
                {t("plan_analyzer.upload.submit")}
              </button>
            </div>
          )}

          {phase === "analyzing" && (
            <div className="flex flex-col items-center gap-6 py-12">
              <Loader2 size={48} className="animate-spin text-[color:var(--color-accent)]" />
              <div className="text-center">
                <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t("plan_analyzer.analyzing.title")}
                </p>
                <p className="mt-2 max-w-sm text-sm leading-7 text-[color:var(--color-mist)]">
                  {t("plan_analyzer.analyzing.description")}
                </p>
              </div>
            </div>
          )}

          {phase === "result" && result && (
            <div className="space-y-5">
              <div className="flex items-start gap-2 rounded-[1rem] border border-amber-200 bg-amber-50 p-4">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
                <p className="text-xs leading-6 text-amber-700">
                  {t("plan_analyzer.result.draft_notice")}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric
                  label={t("plan_analyzer.result.scale")}
                  value={
                    result.meters_per_pixel != null
                      ? t("plan_analyzer.result.scale_value", {
                          value: result.meters_per_pixel.toFixed(4),
                        })
                      : t("plan_analyzer.result.scale_unknown")
                  }
                />
                <Metric
                  label={t("plan_analyzer.result.dimensions")}
                  value={`${result.image_width_px} × ${result.image_height_px} px`}
                />
                <Metric
                  label={t("plan_analyzer.result.walls_detected")}
                  value={String(result.wall_segment_count)}
                />
                <Metric
                  label={t("plan_analyzer.result.bim_draft")}
                  value={result.has_draft_building ? "✓" : "—"}
                />
              </div>

              <Section title={t("plan_analyzer.result.rooms_title")}>
                {result.room_regions.length === 0 ? (
                  <p className="text-sm text-[color:var(--color-mist)]">
                    {t("plan_analyzer.result.no_rooms")}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {result.room_regions.map((r, i) => (
                      <li
                        key={i}
                        className="flex items-center gap-3 rounded-[1rem] border border-[color:var(--color-line)] bg-white/60 px-4 py-2"
                      >
                        <span className="rounded-full bg-[color:var(--color-accent-soft)] px-3 py-1 text-xs font-semibold text-[color:var(--color-accent)]">
                          {r.room_type}
                        </span>
                        <span className="text-sm text-[color:var(--color-ink)]">
                          {r.label_text ?? "—"}
                        </span>
                        <span className="ml-auto text-xs text-[color:var(--color-mist)]">
                          {r.approx_bbox_px.width} × {r.approx_bbox_px.height} px
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title={t("plan_analyzer.result.labels_title")}>
                {result.detected_labels.length === 0 ? (
                  <p className="text-sm text-[color:var(--color-mist)]">
                    {t("plan_analyzer.result.no_labels")}
                  </p>
                ) : (
                  <ul className="flex flex-wrap gap-2">
                    {result.detected_labels.map((lb, i) => (
                      <li
                        key={i}
                        className="rounded-full border border-[color:var(--color-line)] bg-white/60 px-3 py-1 text-xs text-[color:var(--color-ink)]"
                      >
                        {lb.raw_text}
                        {lb.room_type && (
                          <span className="ml-1 text-[color:var(--color-mist)]">
                            ({lb.room_type})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title={t("plan_analyzer.result.symbols_title")}>
                {result.detected_symbols.length === 0 ? (
                  <p className="text-sm text-[color:var(--color-mist)]">
                    {t("plan_analyzer.result.no_symbols")}
                  </p>
                ) : (
                  <ul className="flex flex-wrap gap-2">
                    {result.detected_symbols.map((s, i) => (
                      <li
                        key={i}
                        className="flex items-center gap-1 rounded-full border border-[color:var(--color-line)] bg-white/60 px-3 py-1 text-xs text-[color:var(--color-ink)]"
                      >
                        <ScanLine size={12} />
                        {s.symbol_type}
                        <span className="text-[color:var(--color-mist)]">
                          {(s.confidence * 100).toFixed(0)}%
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              {result.warnings.length > 0 && (
                <Section title={t("plan_analyzer.result.warnings_title")}>
                  <ul className="space-y-1">
                    {result.warnings.map((w, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-amber-700">
                        <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                        {w}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-full bg-[color:var(--color-accent)] px-6 py-3 text-sm font-semibold text-white"
              >
                {t("plan_analyzer.result.confirm")}
              </button>
            </div>
          )}

          {phase === "error" && (
            <div className="flex flex-col items-center gap-6 py-8">
              <AlertTriangle size={48} className="text-amber-500" />
              <div className="text-center">
                <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t("plan_analyzer.error.title")}
                </p>
                {error && (
                  <p className="mt-2 max-w-sm text-sm text-[color:var(--color-mist)]">{error}</p>
                )}
              </div>

              <div className="w-full rounded-[1rem] border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs leading-6 text-amber-700">
                  {t("plan_analyzer.error.hardware_hint")}
                </p>
              </div>

              <button
                type="button"
                onClick={handleRetry}
                className="rounded-full border border-[color:var(--color-line)] bg-white/80 px-6 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
              >
                {t("plan_analyzer.error.retry")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold tracking-[-0.02em] text-[color:var(--color-ink)]">
        {value}
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-[color:var(--color-ink)]">{title}</h3>
      {children}
    </div>
  );
}
