import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  FilePlus,
  FilePen,
  AlertCircle,
  Tag,
  ArrowRight,
} from 'lucide-react'
import type { AuditEntry, AuditFieldDiff, AuditStepDiff } from '@/api/wizardApi'

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------

export function ActionBadge({ action }: { action: AuditEntry['action'] }) {
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

export function ScopeBadge({ scope }: { scope: string }) {
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
// Value renderer
// ---------------------------------------------------------------------------

export function Value({ val, className = '' }: { val: unknown; className?: string }) {
  if (val === null || val === undefined) return <span className={`italic text-gray-400 ${className}`}>—</span>
  const str = typeof val === 'string' ? val : JSON.stringify(val, null, 2)
  return (
    <span className={`font-mono text-xs break-all whitespace-pre-wrap ${className}`}>
      {str || <span className="italic text-gray-400">(empty)</span>}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Diff row
// ---------------------------------------------------------------------------

export function DiffRow({ label, before, after }: { label: string; before: unknown; after: unknown }) {
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

export function FieldDiffPanel({ fd }: { fd: AuditFieldDiff }) {
  const [open, setOpen] = useState(false)
  const presets = fd.presets ?? []
  const hasDetail =
    fd.value?.changed ||
    fd.label?.changed ||
    fd.description?.changed ||
    fd.hidden?.changed ||
    presets.length > 0 ||
    fd.locking != null

  if (!hasDetail) return null

  return (
    <div className="rounded-md border border-gray-200 bg-white overflow-hidden text-sm">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="size-3.5 text-gray-500" /> : <ChevronRight className="size-3.5 text-gray-500" />}
          <span className="font-medium text-gray-800 font-mono text-xs">{fd.id}</span>
          <span className="text-xs text-gray-400">({fd.type})</span>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {fd.value?.changed && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">value</span>}
          {fd.locking && <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">locking</span>}
          {presets.length > 0 && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">{presets.length} preset{presets.length !== 1 ? 's' : ''}</span>}
          {fd.hidden?.changed && <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-700">visibility</span>}
        </div>
      </button>

      {open && (
        <div className="px-3 py-3 space-y-2">
          {fd.value?.changed && (
            <DiffRow label="Default value" before={fd.value.before} after={fd.value.after} />
          )}
          {fd.label?.changed && (
            <DiffRow label="Label" before={fd.label.before} after={fd.label.after} />
          )}
          {fd.description?.changed && (
            <DiffRow label="Description" before={fd.description.before} after={fd.description.after} />
          )}
          {fd.hidden?.changed && (
            <DiffRow label="Visible" before={!fd.hidden.before} after={!fd.hidden.after} />
          )}
          {fd.locking && (
            <DiffRow
              label="Editability"
              before={fd.locking.before_state}
              after={fd.locking.after_state}
            />
          )}
          {presets.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1.5">Preset changes</p>
              <div className="space-y-1">
                {presets.map((pc, i) => {
                  const colour =
                    pc.type === 'added'
                      ? 'bg-green-50 border-green-200 text-green-800'
                      : pc.type === 'removed'
                      ? 'bg-red-50 border-red-200 text-red-800'
                      : 'bg-blue-50 border-blue-200 text-blue-800'
                  return (
                    <div key={i} className={`flex items-center gap-2 rounded border px-2 py-1 ${colour}`}>
                      <span className="text-xs font-medium capitalize">{pc.type}</span>
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

export function StepDiffPanel({ sd }: { sd: AuditStepDiff }) {
  const [open, setOpen] = useState(false)
  const fieldDiffsWithChanges = (sd.fields?.modified ?? []).filter(
    fd =>
      fd.value?.changed ||
      fd.label?.changed ||
      fd.description?.changed ||
      fd.hidden?.changed ||
      (fd.presets?.length ?? 0) > 0 ||
      fd.locking != null,
  )
  const totalChanges =
    fieldDiffsWithChanges.length + (sd.fields?.added?.length ?? 0) + (sd.fields?.removed?.length ?? 0)

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown className="size-4 text-gray-500" /> : <ChevronRight className="size-4 text-gray-500" />}
          <span className="font-semibold text-gray-800 text-sm">{sd.id}</span>
        </div>
        <span className="text-xs text-gray-500">{totalChanges} change{totalChanges !== 1 ? 's' : ''}</span>
      </button>

      {open && (
        <div className="px-4 py-3 bg-white space-y-3">
          {sd.title?.changed && (
            <DiffRow label="Step title" before={sd.title.before} after={sd.title.after} />
          )}
          {sd.description?.changed && (
            <DiffRow label="Description" before={sd.description.before} after={sd.description.after} />
          )}
          {(sd.fields?.added?.length ?? 0) > 0 && (
            <div className="rounded bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-800">
              <strong>Fields added:</strong> {sd.fields.added.join(', ')}
            </div>
          )}
          {(sd.fields?.removed?.length ?? 0) > 0 && (
            <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800">
              <strong>Fields removed:</strong> {sd.fields.removed.join(', ')}
            </div>
          )}
          {fieldDiffsWithChanges.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Modified fields</p>
              {fieldDiffsWithChanges.map(fd => (
                <FieldDiffPanel key={fd.id} fd={fd} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
