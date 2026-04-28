import { useEffect, useState, useCallback } from 'react'
import {
  Clock,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  FilePlus,
  FilePen,
  AlertCircle,
  Tag,
  ArrowRight,
} from 'lucide-react'
import {
  fetchAuditLog,
  type AuditEntry,
  type AuditFieldDiff,
  type AuditStepDiff,
} from '@/api/wizardApi'

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

function ActionBadge({ action }: { action: AuditEntry['action'] }) {
  const styles = {
    create: 'bg-green-100 text-green-800 border-green-200',
    update: 'bg-blue-100 text-blue-800 border-blue-200',
    delete: 'bg-red-100 text-red-800 border-red-200',
  }
  const icons = {
    create: <FilePlus className="size-3" />,
    update: <FilePen className="size-3" />,
    delete: <AlertCircle className="size-3" />,
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${styles[action] ?? styles.update}`}
    >
      {icons[action]}
      {action}
    </span>
  )
}

function ScopeBadge({ scope }: { scope: string }) {
  const colours: Record<string, string> = {
    language: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    tool: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    override: 'bg-purple-50 text-purple-700 border-purple-200',
    unknown: 'bg-gray-50 text-gray-500 border-gray-200',
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium ${colours[scope] ?? colours.unknown}`}
    >
      <Tag className="size-3" />
      {scope}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Value renderer — handles long strings, objects, booleans gracefully
// ---------------------------------------------------------------------------
function Value({ val, className = '' }: { val: unknown; className?: string }) {
  if (val === null || val === undefined) return <span className={`italic text-gray-400 ${className}`}>—</span>
  const str = typeof val === 'string' ? val : JSON.stringify(val, null, 2)
  return (
    <span className={`font-mono text-xs break-all whitespace-pre-wrap ${className}`}>
      {str || <span className="italic text-gray-400">(empty)</span>}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Inline before → after diff row
// ---------------------------------------------------------------------------
function DiffRow({ label, before, after }: { label: string; before: unknown; after: unknown }) {
  return (
    <div className="grid grid-cols-[160px_1fr_20px_1fr] gap-2 items-start py-1.5 border-b border-gray-100 last:border-0">
      <span className="text-xs font-medium text-gray-500 pt-0.5 truncate" title={label}>{label}</span>
      <div className="rounded bg-red-50 border border-red-100 px-2 py-1.5 min-h-[28px]">
        <Value val={before} className="text-red-800" />
      </div>
      <ArrowRight className="size-4 text-gray-400 mt-1 mx-auto flex-shrink-0" />
      <div className="rounded bg-green-50 border border-green-100 px-2 py-1.5 min-h-[28px]">
        <Value val={after} className="text-green-800" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Field diff panel
// ---------------------------------------------------------------------------
function FieldDiffPanel({ fd }: { fd: AuditFieldDiff }) {
  const [open, setOpen] = useState(false)
  const hasDetail =
    fd.value_changed ||
    fd.label_changed ||
    fd.description_changed ||
    fd.hidden_changed ||
    fd.preset_changes.length > 0 ||
    fd.locking_changes != null

  if (!hasDetail) return null

  return (
    <div className="rounded-md border border-gray-200 bg-white overflow-hidden text-sm">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="size-3.5 text-gray-500" /> : <ChevronRight className="size-3.5 text-gray-500" />}
          <span className="font-medium text-gray-800 font-mono text-xs">{fd.field_id}</span>
          <span className="text-xs text-gray-400">({fd.field_type})</span>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {fd.value_changed && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">value</span>}
          {fd.locking_changes && <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">locking</span>}
          {fd.preset_changes.length > 0 && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">{fd.preset_changes.length} preset{fd.preset_changes.length !== 1 ? 's' : ''}</span>}
          {fd.hidden_changed && <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-700">visibility</span>}
        </div>
      </button>

      {open && (
        <div className="px-3 py-3 space-y-2">
          {fd.value_changed && (
            <DiffRow label="Default value" before={fd.before_value} after={fd.after_value} />
          )}
          {fd.label_changed && (
            <DiffRow label="Label" before={fd.before_label} after={fd.after_label} />
          )}
          {fd.description_changed && (
            <DiffRow label="Description" before={fd.before_description} after={fd.after_description} />
          )}
          {fd.hidden_changed && (
            <DiffRow label="Visible" before={!fd.before_hidden} after={!fd.after_hidden} />
          )}
          {fd.locking_changes && (
            <DiffRow
              label="Editability"
              before={fd.locking_changes.before_state}
              after={fd.locking_changes.after_state}
            />
          )}
          {fd.preset_changes.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1.5">Preset changes</p>
              <div className="space-y-1">
                {fd.preset_changes.map((pc, i) => {
                  const colour =
                    pc.change_type === 'added'
                      ? 'bg-green-50 border-green-200 text-green-800'
                      : pc.change_type === 'removed'
                      ? 'bg-red-50 border-red-200 text-red-800'
                      : 'bg-blue-50 border-blue-200 text-blue-800'
                  return (
                    <div key={i} className={`flex items-center gap-2 rounded border px-2 py-1 ${colour}`}>
                      <span className="text-xs font-medium capitalize">{pc.change_type}</span>
                      <span className="text-xs font-mono">{pc.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Step diff panel
// ---------------------------------------------------------------------------
function StepDiffPanel({ sd }: { sd: AuditStepDiff }) {
  const [open, setOpen] = useState(false)
  const fieldDiffsWithChanges = sd.field_diffs.filter(
    fd =>
      fd.value_changed ||
      fd.label_changed ||
      fd.description_changed ||
      fd.hidden_changed ||
      fd.preset_changes.length > 0 ||
      fd.locking_changes != null,
  )
  const totalChanges =
    fieldDiffsWithChanges.length + sd.fields_added.length + sd.fields_removed.length

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="size-4 text-gray-500" /> : <ChevronRight className="size-4 text-gray-500" />}
          <span className="font-semibold text-gray-800 text-sm">{sd.step_id}</span>
        </div>
        <span className="text-xs text-gray-500">{totalChanges} change{totalChanges !== 1 ? 's' : ''}</span>
      </button>

      {open && (
        <div className="px-4 py-3 bg-white space-y-3">
          {sd.title_changed && (
            <DiffRow label="Step title" before={sd.before_title} after={sd.after_title} />
          )}
          {sd.description_changed && (
            <DiffRow label="Description" before={sd.before_description} after={sd.after_description} />
          )}
          {sd.fields_added.length > 0 && (
            <div className="rounded bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-800">
              <strong>Fields added:</strong> {sd.fields_added.join(', ')}
            </div>
          )}
          {sd.fields_removed.length > 0 && (
            <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
              <strong>Fields removed:</strong> {sd.fields_removed.join(', ')}
            </div>
          )}
          {fieldDiffsWithChanges.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Modified fields</p>
              {fieldDiffsWithChanges.map(fd => (
                <FieldDiffPanel key={fd.field_id} fd={fd} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
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
    const fields = sd.field_diffs.filter(
      fd =>
        fd.value_changed ||
        fd.label_changed ||
        fd.description_changed ||
        fd.hidden_changed ||
        fd.preset_changes.length > 0 ||
        fd.locking_changes != null,
    )
    return (
      fields.length > 0 ||
      sd.fields_added.length > 0 ||
      sd.fields_removed.length > 0 ||
      sd.title_changed ||
      sd.description_changed
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
          {(diff?.metadata_changes?.title || diff?.metadata_changes?.description) && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Config metadata</p>
              {diff.metadata_changes.title && (
                <DiffRow label="Title" before={null} after={diff.metadata_changes.title} />
              )}
              {diff.metadata_changes.description && (
                <DiffRow label="Description" before={null} after={diff.metadata_changes.description} />
              )}
            </div>
          )}

          {/* Added / removed steps */}
          {diff?.steps?.added?.length > 0 && (
            <div className="rounded bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-800">
              <strong>Steps added:</strong> {diff.steps.added.join(', ')}
            </div>
          )}
          {diff?.steps?.removed?.length > 0 && (
            <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
              <strong>Steps removed:</strong> {diff.steps.removed.join(', ')}
            </div>
          )}

          {/* Modified steps */}
          {modifiedSteps.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Changed steps</p>
              {modifiedSteps.map(sd => (
                <StepDiffPanel key={sd.step_id} sd={sd} />
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
          onClick={() => load(page, scopeFilter, targetFilter)}
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
