import { useTranslation } from "react-i18next";
import type { Program } from "../../types/project";

type ProgramEditorFormProps = {
  program: Program;
  onChange: (program: Program) => void;
};

function parseNumberInput(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function createInputClasses() {
  return "mt-2 w-full rounded-2xl border border-[color:var(--color-line)] bg-white px-4 py-3 text-sm outline-none transition focus:border-[color:var(--color-teal)]";
}

export function ProgramEditorForm({
  program,
  onChange,
}: ProgramEditorFormProps) {
  const { t } = useTranslation();
  const typology = program.typologies[0];
  const mixEntry = program.mix[0];
  const unitsPerFloor = mixEntry.count / Math.max(program.num_floors, 1);

  const updateTypology = (updates: Partial<typeof typology>) => {
    onChange({
      ...program,
      typologies: [
        {
          ...typology,
          ...updates,
        },
      ],
    });
  };

  const updateMixCount = (count: number) => {
    onChange({
      ...program,
      mix: [{ ...mixEntry, count }],
    });
  };

  return (
    <section className="panel-surface rounded-[2rem] p-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-[-0.03em]">
          {t("program_editor.title")}
        </h2>
        <p className="max-w-xl text-sm leading-6 text-[color:var(--color-mist)]">
          {t("program_editor.description")}
        </p>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.typology_name")}
          <input
            value={typology.name}
            onChange={(event) => updateTypology({ name: event.target.value })}
            className={createInputClasses()}
          />
        </label>

        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.floors")}
          <input
            type="number"
            min={1}
            value={program.num_floors}
            onChange={(event) =>
              onChange({
                ...program,
                num_floors: parseNumberInput(event.target.value),
              })
            }
            className={createInputClasses()}
          />
        </label>

        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.floor_height")}
          <input
            type="number"
            min={2.4}
            step={0.1}
            value={program.floor_height_m}
            onChange={(event) =>
              onChange({
                ...program,
                floor_height_m: parseNumberInput(event.target.value),
              })
            }
            className={createInputClasses()}
          />
        </label>

        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.unit_count")}
          <input
            type="number"
            min={1}
            value={mixEntry.count}
            onChange={(event) =>
              updateMixCount(parseNumberInput(event.target.value))
            }
            className={createInputClasses()}
          />
        </label>

        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.min_area")}
          <input
            type="number"
            min={35}
            step={1}
            value={typology.min_useful_area}
            onChange={(event) => {
              const nextMin = parseNumberInput(event.target.value);
              updateTypology({
                min_useful_area: nextMin,
                max_useful_area: Math.max(
                  typology.max_useful_area,
                  nextMin + 4,
                ),
              });
            }}
            className={createInputClasses()}
          />
        </label>

        <label className="text-sm font-medium text-[color:var(--color-ink)]">
          {t("program_editor.max_area")}
          <input
            type="number"
            min={40}
            step={1}
            value={typology.max_useful_area}
            onChange={(event) => {
              const nextMax = parseNumberInput(event.target.value);
              updateTypology({
                max_useful_area: Math.max(
                  nextMax,
                  typology.min_useful_area + 4,
                ),
              });
            }}
            className={createInputClasses()}
          />
        </label>
      </div>

      <div className="mt-5 rounded-[1.5rem] border border-[color:var(--color-line)] bg-[color:var(--color-teal-soft)] px-5 py-4 text-sm text-[color:var(--color-teal)]">
        <p className="font-semibold">{t("program_editor.units_per_floor")}</p>
        <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
          {unitsPerFloor.toFixed(1)}
        </p>
      </div>
    </section>
  );
}
