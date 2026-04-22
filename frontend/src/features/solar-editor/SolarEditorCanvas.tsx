import { Fragment, useEffect, useRef, useState } from "react";
import { Circle, Layer, Line, Stage, Text } from "react-konva";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { KonvaEventObject } from "konva/lib/Node";
import type { Point2D } from "../../types/project";
import { clamp, formatArea } from "../../utils/format";
import {
  isSelfIntersecting,
  polygonAreaM2,
  validateSolar,
} from "./solarValidation";
import { NorthCompass } from "./NorthCompass";

// ---------------------------------------------------------------------------
// Typen & Konstanten
// ---------------------------------------------------------------------------

type SolarEditorCanvasProps = {
  points: Point2D[];
  northAngleDeg: number;
  gridStep?: number;
  onChange: (points: Point2D[]) => void;
  onNorthAngleChange: (deg: number) => void;
};

const CANVAS_W = 580;
const CANVAS_H = 460;
const PADDING = 60;

const VERTEX_RADIUS = 8;
const GRID_COLOR = "rgba(24,36,45,0.07)";
const POLYGON_FILL = "rgba(24,78,99,0.10)";
const POLYGON_STROKE = "#184e63";
const VERTEX_COLOR = "#225b55";
const VERTEX_HOVER_COLOR = "#184e63";
const DIM_COLOR = "#5f6d76";
const NORTH_ARROW_COLOR = "#c96842";

// ---------------------------------------------------------------------------
// Hilfsfunktionen
// ---------------------------------------------------------------------------

function edgeLength(a: Point2D, b: Point2D): number {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
}

function snapToGrid(p: Point2D, step: number): Point2D {
  return {
    x: Math.round(p.x / step) * step,
    y: Math.round(p.y / step) * step,
  };
}

function computeAutoScale(pts: Point2D[]): number {
  const fallback = [
    { x: 0, y: 0 },
    { x: 20, y: 30 },
  ];
  const source = pts.length >= 2 ? pts : fallback;
  const xs = source.map((p) => p.x);
  const ys = source.map((p) => p.y);
  const w = Math.max(Math.max(...xs) - Math.min(...xs), 1);
  const h = Math.max(Math.max(...ys) - Math.min(...ys), 1);
  return Math.min((CANVAS_W - 2 * PADDING) / w, (CANVAS_H - 2 * PADDING) / h);
}

// ---------------------------------------------------------------------------
// Komponente
// ---------------------------------------------------------------------------

