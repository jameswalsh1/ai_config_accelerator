import { useState, useEffect, useCallback } from 'react'
import { History, GitCompareArrows, ChevronDown, ChevronRight, Clock, User } from 'lucide-react'
import {
  fetchVersionHistory,
  fetchVersionDiff,
  type VersionMeta,
  type AuditDiff,
} from '@/api/wizardApi'
import { StepDiffPanel } from './AuditDiffPanels'

interface VersionHistoryProps {
  scope: string
  target: string
}

export function VersionHistory({ scope, target }: VersionHistoryProps) {
  const [versions, setVersions] = useState<VersionMeta[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  // Diff state
  const [v1, setV1] = useState<number | null>(null)
  const [v2, setV2] = useState<number | null>(null)
  const [diff, setDiff] = useState<AuditDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!scope || !target) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchVersionHistory(scope, target)
      setVersions(data)
      // Default: compare latest two if available
      if (data.length >= 2) {
        setV1(data[1].version)
        setV2(data[0].version)
      } else {
        setV1(null)
        setV2(null)
      }
      setDiff(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }, [scope, target])

  useEffect(() => {
    if (open) {
      void load()
    }
  }, [open, load])

  const handleCompare = async () => {
    if (v1 == null || v2 == null) return
    setDiffLoading(true)
    setDiffError(null)
    setDiff(null)
    try {
      const result = await fetchVersionDiff(scope, target, v1, v2)
      setDiff(result.diff as unknown as AuditDiff)
    } catch (err) {
      setDiffError(err instanceof Error ? err.message : 'Failed to load diff')
    } finally {
      setDiffLoading(false)
    }
  }

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts)
      return d.toLocaleString(undefined, {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return ts }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          <History className="size-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-900">Version History</span>
          {versions.length > 0 && (
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
              {versions.length}
            </span>
          )}
        </div>
        {open ? <ChevronDown className="size-4 text-gray-400" /> : <ChevronRight className="size-4 text-gray-400" />}
      </button>

      {open && (
        <div className="border-t border-gray-100 px-4 py-3 space-y-4">
          {loading && (
            <p className="text-sm text-gray-400">Loading history…</p>
          )}

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          {!loading && versions.length === 0 && !error && (
            <p className="text-sm text-gray-400">No versions recorded yet. Changes will appear here after the first edit.</p>
          )}

          {versions.length > 0 && (
            <>
              {/* Version list */}
              <div className="max-h-48 overflow-y-auto rounded border border-gray-100">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-3 py-1.5 text-left font-medium text-gray-500">v#</th>
                      <th className="px-3 py-1.5 text-left font-medium text-gray-500">Date</th>
                      <th className="px-3 py-1.5 text-left font-medium text-gray-500">Author</th>
                      <th className="px-3 py-1.5 text-left font-medium text-gray-500">Summary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {versions.map(v => (
                      <tr key={v.version} className="hover:bg-gray-50">
                        <td className="px-3 py-1.5 font-mono text-xs text-indigo-600">v{v.version}</td>
                        <td className="px-3 py-1.5 text-gray-600 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="size-3 text-gray-400" />
                            {formatTime(v.timestamp)}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-gray-600">
                          <span className="inline-flex items-center gap-1">
                            <User className="size-3 text-gray-400" />
                            {v.actor}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-gray-500 truncate max-w-[200px]" title={v.summary}>
                          {v.summary || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Diff picker */}
              {versions.length >= 2 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <label className="text-xs font-medium text-gray-500">Compare</label>
                  <select
                    value={v1 ?? ''}
                    onChange={e => { setV1(Number(e.target.value)); setDiff(null) }}
                    className="rounded border border-gray-300 px-2 py-1 text-sm"
                  >
                    {versions.map(v => (
                      <option key={v.version} value={v.version}>v{v.version}</option>
                    ))}
                  </select>
                  <GitCompareArrows className="size-4 text-gray-400" />
                  <select
                    value={v2 ?? ''}
                    onChange={e => { setV2(Number(e.target.value)); setDiff(null) }}
                    className="rounded border border-gray-300 px-2 py-1 text-sm"
                  >
                    {versions.map(v => (
                      <option key={v.version} value={v.version}>v{v.version}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => { void handleCompare() }}
                    disabled={v1 === v2 || diffLoading}
                    className="rounded bg-indigo-600 px-3 py-1 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {diffLoading ? 'Loading…' : 'Show Diff'}
                  </button>
                </div>
              )}

              {/* Diff display */}
              {diffError && (
                <p className="text-sm text-red-600">{diffError}</p>
              )}

              {diff && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-700">
                    Changes from v{v1} → v{v2}
                  </h4>
                  {diff.total_changes === 0 ? (
                    <p className="text-sm text-gray-400">No differences found.</p>
                  ) : (
                    <div className="space-y-2">
                      {diff.steps?.added?.length > 0 && (
                        <div className="text-sm text-green-700">
                          Steps added: {diff.steps.added.join(', ')}
                        </div>
                      )}
                      {diff.steps?.removed?.length > 0 && (
                        <div className="text-sm text-red-700">
                          Steps removed: {diff.steps.removed.join(', ')}
                        </div>
                      )}
                      {diff.steps?.modified?.map(sd => (
                        <StepDiffPanel key={sd.id} sd={sd} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
