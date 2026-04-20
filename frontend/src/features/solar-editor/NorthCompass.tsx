import { useRef } from 'react'
import { useTranslation } from 'react-i18next'

type NorthCompassProps = {
  angleDeg: number
  onChange: (deg: number) => void
  size?: number
}

export function NorthCompass({ angleDeg, onChange, size = 72 }: NorthCompassProps) {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement>(null)
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 6

  // Richtungsvektor für den Pfeil (0° = oben, im Uhrzeigersinn)
  const rad = ((angleDeg - 90) * Math.PI) / 180
  const tipX = cx + r * Math.cos(rad)
  const tipY = cy + r * Math.sin(rad)
  const tailX = cx - (r * 0.45) * Math.cos(rad)
  const tailY = cy - (r * 0.45) * Math.sin(rad)

  const getAngleFromEvent = (event: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return angleDeg
    const rect = svg.getBoundingClientRect()
    const dx = event.clientX - rect.left - cx
    const dy = event.clientY - rect.top - cy
    // atan2 gibt Winkel im mathematischen Sinn (0° = rechts, CCW positiv)
    // Umrechnung: 0° = oben, CW positiv
    const deg = (Math.atan2(dy, dx) * 180) / Math.PI + 90
    return ((deg % 360) + 360) % 360
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
        {t('solar_editor.north_label')}
      </p>
      <svg
        ref={svgRef}
        width={size}
        height={size}
        className="cursor-pointer select-none"
        onClick={(e) => onChange(Math.round(getAngleFromEvent(e)))}
      >
        {/* Äußerer Ring */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--color-line)" strokeWidth={1.5} />
        {/* Nordpfeil */}
        <line
          x1={tailX}
          y1={tailY}
          x2={tipX}
          y2={tipY}
          stroke="var(--color-accent)"
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        <circle cx={tipX} cy={tipY} r={3} fill="var(--color-accent)" />
        {/* N-Beschriftung */}
        <text
          x={cx}
          y={8}
          textAnchor="middle"
          dominantBaseline="hanging"
          fontSize={9}
          fontWeight="600"
          fill="var(--color-mist)"
          letterSpacing="0.1em"
        >
          N
        </text>
      </svg>
      <p className="text-xs tabular-nums text-[color:var(--color-mist)]">
        {Math.round(angleDeg)}°
      </p>
    </div>
  )
}
