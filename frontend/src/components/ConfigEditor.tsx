import { StepFieldEditor } from '@/components/StepFieldEditor'
import type { EditableStep } from '@/types/wizard'

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
  return (
    <div className="w-full">
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
