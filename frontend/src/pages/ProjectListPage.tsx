/**
 * ProjectListPage — página de listado de proyectos (/projekte).
 *
 * También actúa como host del diálogo de creación de proyecto (ProjectCreateDialog)
 * cuando ``showCreateDialog=true`` (ruta /projekte/neu). Usar la misma página como
 * host evita montar/desmontar la lista completa al abrir/cerrar el diálogo.
 *
 * Al cerrar el diálogo navega a /projekte sin destruir el estado de la lista.
 */
import { Link, useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../components/PageHeader";
import { ProjectCreateDialog } from "../features/projects/ProjectCreateDialog";
import { ProjectsListPanel } from "../features/projects/ProjectsListPanel";

type ProjectListPageProps = {
  showCreateDialog?: boolean;
};

export function ProjectListPage({
  showCreateDialog = false,
}: ProjectListPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <section className="panel-surface rounded-[2rem] p-6 md:p-8">
        <PageHeader
          eyebrow={t("projects.list.eyebrow")}
          title={t("projects.list.title")}
          description={t("projects.list.description")}
          actions={
            <Link
              to="/projekte/neu"
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white"
            >
              <Plus size={16} />
              {t("project_create.trigger")}
            </Link>
          }
        />
      </section>

      <ProjectsListPanel />

      <ProjectCreateDialog
        isOpen={showCreateDialog}
        onClose={() => navigate("/projekte")}
      />
    </div>
  );
}
