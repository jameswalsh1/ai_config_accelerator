import { StepFieldEditor } from '@/components/StepFieldEditor'
import type { EditableStep } from '@/types/wizard'

interface ConfigEditorProps {
  editableStep: EditableStep
  onFieldChange?: (fieldId: string, value: unknown) => void
  onToggleLock?: (fieldId: string, locked: boolean) => void
}

export function ConfigEditor({
  editableStep,
  onFieldChange,
  onToggleLock,
}: ConfigEditorProps) {
  return (
    <div className="w-full">
      <StepFieldEditor
        editableStep={editableStep}
        onFieldChange={onFieldChange}
        onToggleLock={onToggleLock}
      />
    </div>
  )
}
