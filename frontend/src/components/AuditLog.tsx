import { useEffect, useState, useCallback } from 'react'
import {
  Clock,
  ChevronDown,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import {
  fetchAuditLog,
  type AuditEntry,
} from '@/api/wizardApi'
import { ActionBadge, ScopeBadge, DiffRow, StepDiffPanel } from './AuditDiffPanels'

const PAGE_SIZE = 20

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string): { date: string; time: string } {
  const d = new Date(iso)
  return {
    date: d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
    time: d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  }
}

// ---------------------------------------------------------------------------
// Single audit entry row
// ---------------------------------------------------------------------------
function AuditEntryRow({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false)
  const { date, time } = formatTimestamp(entry.timestamp)
  const diff = entry.diff
  const hasChanges = diff?.has_changes

  const modifiedSteps = diff?.steps?.modified?.filter(sd => {
    const fields = (sd.fields?.modified ?? []).filter(
      fd =>
        fd.value?.changed ||
        fd.label?.changed ||
        fd.description?.changed ||
        fd.hidden?.changed ||
        (fd.presets?.length ?? 0) > 0 ||
        fd.locking != null,
    )
    return (
      fields.length > 0 ||
      (sd.fields?.added?.length ?? 0) > 0 ||
      (sd.fields?.removed?.length ?? 0) > 0 ||
      sd.title?.changed ||
      sd.description?.changed
    )
  }) ?? []

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex-shrink-0 mt-0.5">
          {open ? (
            <ChevronDown className="size-4 text-gray-400" />
          ) : (
            <ChevronRight className="size-4 text-gray-400" />
          )}
        </div>

        {/* Timestamp */}
        <div className="flex-shrink-0 text-right w-28">
          <p className="text-xs font-medium text-gray-700">{date}</p>
          <p className="text-xs text-gray-400 font-mono">{time}</p>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
          <ActionBadge action={entry.action} />
          <ScopeBadge scope={entry.scope} />
        </div>

        {/* File + summary */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{entry.target}</p>
          <p className="text-xs text-gray-400 font-mono truncate mt-0.5">{entry.file}</p>
          {entry.diff_summary && entry.diff_summary !== 'no changes' && (
            <p className="text-xs text-gray-600 mt-1 italic">{entry.diff_summary}</p>
          )}
        </div>

        {/* Change count */}
        <div className="flex-shrink-0 text-right">
          {hasChanges ? (
            <span className="inline-block px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">
              {diff.total_changes} change{diff.total_changes !== 1 ? 's' : ''}
            </span>
          ) : (
            <span className="text-xs text-gray-400 italic">no diff</span>
          )}
        </div>
      </button>

      {/* Expanded diff */}
      {open && (
        <div className="border-t border-gray-100 px-5 py-4 bg-gray-50 space-y-4">
          {/* Metadata */}
          <div className="flex flex-wrap gap-4 text-xs text-gray-500">
            <span><strong className="text-gray-700">Actor:</strong> {entry.actor}</span>
            <span><strong className="text-gray-700">File:</strong> <code className="font-mono">{entry.file}</code></span>
          </div>

          {!hasChanges && (
            <p className="text-sm text-gray-400 italic">
              {entry.action === 'create'
                ? 'New file created — no previous version to diff against.'
                : 'No structural changes detected in this save.'}
            </p>
          )}

          {/* Config-level metadata changes */}
          {(diff?.metadata_changes?.title?.changed || diff?.metadata_changes?.description?.changed) && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Config metadata</p>
              {diff.metadata_changes.title?.changed && (
                <DiffRow label="Title" before={diff.metadata_changes.title.before} after={diff.metadata_changes.title.after} />
              )}
              {diff.metadata_changes.description?.changed && (
                <DiffRow label="Description" before={diff.metadata_changes.description.before} after={diff.metadata_changes.description.after} />
              )}
            </div>
          )}

          {/* Added / removed steps */}
          {(diff?.steps?.added?.length ?? 0) > 0 && (
            <div className="rounded bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-800">
              <strong>Steps added:</strong> {diff.steps.added.join(', ')}
            </div>
          )}
          {(diff?.steps?.removed?.length ?? 0) > 0 && (
            <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
              <strong>Steps removed:</strong> {diff.steps.removed.join(', ')}
            </div>
          )}

          {/* Modified steps */}
          {modifiedSteps.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Changed steps</p>
              {modifiedSteps.map(sd => (
                <StepDiffPanel key={sd.id} sd={sd} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [scopeFilter, setScopeFilter] = useState('')
  const [targetFilter, setTargetFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (pg: number, scope: string, target: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchAuditLog({
        limit: PAGE_SIZE,
        offset: pg * PAGE_SIZE,
        scope: scope || undefined,
        target: target || undefined,
      })
      setEntries(result.entries)
      setTotal(result.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(page, scopeFilter, targetFilter)
  }, [page, scopeFilter, targetFilter, load])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleFilterChange = (scope: string, target: string) => {
    setPage(0)
    setScopeFilter(scope)
    setTargetFilter(target)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Audit Log</h2>
          <p className="text-sm text-gray-500 mt-1">
            Every configuration change, with a full field-level diff.
          </p>
        </div>
        <button
          onClick={() => { void load(page, scopeFilter, targetFilter) }}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={scopeFilter}
          onChange={e => handleFilterChange(e.target.value, targetFilter)}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All scopes</option>
          <option value="language">Language</option>
          <option value="tool">Tool</option>
          <option value="override">Override</option>
        </select>
        <input
          type="text"
          value={targetFilter}
          onChange={e => handleFilterChange(scopeFilter, e.target.value)}
          placeholder="Filter by target (e.g. python)"
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 w-56"
        />
        {(scopeFilter || targetFilter) && (
          <button
            onClick={() => handleFilterChange('', '')}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && entries.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-16 text-center">
          <Clock className="size-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No audit entries yet</p>
          <p className="text-sm text-gray-400 mt-1">
            Changes made via the Config Editor will appear here.
          </p>
        </div>
      )}

      {/* Entry list */}
      {entries.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            {total} total entr{total !== 1 ? 'ies' : 'y'}
            {(scopeFilter || targetFilter) ? ' (filtered)' : ''}
          </p>
          {entries.map((entry, i) => (
            <AuditEntryRow key={`${entry.timestamp}-${i}`} entry={entry} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0 || loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1 || loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
