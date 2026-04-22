import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { createProject } from "../../api/projects";
import type { Program, Solar } from "../../types/project";
import { ProgramEditorForm } from "../program-editor/ProgramEditorForm";
import {
  createProgramSchema,
  mapZodIssues,
} from "../program-editor/programValidation";
import { SolarEditorCanvas } from "../solar-editor/SolarEditorCanvas";
import { validateSolar } from "../solar-editor/solarValidation";
import { createDefaultProgram, createDefaultSolar } from "./projectDefaults";

type ProjectCreateDialogProps = {
  isOpen: boolean;
  onClose: () => void;
};

function inputClasses() {
  return "mt-2 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-accent)]";
}

export function ProjectCreateDialog({
  isOpen,
  onClose,
}: ProjectCreateDialogProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [activeTab, setActiveTab] = useState<"site" | "program">("site");
  const [solar, setSolar] = useState<Solar>(createDefaultSolar());
  const [program, setProgram] = useState<Program>(createDefaultProgram());

  useEffect(() => {
    if (!isOpen) {
      setProjectName("");
      setDescription("");
      setActiveTab("site");
      setSolar(createDefaultSolar());
      setProgram(createDefaultProgram());
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeydown);
    return () => {
      window.removeEventListener("keydown", handleKeydown);
    };
  }, [isOpen, onClose]);

  const solarValidation = validateSolar(solar.contour.points);
  const programSchema = useMemo(() => createProgramSchema(t), [t]);
  const isSolarHeightValid =
    Number.isFinite(solar.max_buildable_height_m) &&
    solar.max_buildable_height_m > 0;
  const programValidation = programSchema.safeParse(program);
  const programValidationMessage = !programValidation.success
    ? (() => {
        const issues = mapZodIssues(programValidation.error);
        return (
          issues.root ?? Object.values(issues)[0] ?? t("project_create.error")
        );
      })()
    : null;
  const validationMessage = !isSolarHeightValid
    ? t("program_editor.validation.positive_number")
    : !solarValidation.valid
      ? t("solar_editor.save_invalid")
      : programValidationMessage;

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!isSolarHeightValid) {
        throw new Error(t("program_editor.validation.positive_number"));
      }

      if (!solarValidation.valid) {
        throw new Error(t("solar_editor.save_invalid"));
      }

      const validatedProgram = programSchema.safeParse(program);
      if (!validatedProgram.success) {
        const issues = mapZodIssues(validatedProgram.error);
        throw new Error(
          issues.root ?? Object.values(issues)[0] ?? t("project_create.error"),
        );
      }

      return createProject({
        name: projectName,
        description: description || null,
        solar,
        program: validatedProgram.data,
      });
    },
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.setQueryData(["project", project.id], project);
      navigate(`/projekte/${project.id}`);
    },
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--color-ink)]/28 px-4 py-8 backdrop-blur-sm">
      <div className="panel-surface flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] p-6 md:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--color-accent)]">
              {t("project_create.eyebrow")}
            </p>
            <div>
              <h2 className="text-3xl font-semibold tracking-[-0.04em] text-[color:var(--color-ink)]">
                {t("project_create.title")}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--color-mist)]">
                {t("project_create.description")}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-accent)]"
            aria-label={t("common.close")}
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-6 flex-1 overflow-y-auto pr-1">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium text-[color:var(--color-ink)]">
              {t("project_create.fields.name")}
              <input
                autoFocus
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                className={inputClasses()}
              />
            </label>

            <label className="text-sm font-medium text-[color:var(--color-ink)] md:row-span-2">
              {t("project_create.fields.description")}
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={5}
                className={inputClasses()}
              />
            </label>

            <label className="text-sm font-medium text-[color:var(--color-ink)]">
              {t("solar_editor.max_height")}
              <input
                type="number"
                min={0}
                step={0.5}
                value={solar.max_buildable_height_m}
                onChange={(event) =>
                  setSolar((current) => ({
                    ...current,
                    max_buildable_height_m: Math.max(
                      0,
                      Number(event.target.value),
                    ),
                  }))
                }
                className={inputClasses()}
              />
            </label>
          </div>

          <div className="mt-6 flex flex-wrap gap-3 border-b border-[color:var(--color-line)] pb-5">
            {(["site", "program"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={[
                  "rounded-full border px-4 py-2 text-sm font-semibold transition",
                  activeTab === tab
                    ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                    : "border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)]",
                ].join(" ")}
              >
                {tab === "site"
                  ? t("project_editor.tabs.site")
                  : t("project_editor.tabs.program")}
              </button>
            ))}
          </div>

          <div className="mt-6 space-y-5">
            {activeTab === "site" ? (
              <div className="overflow-x-auto">
                <SolarEditorCanvas
                  points={solar.contour.points}
                  northAngleDeg={solar.north_angle_deg}
                  onChange={(points) =>
                    setSolar((current) => ({
                      ...current,
                      contour: { points },
                    }))
                  }
                  onNorthAngleChange={(deg) =>
                    setSolar((current) => ({
                      ...current,
                      north_angle_deg: deg,
                    }))
                  }
                />
              </div>
            ) : (
              <ProgramEditorForm program={program} onChange={setProgram} />
            )}
          </div>

          {validationMessage ? (
            <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              {validationMessage}
            </div>
          ) : null}

          {createMutation.isError && !validationMessage ? (
            <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : t("project_create.error")}
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap justify-end gap-3 border-t border-[color:var(--color-line)] pt-6">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[color:var(--color-line)] px-5 py-3 text-sm font-semibold text-[color:var(--color-ink)]"
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={
              createMutation.isPending ||
              projectName.trim().length === 0 ||
              !isSolarHeightValid ||
              !solarValidation.valid ||
              !programValidation.success
            }
            className="rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#143f50] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("project_create.submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
