import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  LoaderCircle,
  Play,
  Radio,
  TimerReset,
  Workflow,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDate } from "../../utils/format";
import type { JobEvent } from "../../types/project";
import {
  getGenerationFailure,
  getGenerationPhases,
  type GenerationPhaseStatus,
} from "./generationProgress";

type GenerationStatusPanelProps = {
  jobId: string | null;
  status: string;
  events: JobEvent[];
  isPending: boolean;
  onGenerate: () => void;
  startError?: string | null;
  connectionStatus?:
    | "idle"
    | "connecting"
    | "connected"
    | "reconnecting"
    | "closed"
    | "error";
  connectionError?: string | null;
};

function toneForStatus(status: string): "neutral" | "good" | "warn" | "accent" {
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

function toneForStep(
  status: GenerationPhaseStatus,
): "neutral" | "good" | "warn" | "accent" {
  if (status === "success") {
    return "good";
  }
  if (status === "error") {
    return "warn";
  }
  if (status === "running") {
    return "accent";
  }
  return "neutral";
}

function formatDuration(
  durationMs: number | null,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  if (durationMs === null) {
    return t("generation.not_started");
  }

  const totalSeconds = Math.max(0, Math.round(durationMs / 1000));
  if (totalSeconds < 60) {
    return `${totalSeconds} s`;
  }

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes} min ${String(seconds).padStart(2, "0")} s`;
}

function StepIcon({ status }: { status: GenerationPhaseStatus }) {
  if (status === "success") {
    return <CheckCircle2 size={18} />;
  }
  if (status === "error") {
    return <AlertTriangle size={18} />;
  }
  if (status === "running") {
    return <LoaderCircle size={18} className="animate-spin" />;
  }
  return <CircleDot size={18} />;
}

export function GenerationStatusPanel({
  jobId,
  status,
  events,
  isPending,
  onGenerate,
  startError,
  connectionStatus = "idle",
  connectionError,
}: GenerationStatusPanelProps) {
  const { t } = useTranslation();
  const [now, setNow] = useState(() => Date.now());

  const statusLabels: Record<string, string> = {
    idle: t("generation.idle"),
    queued: t("generation.queued"),
    running: t("generation.running"),
    finished: t("generation.finished"),
    failed: t("generation.failed"),
  };

  const connectionLabels: Record<
    NonNullable<GenerationStatusPanelProps["connectionStatus"]>,
    string
  > = {
    idle: t("generation.connection.idle"),
    connecting: t("generation.connection.connecting"),
    connected: t("generation.connection.connected"),
    reconnecting: t("generation.connection.reconnecting"),
    closed: t("generation.connection.closed"),
    error: t("generation.connection.error"),
  };

  const showLiveTimer = status === "queued" || status === "running";

  useEffect(() => {
    if (!showLiveTimer) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [showLiveTimer]);

  const phases = useMemo(
    () => getGenerationPhases(events, status, now),
    [events, now, status],
  );
  const failure = useMemo(() => getGenerationFailure(events), [events]);
  const showInfeasibleBanner = failure?.infeasible ?? false;
  const showFailureBanner = Boolean(!showInfeasibleBanner && failure?.message);
  const showConnectionBanner =
    connectionStatus === "reconnecting" || connectionStatus === "error";

  return (
    <section className="panel-surface rounded-[2rem] p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-[-0.03em]">
            {t("generation.title")}
          </h2>
          <p className="max-w-2xl text-sm leading-6 text-[color:var(--color-mist)]">
            {t("generation.description")}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={toneForStatus(status)}>
            {statusLabels[status] ?? t("generation.idle")}
          </StatusBadge>
          {jobId ? (
            <StatusBadge
              tone={
                connectionStatus === "connected"
                  ? "good"
                  : connectionStatus === "reconnecting"
                    ? "warn"
                    : "neutral"
              }
            >
              {connectionLabels[connectionStatus]}
            </StatusBadge>
          ) : null}
          <button
            type="button"
            onClick={onGenerate}
            disabled={isPending}
            className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-teal)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#0c655e] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Play size={16} />
            {t("generation.start")}
          </button>
        </div>
      </div>

      {startError ? (
        <div className="mt-5 rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
          {startError}
        </div>
      ) : null}

      {showConnectionBanner ? (
        <div className="mt-5 rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
          {connectionError ?? t("generation.connection_lost")}
        </div>
      ) : null}

      {showInfeasibleBanner ? (
        <div className="mt-5 rounded-[1.5rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
          <p className="font-semibold">{t("generation.infeasible.title")}</p>
          <p className="mt-2 leading-6">
            {failure?.message ?? t("generation.infeasible.description")}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-rose-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em]">
              {t("generation.infeasible.suggestion_reduce_units")}
            </span>
            <span className="rounded-full border border-rose-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em]">
              {t("generation.infeasible.suggestion_expand_site")}
            </span>
          </div>
        </div>
      ) : null}

      {showFailureBanner ? (
        <div className="mt-5 rounded-[1.5rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
          <p className="font-semibold">{t("generation.failed")}</p>
          <p className="mt-2 leading-6">
            {failure?.message ?? t("generation.failed_detail_fallback")}
          </p>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div className="space-y-3 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-[color:var(--color-clay-soft)] p-3 text-[color:var(--color-clay)]">
              <Workflow size={18} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t("generation.job")}
              </p>
              <p className="mt-1 break-all text-sm font-medium text-[color:var(--color-ink)]">
                {jobId ?? t("generation.not_started")}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-3">
            <Radio size={16} className="text-[color:var(--color-accent)]" />
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t("generation.connection.title")}
              </p>
              <p className="mt-1 text-sm font-medium text-[color:var(--color-ink)]">
                {connectionLabels[connectionStatus]}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[color:var(--color-ink)]">
            <Activity size={16} />
            {t("generation.phase_title")}
          </div>

          <ol className="space-y-4">
            {phases.map((phase, index) => (
              <li key={phase.id} className="relative pl-10">
                {index < phases.length - 1 ? (
                  <span className="absolute left-[0.55rem] top-8 h-[calc(100%-0.75rem)] w-px bg-[color:var(--color-line)]" />
                ) : null}

                <span
                  className={[
                    "absolute left-0 top-1 inline-flex h-5 w-5 items-center justify-center rounded-full border",
                    phase.status === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : phase.status === "error"
                        ? "border-rose-200 bg-rose-50 text-rose-700"
                        : phase.status === "running"
                          ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                          : "border-[color:var(--color-line)] bg-white text-[color:var(--color-mist)]",
                  ].join(" ")}
                >
                  <StepIcon status={phase.status} />
                </span>

                <div className="rounded-[1.25rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] px-4 py-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-[color:var(--color-ink)]">
                        {t(`generation.steps.${phase.id}.title`)}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-[color:var(--color-mist)]">
                        {t(`generation.steps.${phase.id}.description`)}
                      </p>
                    </div>
                    <StatusBadge tone={toneForStep(phase.status)}>
                      {t(`generation.step_status.${phase.status}`)}
                    </StatusBadge>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-4 text-xs uppercase tracking-[0.14em] text-[color:var(--color-mist)]">
                    <span className="inline-flex items-center gap-2">
                      <TimerReset size={14} />
                      {t("generation.duration")}:{" "}
                      {formatDuration(phase.durationMs, t)}
                    </span>
                    <span>
                      {t("generation.started_at")}:{" "}
                      {phase.startedAt
                        ? formatDate(phase.startedAt)
                        : t("generation.not_started")}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
