import { CheckCircle2Icon, RotateCcwIcon } from 'lucide-react'

interface WizardCompleteProps {
  configTitle: string
  onReset: () => void
}

export function WizardComplete({ configTitle, onReset }: WizardCompleteProps) {
  return (
    <div className="flex flex-col items-center gap-6 py-12 text-center">
      <div className="flex size-16 items-center justify-center rounded-full bg-green-100">
        <CheckCircle2Icon className="size-9 text-green-600" />
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold text-gray-900">Files Generated!</h2>
        <p className="text-sm text-gray-500">
          Your <span className="font-medium text-gray-700">{configTitle}</span> configuration has
          been packaged and downloaded as a ZIP file.
        </p>
      </div>
      <p className="max-w-sm text-xs text-gray-400">
        Unzip the file and place the configuration files in the root of your project, then restart
        your AI assistant to pick up the new settings.
      </p>
      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-2 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
      >
        <RotateCcwIcon className="size-4" />
        Start Over
      </button>
    </div>
  )
}
