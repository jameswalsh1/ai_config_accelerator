import { StepFieldEditor } from '@/components/StepFieldEditor'
import type { EditableField, EditableStep } from '@/types/wizard'
import { saveFieldValue } from '@/api/wizardApi'

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
  // Resolve scope/target from the field's override_source so saves go to the right file.
  // Falls back to language scope when the field has no existing override (base-only).
  const scopeFromField = (field: EditableField): { scope: string; target: string } => {
    if (field.override_source && field.override_source !== 'schema') {
      const [s, t] = field.override_source.split(':', 2)
      if (s && t) return { scope: s, target: t }
    }
    return { scope: 'language', target: language }
  }

  const handleFieldSave = async (fieldId: string, value: unknown) => {
    const field = editableStep.step.fields.find(f => f.id === fieldId)
    if (!field) return
    const { scope, target } = scopeFromField(field)
    const updated = await saveFieldValue(tool, language, editableStep.step.id, fieldId, value, scope, target)
    onMetadataUpdate?.(updated)
  }

  return (
    <div className="w-full">
      <StepFieldEditor
        editableStep={editableStep}
        onFieldChange={onFieldChange}
        onMetadataUpdate={onMetadataUpdate}
        onFieldSave={handleFieldSave}
        tool={tool}
        language={language}
      />
    </div>
  )
}
