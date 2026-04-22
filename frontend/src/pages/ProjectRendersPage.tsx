import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  ArrowLeft,
  Clock3,
  Download,
  ImagePlus,
  LoaderCircle,
  Sparkles,
  Upload,
  Wand2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { createRender, listRenders, resolveApiUrl } from "../api/projects";
import { listDiffusion } from "../api/diffusion";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { DiffusionComposerDialog } from "../features/diffusion/DiffusionComposerDialog";
import { useProjectDetailQuery } from "../features/projects/useProjectsQuery";
import { getRenderProgress } from "../features/renders/renderProgress";
import {
  useJobStream,
  type JobStreamCloseReason,
  type JobStreamError,
} from "../hooks/useJobStream";
import type {
  CreateRenderPayload,
  JobEvent,
  RenderGalleryItem,
  RenderViewType,
} from "../types/project";
import type { DiffusionGalleryItem } from "../types/diffusion";
import { formatDate } from "../utils/format";

type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "error";

function formatDuration(seconds: number | null): string {
  if (seconds === null) {
    return "—";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)} s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes} min ${String(remainingSeconds).padStart(2, "0")} s`;
}

function makeEventKey(event: JobEvent): string {
  return `${event.timestamp}:${event.event}:${JSON.stringify(event.data)}`;
}

function appendUniqueEvent(
  currentEvents: JobEvent[],
  nextEvent: JobEvent,
): JobEvent[] {
  const alreadyPresent = currentEvents.some(
    (event) => makeEventKey(event) === makeEventKey(nextEvent),
  );
  if (alreadyPresent) {
    return currentEvents;
  }

  return [...currentEvents, nextEvent].sort(
    (left, right) => Date.parse(left.timestamp) - Date.parse(right.timestamp),
  );
}

function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as
      | { error?: { message?: string } }
      | undefined;
    if (payload?.error?.message) {
      return payload.error.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

function toneForJobStatus(
  status: string,
): "neutral" | "good" | "warn" | "accent" {
  if (status === "finished") {
    return "good";
  }
  if (status === "failed") {
    return "warn";
  }
  if (status === "running" || status === "queued") {
    return "accent";
  }
  return "neutral";
}

function toneForConnectionStatus(
  status: ConnectionStatus,
): "neutral" | "good" | "warn" | "accent" {
  if (status === "connected" || status === "closed") {
    return "good";
  }
  if (status === "reconnecting" || status === "error") {
    return "warn";
  }
  if (status === "connecting") {
    return "accent";
  }
  return "neutral";
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Datei konnte nicht gelesen werden."));
        return;
      }
      const [, payload = result] = result.split(",", 2);
      resolve(payload);
    };
    reader.onerror = () =>
      reject(new Error("Datei konnte nicht gelesen werden."));
    reader.readAsDataURL(file);
  });
}

function RenderCard({
  render,
  projectName,
  exteriorLabel,
  interiorLabel,
  referenceLabel,
  deviceLabel,
  durationLabel,
  downloadLabel,
  versionLabel,
  refineLabel,
  onRefine,
}: {
  render: RenderGalleryItem;
  projectName: string;
  exteriorLabel: string;
  interiorLabel: string;
  referenceLabel: string;
  deviceLabel: string;
  durationLabel: string;
  downloadLabel: string;
  versionLabel: string;
  refineLabel: string;
  onRefine: (url: string) => void;
}) {
  const viewLabel = render.view === "interior" ? interiorLabel : exteriorLabel;

  return (
    <article className="overflow-hidden rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/85 shadow-[0_24px_60px_rgba(38,34,28,0.08)]">
      <div className="aspect-[16/10] overflow-hidden bg-[linear-gradient(135deg,rgba(207,128,93,0.12),rgba(31,110,122,0.08))]">
        <img
          src={resolveApiUrl(render.image_url)}
          alt={`${projectName} ${viewLabel}`}
          className="h-full w-full object-cover"
          loading="lazy"
        />
      </div>

      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone="accent">{viewLabel}</StatusBadge>
              <StatusBadge>
                {versionLabel.replace(
                  "{{count}}",
                  String(render.version_number),
                )}
              </StatusBadge>
            </div>
            <p className="mt-3 text-sm font-medium text-[color:var(--color-ink)]">
              {formatDate(render.created_at)}
            </p>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onRefine(resolveApiUrl(render.image_url))}
              className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--color-teal)] bg-white px-3 py-1.5 text-xs font-semibold text-[color:var(--color-teal)]"
            >
              <Wand2 size={13} />
              {refineLabel}
            </button>
            <a
              href={resolveApiUrl(render.download_url)}
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white px-4 py-2 text-sm font-semibold text-[color:var(--color-ink)]"
            >
              <Download size={16} />
              {downloadLabel}
            </a>
          </div>
        </div>

        {render.prompt ? (
          <p className="rounded-[1.25rem] bg-[color:var(--color-paper)] px-4 py-3 text-sm leading-6 text-[color:var(--color-ink)]">
            {render.prompt}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {durationLabel}
            </p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">
              {formatDuration(render.duration_seconds)}
            </p>
          </div>
          <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {deviceLabel}
            </p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">
              {render.device_used ?? "—"}
            </p>
          </div>
        </div>

        {render.has_reference_image ? (
          <p className="text-sm text-[color:var(--color-mist)]">
            {referenceLabel}: {render.reference_image_name}
          </p>
        ) : null}
      </div>
    </article>
  );
}

export function ProjectRendersPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { id } = useParams();
  const projectQuery = useProjectDetailQuery(id);
  const rendersQuery = useQuery({
    queryKey: ["renders", id],
    queryFn: () => listRenders(id!),
    enabled: Boolean(id),
  });

  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [isDiffusionOpen, setIsDiffusionOpen] = useState(false);
  const [diffusionSourceUrl, setDiffusionSourceUrl] = useState<
    string | undefined
  >(undefined);

  function openDiffusionWith(sourceUrl?: string) {
    setDiffusionSourceUrl(sourceUrl);
    setIsDiffusionOpen(true);
  }
  const diffusionQuery = useQuery({
    queryKey: ["diffusion", id],
    queryFn: () => listDiffusion(id!),
    enabled: Boolean(id),
  });
  const [view, setView] = useState<RenderViewType>("exterior");
  const [prompt, setPrompt] = useState("");
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState("idle");
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setActiveJobId(null);
    setJobStatus("idle");
    setJobEvents([]);
    setConnectionStatus("idle");
    setConnectionError(null);
    setStartError(null);
    setIsComposerOpen(false);
  }, [id]);

  const activeStatus = activeJobId ? jobStatus : "idle";
  const showLiveTimer = activeStatus === "queued" || activeStatus === "running";

  useEffect(() => {
    if (!showLiveTimer) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [showLiveTimer]);

  const refreshData = () => {
    void queryClient.invalidateQueries({ queryKey: ["renders", id] });
    void queryClient.invalidateQueries({ queryKey: ["project", id] });
  };

  useJobStream(activeJobId, {
    onEvent: (event) => {
      setJobEvents((currentEvents) => appendUniqueEvent(currentEvents, event));

      if (event.event === "finished") {
        setJobStatus("finished");
        refreshData();
        return;
      }

      if (event.event === "failed") {
        setJobStatus("failed");
        refreshData();
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
      setConnectionError(t("renders.connection_lost"));
    },
    onSocketError: (error: JobStreamError) => {
      setConnectionStatus("error");
      setConnectionError(error.message);
    },
    onClose: (reason: JobStreamCloseReason) => {
      setConnectionStatus(reason === "completed" ? "closed" : "error");
    },
  });

  const renderMutation = useMutation({
    mutationFn: async () => {
      const payload: CreateRenderPayload = {
        view,
        prompt: prompt.trim() || null,
      };

      if (referenceFile) {
        payload.reference_image_name = referenceFile.name;
        payload.reference_image_media_type = referenceFile.type;
        payload.reference_image_base64 = await fileToBase64(referenceFile);
      }

      return createRender(id!, payload);
    },
    onMutate: () => {
      setStartError(null);
      setConnectionError(null);
    },
    onSuccess: ({ job_id, status }) => {
      setActiveJobId(job_id);
      setJobStatus(status);
      setJobEvents([]);
      setConnectionStatus("connecting");
      setConnectionError(null);
      setIsComposerOpen(false);
    },
    onError: (error) => {
      setStartError(extractApiErrorMessage(error, t("renders.start_error")));
    },
  });

  if (!id) {
    return null;
  }

  if (projectQuery.isLoading) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">
          {t("common.loading")}
        </p>
      </section>
    );
  }

  if (!projectQuery.data) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">
          {t("common.empty")}
        </p>
      </section>
    );
  }

  const project = projectQuery.data;
  const renders = rendersQuery.data ?? [];
  const hasIfcOutput =
    project.current_version?.generated_outputs.some(
      (output) => output.output_type === "IFC",
    ) ?? false;
  const isRenderPending =
    renderMutation.isPending ||
    activeStatus === "queued" ||
    activeStatus === "running" ||
    connectionStatus === "connecting" ||
    connectionStatus === "reconnecting";
  const progress = getRenderProgress(
    jobEvents,
    renderMutation.isPending ? "queued" : activeStatus,
    now,
  );
  const viewLabels: Record<RenderViewType, string> = {
    exterior: t("renders.views.exterior"),
    interior: t("renders.views.interior"),
  };
  const statusLabels: Record<string, string> = {
    idle: t("renders.status.idle"),
    queued: t("renders.status.queued"),
    running: t("renders.status.running"),
    finished: t("renders.status.finished"),
    failed: t("renders.status.failed"),
  };
  const connectionLabels: Record<ConnectionStatus, string> = {
    idle: t("renders.connection.idle"),
    connecting: t("renders.connection.connecting"),
    connected: t("renders.connection.connected"),
    reconnecting: t("renders.connection.reconnecting"),
    closed: t("renders.connection.closed"),
    error: t("renders.connection.error"),
  };
  const latestEvents = [...jobEvents].slice(-4).reverse();

  return (
    <div className="space-y-6">
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <PageHeader
          eyebrow={t("renders.eyebrow")}
          title={project.name}
          description={t("renders.description")}
          actions={
            <>
              <Link
                to={`/projekte/${project.id}`}
                className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
              >
                <ArrowLeft size={16} />
                {t("renders.back_to_project")}
              </Link>
              <button
                type="button"
                onClick={() => setIsComposerOpen((current) => !current)}
                className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-clay)] px-5 py-3 text-sm font-semibold text-white"
              >
                <ImagePlus size={16} />
                {t("renders.new_render")}
              </button>
              <button
                type="button"
                onClick={() => openDiffusionWith()}
                className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-teal)] px-5 py-3 text-sm font-semibold text-white"
              >
                <Wand2 size={16} />
                {t("diffusion.trigger")}
              </button>
            </>
          }
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
        <section className="panel-surface rounded-[2rem] p-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
                {t("renders.form.title")}
              </h2>
              <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                {t("renders.form.description")}
              </p>
            </div>
            <StatusBadge tone={hasIfcOutput ? "good" : "warn"}>
              {hasIfcOutput
                ? t("renders.form.ifc_ready")
                : t("renders.form.ifc_missing")}
            </StatusBadge>
          </div>

          {isComposerOpen ? (
            <div className="mt-6 space-y-5">
              <label className="block space-y-2">
                <span className="text-sm font-semibold text-[color:var(--color-ink)]">
                  {t("renders.form.fields.view")}
                </span>
                <select
                  value={view}
                  onChange={(event) =>
                    setView(event.target.value as RenderViewType)
                  }
                  className="w-full rounded-[1.25rem] border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm text-[color:var(--color-ink)] outline-none transition focus:border-[color:var(--color-accent)]"
                >
                  <option value="exterior">
                    {t("renders.views.exterior")}
                  </option>
                  <option value="interior">
                    {t("renders.views.interior")}
                  </option>
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-[color:var(--color-ink)]">
                  {t("renders.form.fields.prompt")}
                </span>
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={4}
                  placeholder={t("renders.form.prompt_placeholder")}
                  className="w-full rounded-[1.5rem] border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm leading-7 text-[color:var(--color-ink)] outline-none transition focus:border-[color:var(--color-accent)]"
                />
              </label>

              <div className="space-y-2">
                <span className="text-sm font-semibold text-[color:var(--color-ink)]">
                  {t("renders.form.fields.reference")}
                </span>
                <label className="flex cursor-pointer items-center justify-between gap-4 rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] bg-white/80 px-4 py-4 text-sm text-[color:var(--color-ink)]">
                  <span className="inline-flex items-center gap-3">
                    <Upload size={18} />
                    {referenceFile?.name ??
                      t("renders.form.reference_placeholder")}
                  </span>
                  <span className="rounded-full border border-[color:var(--color-line)] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                    {t("renders.form.reference_action")}
                  </span>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                    className="sr-only"
                    onChange={(event) =>
                      setReferenceFile(event.target.files?.[0] ?? null)
                    }
                  />
                </label>
              </div>

              {!hasIfcOutput ? (
                <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
                  {t("renders.form.ifc_hint")}
                </div>
              ) : null}

              {startError ? (
                <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
                  {startError}
                </div>
              ) : null}

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => renderMutation.mutate()}
                  disabled={!hasIfcOutput || isRenderPending}
                  className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-teal)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#0c655e] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {renderMutation.isPending ? (
                    <LoaderCircle size={16} className="animate-spin" />
                  ) : (
                    <Sparkles size={16} />
                  )}
                  {t("renders.form.submit")}
                </button>
                <button
                  type="button"
                  onClick={() => setIsComposerOpen(false)}
                  className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
                >
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-6 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-5">
              <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                {t("renders.form.collapsed_hint")}
              </p>
            </div>
          )}
        </section>

        <section className="panel-surface rounded-[2rem] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
                {t("renders.progress.title")}
              </h2>
              <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                {t("renders.progress.description")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge
                tone={toneForJobStatus(
                  renderMutation.isPending ? "queued" : activeStatus,
                )}
              >
                {
                  statusLabels[
                    renderMutation.isPending ? "queued" : activeStatus
                  ]
                }
              </StatusBadge>
              {activeJobId ? (
                <StatusBadge tone={toneForConnectionStatus(connectionStatus)}>
                  {connectionLabels[connectionStatus]}
                </StatusBadge>
              ) : null}
            </div>
          </div>

          {connectionError ? (
            <div className="mt-5 rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
              {connectionError}
            </div>
          ) : null}

          <div className="mt-6 rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/85 p-5">
            <div className="flex items-center justify-between gap-3 text-sm font-semibold text-[color:var(--color-ink)]">
              <span>
                {progress.view === "interior"
                  ? t("renders.views.interior")
                  : t("renders.views.exterior")}
              </span>
              <span>{Math.round(progress.percent)}%</span>
            </div>

            <div className="mt-4 h-3 overflow-hidden rounded-full bg-[color:var(--color-paper)]">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,var(--color-clay),var(--color-teal))] transition-[width] duration-1000"
                style={{ width: `${progress.percent}%` }}
              />
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("renders.progress.remaining")}
                </p>
                <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">
                  {formatDuration(progress.remainingSeconds)}
                </p>
              </div>
              <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("renders.progress.estimated_total")}
                </p>
                <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">
                  {formatDuration(progress.estimatedTotalSeconds)}
                </p>
              </div>
              <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("renders.progress.started_at")}
                </p>
                <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">
                  {progress.startedAt ? formatDate(progress.startedAt) : "—"}
                </p>
              </div>
            </div>

            <div className="mt-5 flex items-center gap-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
              <Clock3 size={16} className="text-[color:var(--color-accent)]" />
              <p className="text-sm text-[color:var(--color-ink)]">
                {activeJobId
                  ? `${t("renders.progress.job")}: ${activeJobId}`
                  : t("renders.progress.idle_hint")}
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("renders.progress.latest_events")}
            </h3>
            {latestEvents.length === 0 ? (
              <p className="text-sm text-[color:var(--color-mist)]">
                {t("renders.progress.no_events")}
              </p>
            ) : (
              latestEvents.map((event) => (
                <div
                  key={makeEventKey(event)}
                  className="flex items-start gap-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-white/80 px-4 py-3"
                >
                  <span className="mt-1 h-2.5 w-2.5 rounded-full bg-[color:var(--color-accent)]" />
                  <div>
                    <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                      {t(`renders.events.${event.event}`, event.event)}
                    </p>
                    <p className="mt-1 text-xs text-[color:var(--color-mist)]">
                      {formatDate(event.timestamp)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <section className="panel-surface rounded-[2rem] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t("renders.gallery.title")}
            </h2>
            <p className="text-sm leading-7 text-[color:var(--color-mist)]">
              {t("renders.gallery.description")}
            </p>
          </div>
          <StatusBadge>{renders.length}</StatusBadge>
        </div>

        {rendersQuery.isLoading ? (
          <p className="mt-5 text-sm text-[color:var(--color-mist)]">
            {t("common.loading")}
          </p>
        ) : renders.length === 0 ? (
          <div className="mt-5 rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] bg-white/70 px-5 py-6 text-sm leading-7 text-[color:var(--color-mist)]">
            {t("renders.gallery.empty")}
          </div>
        ) : (
          <div className="mt-5 grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
            {renders.map((render) => (
              <RenderCard
                key={render.id}
                render={render}
                projectName={project.name}
                exteriorLabel={viewLabels.exterior}
                interiorLabel={viewLabels.interior}
                referenceLabel={t("renders.gallery.reference")}
                deviceLabel={t("renders.gallery.device")}
                durationLabel={t("renders.gallery.duration")}
                downloadLabel={t("renders.gallery.download")}
                versionLabel={t("project_editor.version_label", {
                  count: render.version_number,
                })}
                refineLabel={t("diffusion.refine")}
                onRefine={openDiffusionWith}
              />
            ))}
          </div>
        )}
      </section>
      <section className="panel-surface rounded-[2rem] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t("diffusion.title")}
            </h2>
            <p className="text-sm leading-7 text-[color:var(--color-mist)]">
              {t("diffusion.description")}
            </p>
          </div>
          <StatusBadge>{diffusionQuery.data?.length ?? 0}</StatusBadge>
        </div>

        {diffusionQuery.isLoading ? (
          <p className="mt-5 text-sm text-[color:var(--color-mist)]">
            {t("common.loading")}
          </p>
        ) : !diffusionQuery.data || diffusionQuery.data.length === 0 ? (
          <div className="mt-5 rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] bg-white/70 px-5 py-6 text-sm leading-7 text-[color:var(--color-mist)]">
            {t("diffusion.gallery_empty")}
          </div>
        ) : (
          <div className="mt-5 grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
            {diffusionQuery.data.map((item: DiffusionGalleryItem) => (
              <DiffusionCard
                key={item.id}
                item={item}
                onRefine={openDiffusionWith}
              />
            ))}
          </div>
        )}
      </section>

      {isDiffusionOpen && (
        <DiffusionComposerDialog
          projectId={id}
          initialImageUrl={diffusionSourceUrl}
          onClose={() => {
            setIsDiffusionOpen(false);
            setDiffusionSourceUrl(undefined);
            void queryClient.invalidateQueries({ queryKey: ["diffusion", id] });
          }}
        />
      )}
    </div>
  );
}

function DiffusionCard({
  item,
  onRefine,
}: {
  item: DiffusionGalleryItem;
  onRefine: (url: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <article className="overflow-hidden rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/85 shadow-[0_24px_60px_rgba(38,34,28,0.08)]">
      <div className="aspect-[1/1] overflow-hidden bg-[linear-gradient(135deg,rgba(31,110,122,0.12),rgba(207,128,93,0.08))]">
        <img
          src={resolveApiUrl(item.image_url)}
          alt={item.prompt ?? item.mode}
          className="h-full w-full object-cover"
          loading="lazy"
        />
      </div>
      <div className="space-y-3 p-5">
        <div className="flex flex-wrap gap-2">
          <StatusBadge tone="accent">
            {item.mode.replace(/_/g, " ")}
          </StatusBadge>
          {item.device_used && <StatusBadge>{item.device_used}</StatusBadge>}
        </div>
        {item.prompt && (
          <p className="rounded-[1.25rem] bg-[color:var(--color-paper)] px-4 py-3 text-sm leading-6 text-[color:var(--color-ink)]">
            {item.prompt}
          </p>
        )}
        {item.warnings.length > 0 && (
          <p className="text-xs text-amber-600">{item.warnings.join(" ")}</p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-[color:var(--color-mist)]">
            {formatDate(item.created_at)}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onRefine(resolveApiUrl(item.image_url))}
              className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--color-teal)] bg-white px-3 py-1.5 text-xs font-semibold text-[color:var(--color-teal)]"
            >
              <Wand2 size={12} />
              {t("diffusion.refine")}
            </button>
            <a
              href={resolveApiUrl(item.download_url)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--color-line)] bg-white px-3 py-1.5 text-xs font-semibold text-[color:var(--color-ink)]"
            >
              <Download size={12} />
              {t("common.download")}
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
