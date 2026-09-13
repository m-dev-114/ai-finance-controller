export default function TrendChart({ points, valueKey, label, color = 'var(--accent)', formatValue }) {
  const width = 560
  const height = 140
  const padding = { top: 10, right: 12, bottom: 22, left: 12 }

  if (!points || points.length === 0) {
    return (
      <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
        Not enough runs yet to chart {label.toLowerCase()}.
      </div>
    )
  }

  const values = points.map((p) => p[valueKey])
  const maxV = Math.max(...values, 0.0001)
  const minV = Math.min(...values, 0)
  const range = maxV - minV || 1

  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const coords = points.map((p, i) => {
    const x = points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW
    const y = innerH - ((p[valueKey] - minV) / range) * innerH
    return [x + padding.left, y + padding.top]
  })

  const pathD = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 8 }}>
        {label}
      </div>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
        <line x1={padding.left} y1={innerH + padding.top} x2={width - padding.right} y2={innerH + padding.top}
              stroke="var(--line)" strokeWidth="1" />
        <path d={pathD} fill="none" stroke={color} strokeWidth="2" />
        {coords.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="3" fill={color} />
        ))}
        {points.map((p, i) => {
          if (points.length > 1 && i % Math.ceil(points.length / 6) !== 0 && i !== points.length - 1) return null
          const x = coords[i][0]
          return (
            <text key={i} x={x} y={height - 4} fontSize="9" fill="var(--muted)"
                  textAnchor="middle" fontFamily="var(--font-mono)">
              {new Date(p.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            </text>
          )
        })}
      </svg>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink)', marginTop: 2 }}>
        latest: {formatValue ? formatValue(values[values.length - 1]) : values[values.length - 1]}
      </div>
    </div>
  )
}
