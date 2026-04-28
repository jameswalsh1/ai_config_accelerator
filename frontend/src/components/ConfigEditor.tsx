import { StepFieldEditor } from '@/components/StepFieldEditor'
import type { EditableStep } from '@/types/wizard'
import { saveFieldValue } from '@/api/wizardApi'
import { useState } from 'react'

interface ConfigEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown, source?: string) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
  tool: string
  language: string
}

export function ConfigEditor({
  editableStep,
  onFieldChange,
  onMetadataUpdate,
  tool,
  language,
}: ConfigEditorProps) {
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const handleSaveChanges = async () => {
    setSaving(true)
    setSaveMessage(null)

    try {
      // Save all fields that have current values different from defaults
      const fieldsToSave = editableStep.step.fields.filter(field => 
        field.current_value !== undefined && 
        field.current_value !== field.default &&
        field.editability === 'free'
      )

      let lastUpdatedStep: EditableStep | null = null
      for (const field of fieldsToSave) {
        lastUpdatedStep = await saveFieldValue(tool, language, editableStep.step.id, field.id, field.current_value)
      }

      if (lastUpdatedStep && onMetadataUpdate) {
        onMetadataUpdate(lastUpdatedStep)
      }

      setSaveMessage(`Successfully saved ${fieldsToSave.length} field changes`)
      
      setTimeout(() => setSaveMessage(null), 3000)
    } catch (error) {
      setSaveMessage(`Error saving changes: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }

  const hasUnsavedChanges = editableStep.step.fields.some(field => 
    field.current_value !== undefined && 
    field.current_value !== field.default &&
    field.editability === 'free'
  )

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Configuration Editor</h2>
        <button
          onClick={handleSaveChanges}
          disabled={saving || !hasUnsavedChanges}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
      
      {saveMessage && (
        <div className={`mb-4 p-3 rounded-md ${saveMessage.startsWith('Error') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
          {saveMessage}
        </div>
      )}

      <StepFieldEditor
        editableStep={editableStep}
        onFieldChange={onFieldChange}
        onMetadataUpdate={onMetadataUpdate}
        tool={tool}
        language={language}
      />
    </div>
  )
}
