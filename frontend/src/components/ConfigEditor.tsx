import { StepFieldEditor } from '@/components/StepFieldEditor'
import type { EditableStep } from '@/types/wizard'

interface ConfigEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown) => void
  onToggleLock?: (fieldId: string, locked: boolean) => void
  onMetadataUpdate?: (updatedStep: EditableStep) => void
}

export function ConfigEditor({
  editableStep,
  onFieldChange,
  onToggleLock,
  onMetadataUpdate,
}: ConfigEditorProps) {
  return (
    <div className="w-full">
      <StepFieldEditor
        editableStep={editableStep}
        onFieldChange={onFieldChange}
        onToggleLock={onToggleLock}
        onMetadataUpdate={onMetadataUpdate}
      />
    </div>
  )
}
