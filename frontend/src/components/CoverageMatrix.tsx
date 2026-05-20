import { useCallback, useEffect, useState } from 'react'
import { Loader2, RefreshCw, AlertCircle, CheckCircle2, CircleDot, Circle } from 'lucide-react'
import { fetchCoverageMatrix, type CoverageMatrix, type CoverageStatus } from '@/api/wizardApi'

interface CoverageMatrixProps {
  /** Called when the user clicks a cell to open the config editor for that combination. */
  onNavigateToEditor?: (toolId: string, languageId: string) => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<CoverageStatus, { label: string; bg: string; border: string; text: string; icon: React.ElementType }> = {
  full:    { label: 'Full coverage',    bg: 'bg-emerald-50',  border: 'border-emerald-300', text: 'text-emerald-700', icon: CheckCircle2 },
  partial: { label: 'Partial coverage', bg: 'bg-amber-50',   border: 'border-amber-300',   text: 'text-amber-700',  icon: CircleDot     },
  none:    { label: 'No coverage',      bg: 'bg-gray-50',    border: 'border-gray-200',    text: 'text-gray-400',   icon: Circle        },
}

interface CellProps {
  status: CoverageStatus
  fieldCount: number
  fields: string[]
  toolTitle: string
  languageTitle: string
  onClick?: () => void
}

function Cell({ status, fieldCount, fields, toolTitle, languageTitle, onClick }: CellProps) {
  const [showTip, setShowTip] = useState(false)
  const cfg = STATUS_CONFIG[status]
  const Icon = cfg.icon

  return (
    <div className="relative flex items-center justify-center">
      <button
        type="button"
        onClick={onClick}
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        onFocus={() => setShowTip(true)}
        onBlur={() => setShowTip(false)}
        className={`
          flex h-10 w-full items-center justify-center gap-1.5 rounded-lg border
          text-xs font-medium transition-all
          ${cfg.bg} ${cfg.border} ${cfg.text}
          ${onClick ? 'cursor-pointer hover:brightness-95 hover:shadow-sm' : 'cursor-default'}
        `}
        aria-label={`${toolTitle} × ${languageTitle}: ${cfg.label} (${fieldCount} field${fieldCount !== 1 ? 's' : ''})`}
      >
        <Icon className="size-3.5 shrink-0" />
        <span>{fieldCount}</span>
      </button>

      {/* Tooltip */}
      {showTip && (
        <div className="absolute bottom-full left-1/2 z-30 mb-2 -translate-x-1/2 w-56 rounded-lg border border-gray-200 bg-white p-3 shadow-lg text-left pointer-events-none">
          <p className={`text-xs font-semibold mb-1 ${cfg.text}`}>{cfg.label}</p>
          <p className="text-xs text-gray-500 mb-1">
            {toolTitle} × {languageTitle}
          </p>
          {fields.length > 0 ? (
            <ul className="space-y-0.5">
              {fields.map(f => (
                <li key={f} className="text-xs font-mono text-gray-600 truncate">{f}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400 italic">No language-specific field overrides</p>
          )}
          {onClick && (
            <p className="mt-2 text-xs text-indigo-500">Click to open in Config Editor →</p>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------

function SummaryBar({ matrix, tools, languages }: {
  matrix: CoverageMatrix['matrix']
  tools: CoverageMatrix['tools']
  languages: CoverageMatrix['languages']
}) {
  let full = 0, partial = 0, none = 0
  for (const tool of tools) {
    for (const lang of languages) {
      const s = matrix[tool.id]?.[lang.id]?.status ?? 'none'
      if (s === 'full') full++
      else if (s === 'partial') partial++
      else none++
    }
  }
  const total = full + partial + none
  const fullPct = total > 0 ? Math.round((full / total) * 100) : 0
  const partialPct = total > 0 ? Math.round((partial / total) * 100) : 0
  const nonePct = 100 - fullPct - partialPct

  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-3.5 shadow-sm text-sm">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Coverage</span>
      <div className="flex-1 flex h-2.5 rounded-full overflow-hidden gap-px">
        <div className="bg-emerald-400 transition-all" style={{ width: `${fullPct}%` }} />
        <div className="bg-amber-400 transition-all" style={{ width: `${partialPct}%` }} />
        <div className="bg-gray-200 transition-all" style={{ width: `${nonePct}%` }} />
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1 text-emerald-700">
          <span className="inline-block size-2 rounded-full bg-emerald-400" />
          {full} full
        </span>
        <span className="flex items-center gap-1 text-amber-700">
          <span className="inline-block size-2 rounded-full bg-amber-400" />
          {partial} partial
        </span>
        <span className="flex items-center gap-1 text-gray-500">
          <span className="inline-block size-2 rounded-full bg-gray-300" />
          {none} none
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CoverageMatrix({ onNavigateToEditor }: CoverageMatrixProps) {
  const [data, setData] = useState<CoverageMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchCoverageMatrix()
      .then(result => {
        setData(result)
        setError(null)
        setLoading(false)
      })
      .catch(e => {
        setError(e instanceof Error ? e.message : 'Failed to load coverage matrix')
        setLoading(false)
      })
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Language Coverage Matrix</h2>
          <p className="mt-1 text-sm text-gray-500">
            Shows which languages have field overrides configured for each tool's visible steps.
            Click any cell to open that combination in the Config Editor.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Loading */}
      {loading && !data && (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="size-6 animate-spin mr-2" />
          <span className="text-sm">Loading coverage data…</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Matrix */}
      {data && (
        <>
          <SummaryBar matrix={data.matrix} tools={data.tools} languages={data.languages} />

          <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {/* Row header spacer */}
                  <th className="sticky left-0 z-10 bg-gray-50 border-b border-r border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">
                    Language
                  </th>
                  {data.tools.map(tool => (
                    <th
                      key={tool.id}
                      className="border-b border-gray-200 px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wide whitespace-nowrap min-w-[130px]"
                    >
                      {tool.title.replace(' Configuration', '').replace(' Config', '')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.languages.map((lang, rowIdx) => (
                  <tr key={lang.id} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50/40'}>
                    {/* Language label */}
                    <td className="sticky left-0 z-10 border-r border-gray-200 px-4 py-2.5 font-medium text-gray-800 whitespace-nowrap"
                      style={{ background: rowIdx % 2 === 0 ? 'white' : 'rgb(249 250 251 / 0.4)' }}
                    >
                      {lang.title}
                    </td>
                    {/* Coverage cells */}
                    {data.tools.map(tool => {
                      const cell = data.matrix[tool.id]?.[lang.id] ?? { status: 'none' as CoverageStatus, field_count: 0, fields: [] }
                      return (
                        <td key={tool.id} className="px-3 py-2">
                          <Cell
                            status={cell.status}
                            fieldCount={cell.field_count}
                            fields={cell.fields}
                            toolTitle={tool.title.replace(' Configuration', '').replace(' Config', '')}
                            languageTitle={lang.title}
                            onClick={onNavigateToEditor ? () => onNavigateToEditor(tool.id, lang.id) : undefined}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-5 text-xs text-gray-500">
            <span className="font-medium text-gray-600">Legend:</span>
            {(Object.entries(STATUS_CONFIG) as [CoverageStatus, typeof STATUS_CONFIG[CoverageStatus]][]).map(([status, cfg]) => {
              const Icon = cfg.icon
              return (
                <span key={status} className="flex items-center gap-1.5">
                  <Icon className={`size-3.5 ${cfg.text}`} />
                  <span className={cfg.text}>{cfg.label}</span>
                  <span className="text-gray-400">
                    {status === 'full' && '— ≥ 2 field overrides for this tool'}
                    {status === 'partial' && '— 1 field override for this tool'}
                    {status === 'none' && '— no overrides targeting this tool\'s steps'}
                  </span>
                </span>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
