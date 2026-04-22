import { lazy, Suspense, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ScanLine, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteProject } from "../api/projects";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { ChatPanel } from "../features/chat/ChatPanel";
import { ProjectGenerationPanel } from "../features/generation/ProjectGenerationPanel";
import { PlanAnalyzerDialog } from "../features/plan-analyzer/PlanAnalyzerDialog";
import { ProjectProgramEditor } from "../features/program-editor/ProjectProgramEditor";
import { ProjectSolarEditor } from "../features/solar-editor/ProjectSolarEditor";
import { useProjectDetailQuery } from "../features/projects/useProjectsQuery";
import { formatDate } from "../utils/format";

const IfcModelWorkspace = lazy(() =>
  import("../features/ifc-viewer/IfcModelWorkspace").then((m) => ({
    default: m.IfcModelWorkspace,
  })),
);

function statusTone(status: string): "neutral" | "good" | "warn" | "accent" {
  if (status === "optimal" || status === "feasible") {
    return "good";
  }
  if (status === "infeasible" || status === "timeout" || status === "error") {
    return "warn";
  }
  return "accent";
}

export function ProjectEditorPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { id } = useParams();
  const projectQuery = useProjectDetailQuery(id);
  const [activeTab, setActiveTab] = useState<"site" | "program" | "model">(
    "site",
  );
  const [analyzerOpen, setAnalyzerOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const project = projectQuery.data;
  const outputs = project?.current_version?.generated_outputs ?? [];
  const hasIfcOutput = outputs.some((output) => output.output_type === "IFC");
  const visibleTab =
    activeTab === "model" && !hasIfcOutput ? "site" : activeTab;
  const totalUnits =
    project?.current_version?.program.mix.reduce(
      (total, entry) => total + entry.count,
      0,
    ) ?? 0;

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!project) {
        throw new Error(t("project_editor.delete_error"));
      }

      await deleteProject(project.id);
    },
    onMutate: () => {
      setDeleteError(null);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.removeQueries({ queryKey: ["project", project?.id] });
      navigate("/projekte");
    },
    onError: (error) => {
      setDeleteError(
        error instanceof Error
          ? error.message
          : t("project_editor.delete_error"),
      );
    },
  });

  if (projectQuery.isLoading) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">
          {t("common.loading")}
        </p>
      </section>
    );
  }

  if (!project) {
    return (
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <p className="text-sm text-[color:var(--color-mist)]">
          {t("common.empty")}
        </p>
      </section>
    );
  }

  return (
    <>
      {analyzerOpen && (
        <PlanAnalyzerDialog
          projectId={project.id}
          onClose={() => setAnalyzerOpen(false)}
        />
      )}
      <div className="space-y-6">
        <section className="panel-surface rounded-[2rem] p-6 md:p-8">
          <PageHeader
            eyebrow={t("project_editor.eyebrow")}
            title={project.name}
            description={
              project.description || t("project_editor.description_fallback")
            }
            actions={
              <>
                <button
                  type="button"
                  onClick={() => setAnalyzerOpen(true)}
                  className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
                >
                  <ScanLine size={16} />
                  {t("plan_analyzer.trigger")}
                </button>
                <Link
                  to={`/projekte/${project.id}/renders`}
                  className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-clay)] px-5 py-3 text-sm font-semibold text-white"
                >
                  {t("project_editor.render_gallery")}
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    if (
                      window.confirm(
                        t("project_editor.delete_confirm", {
                          name: project.name,
                        }),
                      )
                    ) {
                      deleteMutation.mutate();
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-5 py-3 text-sm font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Trash2 size={16} />
                  {deleteMutation.isPending
                    ? t("project_editor.delete_pending")
                    : t("project_editor.delete_project")}
                </button>
                <Link
                  to="/projekte"
                  className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
                >
                  <ArrowLeft size={16} />
                  {t("project_editor.back_to_list")}
                </Link>
              </>
            }
          />
        </section>

        {deleteError ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {deleteError}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
          <section className="panel-surface rounded-[2rem] p-6">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge tone={statusTone(project.status)}>
                {t(`projects.status.${project.status}`)}
              </StatusBadge>
              <StatusBadge>
                {t("project_editor.version_label", {
                  count: project.latest_version_number ?? 0,
                })}
              </StatusBadge>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("project_editor.meta.created_at")}
                </p>
                <p className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {formatDate(project.created_at)}
                </p>
              </div>
              <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("project_editor.meta.updated_at")}
                </p>
                <p className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {formatDate(project.updated_at)}
                </p>
              </div>
              <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("project_editor.meta.floors")}
                </p>
                <p className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {project.current_version?.program.num_floors ?? 0}
                </p>
              </div>
              <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                  {t("project_editor.meta.units")}
                </p>
                <p className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                  {totalUnits}
                </p>
              </div>
            </div>
          </section>

          <section className="panel-surface rounded-[2rem] p-6">
            <div className="space-y-3">
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
                {t("project_editor.workspace_title")}
              </h2>
              <p className="max-w-2xl text-sm leading-7 text-[color:var(--color-mist)]">
                {t("project_editor.workspace_description")}
              </p>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setActiveTab("site")}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-semibold transition",
                  visibleTab === "site"
                    ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                    : "border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)]",
                ].join(" ")}
              >
                {t("project_editor.tabs.site")}
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("program")}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-semibold transition",
                  visibleTab === "program"
                    ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                    : "border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)]",
                ].join(" ")}
              >
                {t("project_editor.tabs.program")}
              </button>

              {hasIfcOutput ? (
                <button
                  type="button"
                  onClick={() => setActiveTab("model")}
                  className={[
                    "rounded-full border px-4 py-2 text-sm font-semibold transition",
                    visibleTab === "model"
                      ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                      : "border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)]",
                  ].join(" ")}
                >
                  {t("project_editor.tabs.model")}
                </button>
              ) : null}
            </div>

            {!hasIfcOutput ? (
              <div className="mt-6 rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] bg-white/55 p-5">
                <p className="text-sm leading-7 text-[color:var(--color-mist)]">
                  {t("ifc_viewer.model_tab_hint")}
                </p>
              </div>
            ) : null}
          </section>
        </div>

        <ProjectGenerationPanel key={project.id} projectId={project.id} />

        {visibleTab === "site" ? (
          <ProjectSolarEditor project={project} />
        ) : null}

        {visibleTab === "program" ? (
          <ProjectProgramEditor project={project} />
        ) : null}
        {visibleTab === "model" && hasIfcOutput ? (
          <Suspense
            fallback={
              <section className="panel-surface rounded-[2rem] p-6 md:p-8">
                <p className="text-sm text-[color:var(--color-mist)]">
                  {t("ifc_viewer.loading")}
                </p>
              </section>
            }
          >
            <IfcModelWorkspace outputs={outputs} project={project} />
          </Suspense>
        ) : null}

        <ChatPanel projectId={project.id} />
      </div>
    </>
  );
}
