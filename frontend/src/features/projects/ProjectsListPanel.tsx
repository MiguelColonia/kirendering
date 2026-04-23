/**
 * ProjectsListPanel — tabla de proyectos con búsqueda incremental.
 *
 * Usa `useDeferredValue` para el filtro de búsqueda: permite que React procese
 * el keystroke (actualizar el input) de inmediato y difiera el re-render de la tabla
 * hasta que el hilo esté libre, evitando que listas largas bloqueen la entrada de texto.
 *
 * Los estados de proyecto se mapean a tonos visuales (good/warn/accent/neutral)
 * para que el estado de generación sea legible de un vistazo en la tabla.
 */
import { useDeferredValue, useState } from "react";
import { FolderOpen, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDate } from "../../utils/format";
import { useProjectsQuery } from "./useProjectsQuery";

function statusTone(status: string): "neutral" | "good" | "warn" | "accent" {
  if (status === "optimal" || status === "feasible") {
    return "good";
  }
  if (status === "infeasible" || status === "timeout" || status === "error") {
    return "warn";
  }
  if (status === "draft") {
    return "accent";
  }
  return "neutral";
}

export function ProjectsListPanel() {
  const { t } = useTranslation();
  const [searchValue, setSearchValue] = useState("");
  const deferredSearchValue = useDeferredValue(searchValue);
  const projectsQuery = useProjectsQuery();

  const filteredProjects = (projectsQuery.data ?? []).filter((project) =>
    project.name.toLowerCase().includes(deferredSearchValue.toLowerCase()),
  );

  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <div className="flex justify-end border-b border-[color:var(--color-line)] pb-5">
        <label className="flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--color-mist)]">
          <Search size={16} />
          <input
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder={t("projects.list.search_placeholder")}
            className="w-56 bg-transparent outline-none placeholder:text-[color:var(--color-mist)]"
          />
        </label>
      </div>

      <div className="mt-6 space-y-4">
        {projectsQuery.isLoading ? (
          <p className="text-sm text-[color:var(--color-mist)]">
            {t("common.loading")}
          </p>
        ) : null}

        {projectsQuery.isError ? (
          <div className="rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-700">
            <p>{t("projects.list.offline")}</p>
            <button
              type="button"
              onClick={() => void projectsQuery.refetch()}
              className="mt-3 rounded-full border border-amber-300 px-4 py-2 font-medium"
            >
              {t("common.retry")}
            </button>
          </div>
        ) : null}

        {!projectsQuery.isLoading &&
        !projectsQuery.isError &&
        filteredProjects.length === 0 ? (
          <div className="rounded-[1.75rem] border border-dashed border-[color:var(--color-line)] px-5 py-8 text-sm text-[color:var(--color-mist)]">
            {t("projects.list.empty")}
          </div>
        ) : null}

        {filteredProjects.length > 0 ? (
          <div className="overflow-hidden rounded-[1.75rem] border border-[color:var(--color-line)] bg-white/82">
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-left">
                <thead className="bg-[color:var(--color-paper)]/95">
                  <tr>
                    <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                      {t("projects.table.columns.name")}
                    </th>
                    <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                      {t("projects.table.columns.created_at")}
                    </th>
                    <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                      {t("projects.table.columns.status")}
                    </th>
                    <th className="px-5 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                      {t("projects.table.columns.actions")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProjects.map((project) => (
                    <tr
                      key={project.id}
                      className="border-t border-[color:var(--color-line)] align-top"
                    >
                      <td className="px-5 py-5">
                        <div className="space-y-2">
                          <p className="text-base font-semibold tracking-[-0.02em] text-[color:var(--color-ink)]">
                            {project.name}
                          </p>
                          <p className="max-w-md text-sm leading-6 text-[color:var(--color-mist)]">
                            {project.description ||
                              t("projects.table.empty_description")}
                          </p>
                        </div>
                      </td>
                      <td className="px-5 py-5 text-sm text-[color:var(--color-mist)]">
                        {formatDate(project.created_at)}
                      </td>
                      <td className="px-5 py-5">
                        <StatusBadge tone={statusTone(project.status)}>
                          {t(`projects.status.${project.status}`)}
                        </StatusBadge>
                      </td>
                      <td className="px-5 py-5">
                        <Link
                          to={`/projekte/${project.id}`}
                          className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] px-4 py-2 text-sm font-medium text-[color:var(--color-ink)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
                        >
                          <FolderOpen size={16} />
                          {t("projects.table.open_action")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
