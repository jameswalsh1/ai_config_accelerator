import { useState, useEffect, useCallback } from 'react'
import {
  CameraIcon,
  RotateCcwIcon,
  Trash2Icon,
  ChevronDownIcon,
  ChevronUpIcon,
  Loader2Icon,
  CheckIcon,
  AlertCircleIcon,
} from 'lucide-react'
import {
  createSnapshot,
  listSnapshots,
  restoreSnapshot,
  deleteSnapshot,
} from '@/api/wizardApi'
import type { SnapshotMeta } from '@/api/wizardApi'

interface SnapshotManagerProps {
  /** Snapshot scope — typically "language" for the Config Editor. */
  scope: string
  /** Snapshot target — e.g. "python", "claude". */
  target: string
  /**
   * Called after a successful restore so the parent can refresh the step data.
   * Optional — omit if the parent manages reload separately.
   */
  onRestored?: () => void
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function SnapshotManager({ scope, target, onRestored }: SnapshotManagerProps) {
  const [open, setOpen] = useState(false)
  const [snapshots, setSnapshots] = useState<SnapshotMeta[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Create-snapshot form
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createOk, setCreateOk] = useState(false)

  // Per-snapshot action state
  const [restoringId, setRestoringId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSnapshots(await listSnapshots(scope, target))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load snapshots')
    } finally {
      setLoading(false)
    }
  }, [scope, target])

  // Load when panel opens or scope/target changes
  useEffect(() => {
    if (open) load()
  }, [open, load])

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    setError(null)
    try {
      await createSnapshot(scope, target, name)
      setNewName('')
      setCreateOk(true)
      setTimeout(() => setCreateOk(false), 2000)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create snapshot')
    } finally {
      setCreating(false)
    }
  }

  const handleRestore = async (id: string) => {
    setRestoringId(id)
    setConfirmId(null)
    setError(null)
    try {
      await restoreSnapshot(scope, target, id)
      onRestored?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to restore snapshot')
    } finally {
      setRestoringId(null)
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    setConfirmId(null)
    setError(null)
    try {
      await deleteSnapshot(scope, target, id)
      setSnapshots(prev => prev.filter(s => s.snapshot_id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete snapshot')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Header / toggle */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          <CameraIcon className="size-4 text-indigo-500 shrink-0" />
          <span className="text-sm font-medium text-gray-800">Snapshots</span>
          {snapshots.length > 0 && (
            <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
              {snapshots.length}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUpIcon className="size-4 text-gray-400" />
        ) : (
          <ChevronDownIcon className="size-4 text-gray-400" />
        )}
      </button>

      {open && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-4">
          {/* Create form */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder='e.g. "before Python migration"'
              className="flex-1 min-w-0 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              {creating ? (
                <Loader2Icon className="size-3.5 animate-spin" />
              ) : createOk ? (
                <CheckIcon className="size-3.5" />
              ) : (
                <CameraIcon className="size-3.5" />
              )}
              {creating ? 'Saving…' : createOk ? 'Saved!' : 'Save snapshot'}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircleIcon className="size-4 shrink-0" />
              {error}
            </div>
          )}

          {/* Snapshot list */}
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-4 text-sm text-gray-400">
              <Loader2Icon className="size-4 animate-spin" />
              Loading…
            </div>
          ) : snapshots.length === 0 ? (
            <p className="py-3 text-center text-sm text-gray-400 italic">
              No snapshots yet. Save one above to capture the current state.
            </p>
          ) : (
            <ul className="space-y-2">
              {snapshots.map(snap => (
                <li
                  key={snap.snapshot_id}
                  className="flex items-center gap-2 rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
                >
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm font-medium text-gray-800">{snap.name}</p>
                    <p className="text-xs text-gray-400">{formatDate(snap.created_at)}</p>
                  </div>

                  {/* Restore */}
                  {confirmId === snap.snapshot_id ? (
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-xs text-gray-600 whitespace-nowrap">Restore?</span>
                      <button
                        type="button"
                        onClick={() => handleRestore(snap.snapshot_id)}
                        disabled={restoringId !== null}
                        className="rounded px-2 py-0.5 text-xs font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 transition-colors"
                      >
                        {restoringId === snap.snapshot_id ? (
                          <Loader2Icon className="size-3 animate-spin inline" />
                        ) : (
                          'Yes'
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmId(null)}
                        className="rounded px-2 py-0.5 text-xs font-medium text-gray-600 hover:text-gray-800 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmId(snap.snapshot_id)}
                      disabled={restoringId !== null || deletingId !== null}
                      title="Restore this snapshot"
                      className="rounded p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                    >
                      <RotateCcwIcon className="size-3.5" />
                    </button>
                  )}

                  {/* Delete */}
                  <button
                    type="button"
                    onClick={() => handleDelete(snap.snapshot_id)}
                    disabled={deletingId !== null || restoringId !== null}
                    title="Delete this snapshot"
                    className="rounded p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                  >
                    {deletingId === snap.snapshot_id ? (
                      <Loader2Icon className="size-3.5 animate-spin" />
                    ) : (
                      <Trash2Icon className="size-3.5" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
