import { useState, useEffect } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import {
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Plus, X, Eye, EyeOff } from 'lucide-react'
import type { Preset, PresetAssignment } from '@/types/wizard'
import {
  fetchAvailablePresets,
  fetchFieldPresetAssignments,
  assignPresetToField,
  updatePresetAssignment,
  removePresetAssignment,
  reorderPresetAssignments,
} from '@/api/wizardApi'

interface PresetManagementProps {
  tool: string
  language: string
  fieldId: string
  onAssignmentsChange?: (assignments: PresetAssignment[]) => void
}

interface SortablePresetAssignmentProps {
  assignment: PresetAssignment
  onModeChange: (assignmentId: string, mode: string) => void
  onRemove: (assignmentId: string) => void
  onToggleVisibility: (assignmentId: string, visible: boolean) => void
}

function SortablePresetAssignment({
  assignment,
  onModeChange,
  onRemove,
  onToggleVisibility,
}: SortablePresetAssignmentProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: assignment.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const modeColors = {
    suggested: 'bg-amber-100 text-amber-700',
    defaulted: 'bg-gray-100 text-gray-700',
    locked: 'bg-red-100 text-red-700',
    hidden_applied: 'bg-slate-100 text-slate-700',
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-3 bg-white border rounded-lg shadow-sm ${
        isDragging ? 'opacity-50' : ''
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab hover:bg-gray-100 p-1 rounded"
        title="Drag to reorder"
      >
        <GripVertical className="size-4 text-gray-400" />
      </button>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h4 className="font-medium text-gray-900 truncate">
            {assignment.preset.label}
          </h4>
          {assignment.preset.description && (
            <span className="text-xs text-gray-500 truncate">
              {assignment.preset.description}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={assignment.assignment_mode}
            onChange={(e) => onModeChange(assignment.id, e.target.value)}
            className="text-xs px-2 py-1 rounded border border-gray-300 bg-white"
          >
            <option value="suggested">Suggested</option>
            <option value="defaulted">Defaulted</option>
            <option value="locked">Locked</option>
            <option value="hidden_applied">Hidden</option>
          </select>
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
            modeColors[assignment.assignment_mode]
          }`}>
            {assignment.assignment_mode}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onToggleVisibility(assignment.id, !assignment.is_visible)}
          className="p-1 rounded hover:bg-gray-100"
          title={assignment.is_visible ? 'Hide preset' : 'Show preset'}
        >
          {assignment.is_visible ? (
            <Eye className="size-4 text-gray-500" />
          ) : (
            <EyeOff className="size-4 text-gray-400" />
          )}
        </button>
        <button
          onClick={() => onRemove(assignment.id)}
          className="p-1 rounded hover:bg-red-100 text-red-500"
          title="Remove preset"
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  )
}

export function PresetManagement({
  tool,
  language,
  fieldId,
  onAssignmentsChange,
}: PresetManagementProps) {
  const [availablePresets, setAvailablePresets] = useState<{
    shared: Preset[]
    language: Preset[]
    tool: Preset[]
  }>({ shared: [], language: [], tool: [] })
  const [assignments, setAssignments] = useState<PresetAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [selectedPresetId, setSelectedPresetId] = useState<string>('')

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  useEffect(() => {
    void loadData()
  }, [tool, language, fieldId])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [presetsData, assignmentsData] = await Promise.all([
        fetchAvailablePresets(tool, language).catch(() => ({ shared: [], language: [], tool: [] })),
        fetchFieldPresetAssignments(tool, language, fieldId).catch(() => []),
      ])
      setAvailablePresets(presetsData)
      setAssignments(assignmentsData)
      onAssignmentsChange?.(assignmentsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const oldIndex = assignments.findIndex((item) => item.id === active.id)
      const newIndex = assignments.findIndex((item) => item.id === over.id)

      const newAssignments = arrayMove(assignments, oldIndex, newIndex)
      setAssignments(newAssignments)

      try {
        await reorderPresetAssignments(
          tool,
          language,
          fieldId,
          newAssignments.map((a) => a.id)
        )
        onAssignmentsChange?.(newAssignments)
      } catch {
        // Revert on error
        setAssignments(assignments)
        setError('Failed to reorder presets - changes reverted')
      }
    }
  }

  const handleAddPreset = async () => {
    if (!selectedPresetId) return

    try {
      const newAssignment = await assignPresetToField(
        tool,
        language,
        fieldId,
        selectedPresetId,
        'suggested',
        assignments.length
      )
      const updatedAssignments = [...assignments, newAssignment]
      setAssignments(updatedAssignments)
      onAssignmentsChange?.(updatedAssignments)
      setShowAddDialog(false)
      setSelectedPresetId('')
    } catch {
      setError('Failed to add preset - please try again')
    }
  }

  const handleModeChange = async (assignmentId: string, mode: string) => {
    try {
      const updated = await updatePresetAssignment(assignmentId, {
        assignment_mode: mode as PresetAssignment['assignment_mode'],
      })
      const updatedAssignments = assignments.map((a) =>
        a.id === assignmentId ? updated : a
      )
      setAssignments(updatedAssignments)
      onAssignmentsChange?.(updatedAssignments)
    } catch {
      setError('Failed to update preset mode - please try again')
    }
  }

  const handleRemove = async (assignmentId: string) => {
    try {
      await removePresetAssignment(assignmentId)
      const updatedAssignments = assignments.filter((a) => a.id !== assignmentId)
      setAssignments(updatedAssignments)
      onAssignmentsChange?.(updatedAssignments)
    } catch {
      setError('Failed to remove preset - please try again')
    }
  }

  const handleToggleVisibility = async (assignmentId: string, visible: boolean) => {
    try {
      const updated = await updatePresetAssignment(assignmentId, {
        is_visible: visible,
      })
      const updatedAssignments = assignments.map((a) =>
        a.id === assignmentId ? updated : a
      )
      setAssignments(updatedAssignments)
      onAssignmentsChange?.(updatedAssignments)
    } catch {
      setError('Failed to update preset visibility - please try again')
    }
  }

  const allAvailablePresets = [
    ...availablePresets.shared,
    ...availablePresets.language,
    ...availablePresets.tool,
  ]

  const assignedPresetIds = new Set(assignments.map((a) => a.preset_id))
  const unassignedPresets = allAvailablePresets.filter(
    (p) => !assignedPresetIds.has(p.label) // Using label as ID for now
  )

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-500">
        Loading presets...
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-500">
        Error: {error}
        <button
          onClick={() => { void loadData() }}
          className="ml-2 px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Preset Management</h3>
        <button
          onClick={() => setShowAddDialog(true)}
          className="flex items-center gap-2 px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          <Plus className="size-4" />
          Add Preset
        </button>
      </div>

      {/* Assigned Presets */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">
          Assigned Presets ({assignments.length})
        </h4>
        {assignments.length === 0 ? (
          <div className="text-center py-8 text-gray-500 border-2 border-dashed border-gray-300 rounded-lg">
            No presets assigned. Add one to get started.
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(e) => { void handleDragEnd(e) }}
          >
            <SortableContext
              items={assignments.map((a) => a.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {assignments.map((assignment) => (
                  <SortablePresetAssignment
                    key={assignment.id}
                    assignment={assignment}
                    onModeChange={(id, mode) => { void handleModeChange(id, mode) }}
                    onRemove={(id) => { void handleRemove(id) }}
                    onToggleVisibility={(id, vis) => { void handleToggleVisibility(id, vis) }}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      {/* Add Preset Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Add Preset</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Preset
                </label>
                <select
                  value={selectedPresetId}
                  onChange={(e) => setSelectedPresetId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">-- Select a preset --</option>
                  {unassignedPresets.map((preset) => (
                    <option key={preset.label} value={preset.label}>
                      {preset.label}
                      {preset.description && ` - ${preset.description}`}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => { void handleAddPreset() }}
                  disabled={!selectedPresetId}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  Add Preset
                </button>
                <button
                  onClick={() => {
                    setShowAddDialog(false)
                    setSelectedPresetId('')
                  }}
                  className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}