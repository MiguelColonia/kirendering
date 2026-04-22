import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import { patchProjectSolar } from "../../api/projects";
import { StatusBadge } from "../../components/StatusBadge";
import type { ProjectDetail, Solar } from "../../types/project";
import { createDefaultSolar } from "../projects/projectDefaults";
import { SolarEditorCanvas } from "./SolarEditorCanvas";
import { validateSolar } from "./solarValidation";

type ProjectSolarEditorProps = {
  project: ProjectDetail;
};

function inputClasses() {
  return "mt-2 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]";
}

export function ProjectSolarEditor({ project }: ProjectSolarEditorProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [draftSolar, setDraftSolar] = useState<Solar>(
    project.current_version?.solar ?? createDefaultSolar(),
  );
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setDraftSolar(project.current_version?.solar ?? createDefaultSolar());
    setFormMessage(null);
    setFormError(null);
  }, [project.current_version?.id, project.current_version?.updated_at, project.id]);

  const validation = validateSolar(draftSolar.contour.points);
  const hasValidHeight =
    Number.isFinite(draftSolar.max_buildable_height_m) &&
    draftSolar.max_buildable_height_m > 0;

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!hasValidHeight) {
        throw new Error(t("program_editor.validation.positive_number"));
      }

      if (!validation.valid) {
        throw new Error(t("solar_editor.save_invalid"));
      }

      return patchProjectSolar(project.id, draftSolar);
    },
    onSuccess: (updatedProject) => {
      queryClient.setQueryData(["project", project.id], updatedProject);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      setDraftSolar(updatedProject.current_version?.solar ?? createDefaultSolar());
      setFormError(null);
      setFormMessage(t("solar_editor.save_success"));
    },
    onError: (error) => {
      setFormMessage(null);
      setFormError(
        error instanceof Error ? error.message : t("solar_editor.save_error"),
      );
    },
  });

  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <div className="flex flex-col gap-5 border-b border-[color:var(--color-line)] pb-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <StatusBadge tone="accent">{t("project_editor.tabs.site")}</StatusBadge>
          <div>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
              {t("solar_editor.title")}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-[color:var(--color-mist)]">
              {t("solar_editor.description")}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || !hasValidHeight || !validation.valid}
          className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#143f50] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save size={16} />
          {t("common.save")}
        </button>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4 text-sm font-medium text-[color:var(--color-ink)]">
          {t("solar_editor.max_height")}
          <input
            type="number"
            min={0}
            step={0.5}
            value={draftSolar.max_buildable_height_m}
            onChange={(event) =>
              setDraftSolar((current) => ({
                ...current,
                max_buildable_height_m: Math.max(0, Number(event.target.value)),
              }))
            }
            className={inputClasses()}
          />
        </label>

        <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/78 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
            {t("solar_editor.north_label")}
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
            {Math.round(draftSolar.north_angle_deg)}°
          </p>
        </div>
      </div>

      {!hasValidHeight ? (
        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {t("program_editor.validation.positive_number")}
        </div>
      ) : null}

      {formMessage ? (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {formMessage}
        </div>
      ) : null}

      {formError ? (
        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {formError}
        </div>
      ) : null}

      <div className="mt-6 overflow-x-auto">
        <SolarEditorCanvas
          points={draftSolar.contour.points}
          northAngleDeg={draftSolar.north_angle_deg}
          onChange={(points) =>
            setDraftSolar((current) => ({
              ...current,
              contour: { points },
            }))
          }
          onNorthAngleChange={(deg) =>
            setDraftSolar((current) => ({
              ...current,
              north_angle_deg: deg,
            }))
          }
        />
      </div>
    </section>
  );
}