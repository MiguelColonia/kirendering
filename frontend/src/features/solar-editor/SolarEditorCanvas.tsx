import { Fragment } from 'react'
import { Circle, Layer, Line, Stage, Text } from 'react-konva'
import { useTranslation } from 'react-i18next'
import type { Point2D } from '../../types/project'
import { clamp, formatArea, polygonArea } from '../../utils/format'
import { StatusBadge } from '../../components/StatusBadge'

type SolarEditorCanvasProps = {
  points: Point2D[]
  onChange: (points: Point2D[]) => void
}

const CANVAS_WIDTH = 560
const CANVAS_HEIGHT = 420
const CANVAS_PADDING = 42

export function SolarEditorCanvas({ points, onChange }: SolarEditorCanvasProps) {
  const { t } = useTranslation()
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const availableWidth = CANVAS_WIDTH - CANVAS_PADDING * 2
  const availableHeight = CANVAS_HEIGHT - CANVAS_PADDING * 2
  const scale = Math.min(
    availableWidth / Math.max(maxX - minX, 1),
    availableHeight / Math.max(maxY - minY, 1),
  )

  const toCanvas = (point: Point2D) => ({
    x: CANVAS_PADDING + (point.x - minX) * scale,
    y: CANVAS_HEIGHT - CANVAS_PADDING - (point.y - minY) * scale,
  })

  const fromCanvas = (x: number, y: number): Point2D => ({
    x: Number(((x - CANVAS_PADDING) / scale + minX).toFixed(2)),
    y: Number((((CANVAS_HEIGHT - CANVAS_PADDING - y) / scale) + minY).toFixed(2)),
  })

  const flattenedPoints = points.flatMap((point) => {
    const canvasPoint = toCanvas(point)
    return [canvasPoint.x, canvasPoint.y]
  })

  const area = polygonArea(points)
  const isAreaValid = area >= 120

  return (
    <section className="panel-surface rounded-[2rem] p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-[-0.03em]">{t('solar_editor.title')}</h2>
          <p className="max-w-xl text-sm leading-6 text-[color:var(--color-mist)]">
            {t('solar_editor.description')}
          </p>
        </div>
        <StatusBadge tone={isAreaValid ? 'good' : 'warn'}>
          {isAreaValid
            ? t('solar_editor.validation.polygon_ok')
            : t('solar_editor.validation.polygon_too_small')}
        </StatusBadge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="grid-paper overflow-x-auto rounded-[1.5rem] border border-[color:var(--color-line)] bg-[color:var(--color-paper)] p-4">
          <Stage width={CANVAS_WIDTH} height={CANVAS_HEIGHT}>
            <Layer>
              <Line
                points={flattenedPoints}
                closed
                fill="rgba(201, 104, 66, 0.16)"
                stroke="#c96842"
                strokeWidth={3}
              />
              {points.map((point, index) => {
                const canvasPoint = toCanvas(point)
                return (
                  <Fragment key={`vertex-${index}`}>
                    <Circle
                      x={canvasPoint.x}
                      y={canvasPoint.y}
                      radius={8}
                      fill="#0f766e"
                      draggable
                      onDragMove={(event) => {
                        const nextPoints = [...points]
                        nextPoints[index] = fromCanvas(
                          clamp(event.target.x(), CANVAS_PADDING / 2, CANVAS_WIDTH - CANVAS_PADDING / 2),
                          clamp(event.target.y(), CANVAS_PADDING / 2, CANVAS_HEIGHT - CANVAS_PADDING / 2),
                        )
                        onChange(nextPoints)
                      }}
                    />
                    <Text
                      x={canvasPoint.x + 10}
                      y={canvasPoint.y - 24}
                      text={`P${index + 1}`}
                      fontSize={14}
                      fill="#1c2731"
                    />
                  </Fragment>
                )
              })}
            </Layer>
          </Stage>
        </div>

        <div className="space-y-3 rounded-[1.5rem] border border-[color:var(--color-line)] bg-white/80 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t('solar_editor.area')}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{formatArea(area)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
              {t('solar_editor.vertices')}
            </p>
            <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{points.length}</p>
          </div>
        </div>
      </div>
    </section>
  )
}