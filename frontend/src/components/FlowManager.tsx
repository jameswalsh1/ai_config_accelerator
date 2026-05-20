import { useCallback, useEffect, useState } from 'react'
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  EyeIcon,
  EyeOffIcon,
  GripVerticalIcon,
  LayoutListIcon,
  Loader2Icon,
  PlusIcon,
  StarIcon,
  Trash2Icon,
  XIcon,
} from 'lucide-react'
import {
  archiveFlow,
  createFlow,
  fetchFlows,
  fetchFlow,
  setDefaultFlow,
  updateFlow,
} from '@/api/wizardApi'
import type { WizardFlow } from '@/types/wizard'

interface FlowManagerProps {
  onClose: () => void
  onFlowActivated?: (flow: WizardFlow | null) => void
}

interface EditableFlowStep {
  step_key: string
  is_enabled: boolean
  custom_title: string | null
  custom_description: string | null
}

export function FlowManager({ onClose, onFlowActivated }: FlowManagerProps) {
  const [flows, setFlows] = useState<WizardFlow[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFlow, setSelectedFlow] = useState<WizardFlow | null>(null)
  const [editSteps, setEditSteps] = useState<EditableFlowStep[]>([])
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newFlowName, setNewFlowName] = useState('')
  const [newFlowDesc, setNewFlowDesc] = useState('')
  const [error, setError] = useState<string | null>(null)

  const loadFlows = useCallback(async () => {
    setLoading(true)
    try {
      const loaded = await fetchFlows(true)
      setFlows(loaded)
    } catch {
      setError('Failed to load flows')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadFlows() }, [loadFlows])

  const handleSelectFlow = useCallback(async (flow: WizardFlow) => {
    try {
      const full = await fetchFlow(flow.id)
      setSelectedFlow(full)
      setEditSteps(
        (full.steps ?? []).map(s => ({
          step_key: s.step_key,
          is_enabled: s.is_enabled,
          custom_title: s.custom_title ?? null,
          custom_description: s.custom_description ?? null,
        }))
      )
      setEditName(full.name)
      setEditDescription(full.description)
    } catch {
      setError('Failed to load flow details')
    }
  }, [])

  const handleCreate = useCallback(async () => {
    if (!newFlowName.trim()) return
    try {
      const created = await createFlow({ name: newFlowName, description: newFlowDesc })
      setShowCreateForm(false)
      setNewFlowName('')
      setNewFlowDesc('')
      await loadFlows()
      await handleSelectFlow(created)
    } catch {
      setError('Failed to create flow')
    }
  }, [newFlowName, newFlowDesc, loadFlows, handleSelectFlow])

  const handleSave = useCallback(async () => {
    if (!selectedFlow) return
    setSaving(true)
    try {
      const updated = await updateFlow(selectedFlow.id, {
        name: editName,
        description: editDescription,
        steps: editSteps,
      })
      setSelectedFlow(updated)
      await loadFlows()
    } catch {
      setError('Failed to save flow')
    } finally {
      setSaving(false)
    }
  }, [selectedFlow, editName, editDescription, editSteps, loadFlows])

  const handleSetDefault = useCallback(async (flow: WizardFlow) => {
    try {
      await setDefaultFlow(flow.id)
      await loadFlows()
    } catch {
      setError('Failed to set default flow')
    }
  }, [loadFlows])

  const handleArchive = useCallback(async (flow: WizardFlow) => {
    try {
      await archiveFlow(flow.id)
      if (selectedFlow?.id === flow.id) setSelectedFlow(null)
      await loadFlows()
    } catch {
      setError('Failed to archive flow')
    }
  }, [selectedFlow, loadFlows])

  const moveStep = useCallback((index: number, direction: 'up' | 'down') => {
    setEditSteps(prev => {
      const arr = [...prev]
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      if (targetIndex < 0 || targetIndex >= arr.length) return prev
      const temp = arr[index]
      arr[index] = arr[targetIndex]
      arr[targetIndex] = temp
      return arr
    })
  }, [])

  const toggleStep = useCallback((index: number) => {
    setEditSteps(prev => prev.map((s, i) =>
      i === index ? { ...s, is_enabled: !s.is_enabled } : s
    ))
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative ml-auto flex h-full w-full max-w-lg flex-col bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Wizard Flows</h2>
            <p className="text-xs text-gray-500">Customise the steps you see and their order</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
          >
            <XIcon className="size-5" />
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
            <button onClick={() => setError(null)} className="ml-2 font-medium underline">Dismiss</button>
          </div>
        )}

        <div className="flex flex-1 overflow-hidden">
          {/* Flow list */}
          <div className="w-48 flex-shrink-0 border-r border-gray-100 overflow-y-auto">
            <div className="p-3">
              <button
                type="button"
                onClick={() => setShowCreateForm(true)}
                className="flex w-full items-center gap-1.5 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-xs font-medium text-gray-500 transition hover:border-indigo-300 hover:text-indigo-600"
              >
                <PlusIcon className="size-3.5" />
                New Flow
              </button>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2Icon className="size-5 animate-spin text-gray-300" />
              </div>
            ) : (
              <div className="flex flex-col gap-0.5 px-2">
                {flows.map(flow => (
                  <button
                    key={flow.id}
                    type="button"
                    onClick={() => { void handleSelectFlow(flow) }}
                    className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition ${
                      selectedFlow?.id === flow.id
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-gray-600 hover:bg-gray-50'
                    } ${flow.status === 'archived' ? 'opacity-50' : ''}`}
                  >
                    {flow.is_default && <StarIcon className="size-3 text-amber-400 fill-amber-400 shrink-0" />}
                    <span className="truncate flex-1">{flow.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Detail / editor */}
          <div className="flex-1 overflow-y-auto p-4">
            {showCreateForm ? (
              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-semibold text-gray-800">Create New Flow</h3>
                <input
                  type="text"
                  value={newFlowName}
                  onChange={e => setNewFlowName(e.target.value)}
                  placeholder="Flow name"
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
                <textarea
                  value={newFlowDesc}
                  onChange={e => setNewFlowDesc(e.target.value)}
                  placeholder="Description (optional)"
                  rows={2}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => { void handleCreate() }}
                    disabled={!newFlowName.trim()}
                    className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                  >
                    <PlusIcon className="size-3.5" />
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : selectedFlow ? (
              <div className="flex flex-col gap-4">
                {/* Flow header */}
                <div className="flex flex-col gap-2">
                  <input
                    type="text"
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    className="text-base font-semibold text-gray-900 border-0 border-b border-transparent px-0 py-1 focus:border-indigo-300 focus:outline-none focus:ring-0 bg-transparent"
                  />
                  <input
                    type="text"
                    value={editDescription}
                    onChange={e => setEditDescription(e.target.value)}
                    placeholder="Add a description..."
                    className="text-xs text-gray-500 border-0 border-b border-transparent px-0 py-1 focus:border-indigo-300 focus:outline-none focus:ring-0 bg-transparent"
                  />
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => { void handleSave() }}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {saving ? <Loader2Icon className="size-3 animate-spin" /> : <CheckIcon className="size-3" />}
                    Save
                  </button>
                  {!selectedFlow.is_default && (
                    <button
                      type="button"
                      onClick={() => { void handleSetDefault(selectedFlow) }}
                      className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700"
                    >
                      <StarIcon className="size-3" />
                      Set Default
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      void handleArchive(selectedFlow)
                      onFlowActivated?.(null)
                    }}
                    className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-red-50 hover:border-red-200 hover:text-red-600"
                  >
                    <Trash2Icon className="size-3" />
                    Archive
                  </button>
                  <button
                    type="button"
                    onClick={() => { onFlowActivated?.(selectedFlow) }}
                    className="inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-600 transition hover:bg-indigo-100"
                  >
                    Use This Flow
                  </button>
                </div>

                {/* Step list */}
                <div className="mt-2">
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Steps</h4>
                  <div className="flex flex-col gap-1">
                    {editSteps.map((step, i) => (
                      <div
                        key={step.step_key}
                        className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 transition ${
                          step.is_enabled
                            ? 'border-gray-200 bg-white'
                            : 'border-gray-100 bg-gray-50 opacity-60'
                        }`}
                      >
                        <GripVerticalIcon className="size-3.5 text-gray-300 cursor-grab shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className={`text-sm font-medium ${step.is_enabled ? 'text-gray-800' : 'text-gray-400 line-through'}`}>
                            {step.custom_title ?? step.step_key}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => moveStep(i, 'up')}
                            disabled={i === 0}
                            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30 transition"
                            title="Move up"
                          >
                            <ArrowUpIcon className="size-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => moveStep(i, 'down')}
                            disabled={i === editSteps.length - 1}
                            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-30 transition"
                            title="Move down"
                          >
                            <ArrowDownIcon className="size-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleStep(i)}
                            className={`rounded p-1 transition ${
                              step.is_enabled
                                ? 'text-emerald-500 hover:bg-emerald-50'
                                : 'text-gray-300 hover:bg-gray-100'
                            }`}
                            title={step.is_enabled ? 'Disable step' : 'Enable step'}
                          >
                            {step.is_enabled ? <EyeIcon className="size-3.5" /> : <EyeOffIcon className="size-3.5" />}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center text-gray-400">
                <LayoutListIcon className="size-8 mb-3" />
                <p className="text-sm font-medium">Select a flow to edit</p>
                <p className="text-xs mt-1">Or create a new one to get started</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