export function SolarEditorCanvas({
  points,
  northAngleDeg,
  gridStep = 1,
  onChange,
  onNorthAngleChange,
}: SolarEditorCanvasProps) {
  const { t } = useTranslation();
  const [snapStep, setSnapStep] = useState(gridStep);
  const [zoom, setZoom] = useState(1.0);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [hoverCanvas, setHoverCanvas] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const stageRef = useRef<import("konva/lib/Stage").Stage | null>(null);

  useEffect(() => {
    setSnapStep(gridStep);
  }, [gridStep]);

  // --- Koordinatentransform ---
  const allPoints =
    points.length >= 2
      ? points
      : [
          { x: 0, y: 0 },
          { x: 20, y: 30 },
        ];
  const xs = allPoints.map((p) => p.x);
  const ys = allPoints.map((p) => p.y);
  const worldCx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const worldCy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const scale = computeAutoScale(points) * zoom;

  const toCanvas = (p: Point2D) => ({
    x: CANVAS_W / 2 + (p.x - worldCx) * scale,
    y: CANVAS_H / 2 - (p.y - worldCy) * scale,
  });

  const fromCanvas = (cx: number, cy: number): Point2D => ({
    x: (cx - CANVAS_W / 2) / scale + worldCx,
    y: -(cy - CANVAS_H / 2) / scale + worldCy,
  });

  // --- Gitterlinien ---
  const gridLines: Array<[number, number, number, number]> = [];
  const visXMin = worldCx - CANVAS_W / 2 / scale;
  const visXMax = worldCx + CANVAS_W / 2 / scale;
  const visYMin = worldCy - CANVAS_H / 2 / scale;
  const visYMax = worldCy + CANVAS_H / 2 / scale;

  const xStart = Math.floor(visXMin / snapStep) * snapStep;
  for (let wx = xStart; wx <= visXMax; wx += snapStep) {
    const cx = toCanvas({ x: wx, y: 0 }).x;
    gridLines.push([cx, 0, cx, CANVAS_H]);
  }
  const yStart = Math.floor(visYMin / snapStep) * snapStep;
  for (let wy = yStart; wy <= visYMax; wy += snapStep) {
    const cy = toCanvas({ x: 0, y: wy }).y;
    gridLines.push([0, cy, CANVAS_W, cy]);
  }

  // --- Polygondaten ---
  const flat = points.flatMap((p) => {
    const c = toCanvas(p);
    return [c.x, c.y];
  });

  const area = polygonAreaM2(points);
  const validation = validateSolar(points);
  const selfCrossing = isSelfIntersecting(points);

  // --- Nordpfeil (Ecke oben links) ---
  const northRad = ((northAngleDeg - 90) * Math.PI) / 180;
  const arrowR = 22;
  const arrowCx = 38;
  const arrowCy = 38;
  const arrowTipX = arrowCx + arrowR * Math.cos(northRad);
  const arrowTipY = arrowCy + arrowR * Math.sin(northRad);
  const arrowTailX = arrowCx - arrowR * 0.5 * Math.cos(northRad);
  const arrowTailY = arrowCy - arrowR * 0.5 * Math.sin(northRad);

  // --- Events ---
  const handleStageClick = (e: KonvaEventObject<MouseEvent>) => {
    // Klick auf Vertex wird von den Circle-Handlern abgefangen
    if (e.target !== e.target.getStage()) return;
    const pos = e.target.getStage()?.getPointerPosition();
    if (!pos) return;
    const world = fromCanvas(pos.x, pos.y);
    const snapped = snapToGrid(world, snapStep);
    onChange([...points, snapped]);
  };

  const handleMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    const pos = e.target.getStage()?.getPointerPosition();
    if (pos) setHoverCanvas(pos);
  };

  const handleMouseLeave = () => setHoverCanvas(null);

  const handleVertexDrag = (index: number, e: KonvaEventObject<MouseEvent>) => {
    const raw = fromCanvas(
      clamp(e.target.x(), PADDING / 2, CANVAS_W - PADDING / 2),
      clamp(e.target.y(), PADDING / 2, CANVAS_H - PADDING / 2),
    );
    const snapped = snapToGrid(raw, snapStep);
    const next = [...points];
    next[index] = snapped;
    onChange(next);
  };

  // Snapped hover-Punkt für Cursor-Vorschau
  const hoverSnapped = hoverCanvas
    ? snapToGrid(fromCanvas(hoverCanvas.x, hoverCanvas.y), snapStep)
    : null;
  const hoverC = hoverSnapped ? toCanvas(hoverSnapped) : null;

  // --- Kantenbeschriftungen (Maßzahlen) ---
  const dimLabels =
    points.length >= 2
      ? points.map((p, i) => {
          const next = points[(i + 1) % points.length];
          const len = edgeLength(p, next);
          const cp = toCanvas(p);
          const cn = toCanvas(next);
          const midX = (cp.x + cn.x) / 2;
          const midY = (cp.y + cn.y) / 2;
          const dx = cn.x - cp.x;
          const dy = cn.y - cp.y;
          const edgeLen = Math.sqrt(dx * dx + dy * dy) || 1;
          // Beschriftung senkrecht zur Kante, nach außen versetzt
          const offsetX = (-dy / edgeLen) * 14;
          const offsetY = (dx / edgeLen) * 14;
          return {
            x: midX + offsetX,
            y: midY + offsetY,
            text: `${len.toFixed(1)} m`,
          };
        })
      : [];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (points.length === 0) return;
            const last = points[points.length - 1];
            const next = snapToGrid(
              { x: last.x + snapStep, y: last.y },
              snapStep,
            );
            onChange([...points, next]);
          }}
          className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-4 py-2 text-sm font-medium text-[color:var(--color-ink)] transition hover:border-[color:var(--color-accent)]"
        >
          {t("solar_editor.point_add")}
        </button>

        <button
          type="button"
          disabled={points.length === 0}
          onClick={() => onChange(points.slice(0, -1))}
          className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] bg-white/80 px-4 py-2 text-sm font-medium text-[color:var(--color-ink)] transition hover:border-amber-300 hover:text-amber-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t("solar_editor.point_remove")}
        </button>

        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}
            className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)]"
            aria-label="Herauszoomen"
          >
            <Minus size={14} />
          </button>
          <span className="w-12 text-center text-xs tabular-nums text-[color:var(--color-mist)]">
            {Math.round(zoom * 100)} %
          </span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
            className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)]"
            aria-label="Hineinzoomen"
          >
            <Plus size={14} />
          </button>
          <button
            type="button"
            onClick={() => setZoom(1)}
            className="rounded-full border border-[color:var(--color-line)] p-2 text-[color:var(--color-mist)] transition hover:border-[color:var(--color-accent)]"
            aria-label={t("solar_editor.zoom_reset")}
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Canvas + Seitenleiste */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_200px]">
        {/* Zeichenfläche */}
        <div
          className="grid-paper overflow-hidden rounded-[1.5rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)]"
          style={{ cursor: "crosshair" }}
        >
          <Stage
            ref={stageRef}
            width={CANVAS_W}
            height={CANVAS_H}
            onClick={handleStageClick}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          >
            <Layer>
              {/* Gitterlinien */}
              {gridLines.map(([x1, y1, x2, y2], i) => (
                <Line
                  key={`grid-${i}`}
                  points={[x1, y1, x2, y2]}
                  stroke={GRID_COLOR}
                  strokeWidth={1}
                  listening={false}
                />
              ))}

              {/* Polygon */}
              {points.length >= 2 && (
                <Line
                  points={flat}
                  closed={points.length >= 3}
                  fill={selfCrossing ? "rgba(201,104,66,0.12)" : POLYGON_FILL}
                  stroke={selfCrossing ? "#c96842" : POLYGON_STROKE}
                  strokeWidth={2.5}
                  listening={false}
                />
              )}

              {/* Maßzahlen */}
              {points.length >= 2 &&
                dimLabels.map((label, i) => (
                  <Text
                    key={`dim-${i}`}
                    x={label.x - 24}
                    y={label.y - 8}
                    width={48}
                    align="center"
                    text={label.text}
                    fontSize={10}
                    fill={DIM_COLOR}
                    listening={false}
                  />
                ))}

              {/* Vertices */}
              {points.map((p, i) => {
                const c = toCanvas(p);
                const isFirst = i === 0;
                return (
                  <Fragment key={`v-${i}`}>
                    <Circle
                      x={c.x}
                      y={c.y}
                      radius={isFirst ? VERTEX_RADIUS + 2 : VERTEX_RADIUS}
                      fill={
                        hoveredIndex === i ? VERTEX_HOVER_COLOR : VERTEX_COLOR
                      }
                      stroke={isFirst ? "#c96842" : "white"}
                      strokeWidth={isFirst ? 2 : 1.5}
                      draggable
                      onMouseEnter={() => setHoveredIndex(i)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      onDragMove={(e) => handleVertexDrag(i, e)}
                    />
                    <Text
                      x={c.x + 12}
                      y={c.y - 20}
                      text={`P${i + 1}`}
                      fontSize={11}
                      fill="#1c2731"
                      listening={false}
                    />
                  </Fragment>
                );
              })}

              {/* Cursor-Vorschau (nächster Punkt) */}
              {hoverC && (
                <Circle
                  x={hoverC.x}
                  y={hoverC.y}
                  radius={5}
                  fill="rgba(24,78,99,0.35)"
                  listening={false}
                />
              )}

              {/* Nordpfeil */}
              <Line
                points={[arrowTailX, arrowTailY, arrowTipX, arrowTipY]}
                stroke={NORTH_ARROW_COLOR}
                strokeWidth={2}
                listening={false}
              />
              <Circle
                x={arrowTipX}
                y={arrowTipY}
                radius={4}
                fill={NORTH_ARROW_COLOR}
                listening={false}
              />
              <Text
                x={arrowCx - 6}
                y={arrowCy + arrowR + 4}
                text="N"
                fontSize={10}
                fontStyle="600"
                fill={NORTH_ARROW_COLOR}
                listening={false}
              />
              <Circle
                x={arrowCx}
                y={arrowCy}
                radius={arrowR + 8}
                fill="transparent"
                listening={false}
              />
            </Layer>
          </Stage>
        </div>

        {/* Seitenleiste */}
        <div className="flex flex-col gap-4">
          {/* Fläche */}
          <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("solar_editor.area")}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
              {formatArea(area)}
            </p>
          </div>

          {/* Eckpunkte */}
          <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("solar_editor.vertices")}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">
              {points.length}
            </p>
          </div>

          {/* Rasterweite */}
          <div className="rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("solar_editor.grid_snap")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {[0.5, 1, 2, 5].map((step) => (
                <button
                  key={step}
                  type="button"
                  onClick={() => {
                    setSnapStep(step);
                    onChange(points.map((p) => snapToGrid(p, step)));
                  }}
                  className={[
                    "rounded-full border px-3 py-1 text-xs font-semibold transition",
                    snapStep === step
                      ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                      : "border-[color:var(--color-line)] bg-white/70 text-[color:var(--color-mist)]",
                  ].join(" ")}
                >
                  {step} m
                </button>
              ))}
            </div>
          </div>

          {/* Nordausrichtung */}
          <div className="flex items-center justify-center rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
            <NorthCompass
              angleDeg={northAngleDeg}
              onChange={onNorthAngleChange}
            />
          </div>

          {/* OSM Import (TODO) */}
          <div className="rounded-[1.5rem] border border-dashed border-[color:var(--color-line)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t("solar_editor.osm_import")}
            </p>
            <p className="mt-2 text-xs leading-5 text-[color:var(--color-mist)]">
              {/* TODO Fase futura: importar contorno desde OpenStreetMap */}
              {t("solar_editor.osm_todo")}
            </p>
          </div>
        </div>
      </div>

      {/* Validierungsmeldungen */}
      {!validation.valid && (
        <div className="space-y-2">
          {validation.errors.tooFewPoints && (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-700">
              {t("solar_editor.validation.too_few_points")}
            </p>
          )}
          {validation.errors.selfIntersecting && (
            <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
              {t("solar_editor.validation.self_intersecting")}
            </p>
          )}
          {validation.errors.tooSmall && (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-700">
              {t("solar_editor.validation.polygon_too_small")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
