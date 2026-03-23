export function getChartColors(theme) {
  const isDark = theme === 'dark'
  return {
    tick: isDark ? '#94a3b8' : '#4a5568',
    grid: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)',
    tooltip: {
      background: isDark ? '#0e1421' : '#ffffff',
      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
      borderRadius: 10,
      fontSize: 13,
      color: isDark ? '#f1f5f9' : '#1a1a2e',
    },
    labelPrimary: isDark ? '#f1f5f9' : '#1a1a2e',
    labelSecondary: isDark ? '#94a3b8' : '#4a5568',
    labelMuted: isDark ? '#c8d0da' : '#334155',
  }
}
