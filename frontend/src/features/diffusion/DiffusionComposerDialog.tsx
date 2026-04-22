import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileImage, Loader2, Sparkles, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { createDiffusion } from "../../api/diffusion";
import {
  useJobStream,
  type JobStreamCloseReason,
  type JobStreamError,
} from "../../hooks/useJobStream";
import type { DiffusionMode } from "../../types/diffusion";

type Phase = "compose" | "processing" | "done" | "error";
type JobStatus = "idle" | "queued" | "running" | "finished" | "failed";
type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "error";

type Props = {
  projectId: string;
  onClose: () => void;
  initialImageUrl?: string;
};

const MODES: { value: DiffusionMode; labelKey: string; descKey: string }[] = [
  {
    value: "img2img_controlnet_depth",
    labelKey: "diffusion.modes.depth.label",
    descKey: "diffusion.modes.depth.desc",
  },
  {
    value: "img2img_controlnet_canny",
    labelKey: "diffusion.modes.canny.label",
    descKey: "diffusion.modes.canny.desc",
  },
  {
    value: "instruct_pix2pix",
    labelKey: "diffusion.modes.pix2pix.label",
    descKey: "diffusion.modes.pix2pix.desc",
  },
];

export function DiffusionComposerDialog({
  projectId,
  onClose,
  initialImageUrl,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("compose");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!initialImageUrl) return;
    setPreview(initialImageUrl);
    fetch(initialImageUrl)
      .then((res) => res.blob())
      .then((blob) => {
        const filename = initialImageUrl.split("/").pop() ?? "source.png";
        setFile(new File([blob], filename, { type: blob.type || "image/png" }));
      })
      .catch(() => {});
  }, [initialImageUrl]);
  const [mode, setMode] = useState<DiffusionMode>("img2img_controlnet_depth");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus>("idle");
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useJobStream(jobId, {
    onEvent: (event) => {
      if (event.event === "finished") {
        setJobStatus("finished");
        setConnectionError(null);
        void queryClient.invalidateQueries({
          queryKey: ["diffusion", projectId],
        });
        setPhase("done");
        return;
      }

      if (event.event === "failed") {
        setJobStatus("failed");
        setError(t("diffusion.error.generic"));
        setPhase("error");
        return;
      }

      setJobStatus("running");
    },
    onOpen: () => {
      setConnectionStatus("connected");
      setConnectionError(null);
    },
    onReconnect: () => {
      setConnectionStatus("reconnecting");
      setConnectionError(t("generation.connection_lost"));
    },
    onSocketError: (jobError: JobStreamError) => {
      setConnectionStatus("error");
      setConnectionError(jobError.message);
    },
    onClose: (reason: JobStreamCloseReason) => {
      setConnectionStatus(reason === "completed" ? "closed" : "error");
    },
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    if (!picked) return;
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
  }

  async function handleSubmit() {
    if (!file || !prompt.trim()) return;
    setPhase("processing");
    setError(null);
    setConnectionStatus("connecting");
    setConnectionError(null);
    try {
      const result = await createDiffusion(projectId, file, {
        mode,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim() || undefined,
      });
      setJobId(result.job_id);
      setJobStatus(result.status === "queued" ? "queued" : "running");
    } catch {
      setError(t("diffusion.error.generic"));
      setConnectionStatus("error");
      setPhase("error");
    }
  }

  function handleRetry() {
    setPhase("compose");
    setError(null);
    setJobId(null);
    setJobStatus("idle");
    setConnectionStatus("idle");
    setConnectionError(null);
  }

  const canSubmit = file !== null && prompt.trim().length > 0;
  const visibleConnectionStatus =
    connectionStatus === "idle" ? "connecting" : connectionStatus;
  const visibleJobStatus = jobStatus === "idle" ? "queued" : jobStatus;

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
              {t("diffusion.eyebrow")}
            </p>
            <h2 className="mt-1 text-xl font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
              {t("diffusion.title")}
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
          {phase === "compose" && (
            <div className="space-y-5">
              <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                {t("diffusion.description")}
              </p>

              {/* Mode selector */}
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("diffusion.compose.mode_label")}
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {MODES.map((m) => (
                    <button
                      key={m.value}
                      type="button"
                      onClick={() => setMode(m.value)}
                      className={`rounded-[1.25rem] border p-3 text-left transition ${
                        mode === m.value
                          ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)]"
                          : "border-[color:var(--color-line)] bg-white/60 hover:border-[color:var(--color-accent)]"
                      }`}
                    >
                      <p className="text-xs font-semibold text-[color:var(--color-ink)]">
                        {t(m.labelKey)}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-[color:var(--color-mist)]">
                        {t(m.descKey)}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Image upload */}
              <div
                className="flex cursor-pointer flex-col items-center gap-3 rounded-[1.5rem] border-2 border-dashed border-[color:var(--color-line)] bg-white/60 p-8 transition hover:border-[color:var(--color-accent)]"
                onClick={() => inputRef.current?.click()}
              >
                {preview ? (
                  <img
                    src={preview}
                    alt="Vorschau"
                    className="max-h-48 rounded-xl object-contain"
                  />
                ) : (
                  <FileImage
                    size={40}
                    className="text-[color:var(--color-mist)]"
                  />
                )}
                <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                  {file ? file.name : t("diffusion.compose.upload_action")}
                </p>
                <p className="text-xs text-[color:var(--color-mist)]">
                  {t("diffusion.compose.upload_hint")}
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,.tif,.tiff"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>

              {/* Prompt */}
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("diffusion.compose.prompt_label")}
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={3}
                  placeholder={t("diffusion.compose.prompt_placeholder")}
                  className="w-full rounded-[1rem] border border-[color:var(--color-line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--color-ink)] placeholder-[color:var(--color-mist)] focus:border-[color:var(--color-accent)] focus:outline-none"
                />
              </div>

              {/* Negative prompt */}
              {mode !== "instruct_pix2pix" && (
                <div className="space-y-1">
                  <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t("diffusion.compose.negative_prompt_label")}
                  </label>
                  <input
                    type="text"
                    value={negativePrompt}
                    onChange={(e) => setNegativePrompt(e.target.value)}
                    placeholder={t(
                      "diffusion.compose.negative_prompt_placeholder",
                    )}
                    className="w-full rounded-[1rem] border border-[color:var(--color-line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--color-ink)] placeholder-[color:var(--color-mist)] focus:border-[color:var(--color-accent)] focus:outline-none"
                  />
                </div>
              )}

              {/* Hardware notice */}
              <div className="flex items-start gap-2 rounded-[1rem] border border-blue-100 bg-blue-50 p-4">
                <AlertTriangle
                  size={16}
                  className="mt-0.5 shrink-0 text-blue-500"
                />
                <p className="text-xs leading-6 text-blue-700">
                  {t("diffusion.compose.hardware_notice")}
                </p>
              </div>

              <button
                type="button"
                disabled={!canSubmit}
                onClick={handleSubmit}
                className="w-full rounded-full bg-[color:var(--color-accent)] px-6 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
              >
                {t("diffusion.compose.submit")}
              </button>
            </div>
          )}

          {phase === "processing" && (
            <div className="flex flex-col items-center gap-6 py-12">
              <Loader2
                size={48}
                className="animate-spin text-[color:var(--color-accent)]"
              />
              <div className="text-center">
                <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t("diffusion.processing.title")}
                </p>
                <p className="mt-2 max-w-sm text-sm leading-7 text-[color:var(--color-mist)]">
                  {t("diffusion.processing.description")}
                </p>
              </div>

              <div className="w-full max-w-md space-y-3 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-5 text-sm text-[color:var(--color-ink)]">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-[color:var(--color-mist)]">
                    {t("diffusion.processing.job")}
                  </span>
                  <span className="font-mono text-xs">{jobId ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-[color:var(--color-mist)]">
                    {t("diffusion.processing.status")}
                  </span>
                  <span>{t(`renders.status.${visibleJobStatus}`)}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-[color:var(--color-mist)]">
                    {t("diffusion.processing.connection")}
                  </span>
                  <span>
                    {t(`generation.connection.${visibleConnectionStatus}`)}
                  </span>
                </div>
              </div>

              {connectionError ? (
                <div className="w-full max-w-md rounded-[1rem] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
                  {connectionError}
                </div>
              ) : null}
            </div>
          )}

          {phase === "done" && (
            <div className="flex flex-col items-center gap-6 py-8">
              <Sparkles
                size={48}
                className="text-[color:var(--color-accent)]"
              />
              <div className="text-center">
                <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t("diffusion.done.title")}
                </p>
                <p className="mt-2 max-w-sm text-sm leading-7 text-[color:var(--color-mist)]">
                  {t("diffusion.done.description")}
                </p>
                {jobId && (
                  <p className="mt-1 font-mono text-xs text-[color:var(--color-mist)]">
                    Job: {jobId}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-[color:var(--color-accent)] px-6 py-3 text-sm font-semibold text-white"
              >
                {t("diffusion.done.confirm")}
              </button>
            </div>
          )}

          {phase === "error" && (
            <div className="flex flex-col items-center gap-6 py-8">
              <AlertTriangle size={48} className="text-amber-500" />
              <div className="text-center">
                <p className="text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {t("diffusion.error.title")}
                </p>
                {error && (
                  <p className="mt-2 max-w-sm text-sm text-[color:var(--color-mist)]">
                    {error}
                  </p>
                )}
              </div>

              <div className="w-full rounded-[1rem] border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs leading-6 text-amber-700">
                  {t("diffusion.error.hardware_hint")}
                </p>
              </div>

              <button
                type="button"
                onClick={handleRetry}
                className="rounded-full border border-[color:var(--color-line)] bg-white/80 px-6 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
              >
                {t("diffusion.error.retry")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
