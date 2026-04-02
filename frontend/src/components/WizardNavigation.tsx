import { ChevronLeftIcon, ChevronRightIcon, DownloadIcon, Loader2Icon } from 'lucide-react'

interface WizardNavigationProps {
  isFirstScreen: boolean
  isLastScreen: boolean
  isSubmitting: boolean
  onPrev: () => void
  onNext: () => void
  onSubmit: () => void
}

export function WizardNavigation({
  isFirstScreen,
  isLastScreen,
  isSubmitting,
  onPrev,
  onNext,
  onSubmit,
}: WizardNavigationProps) {
  return (
    <div className="flex items-center justify-between pt-4 border-t border-gray-200">
      <button
        type="button"
        onClick={onPrev}
        disabled={isFirstScreen}
        className="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <ChevronLeftIcon className="size-4" />
        Previous
      </button>

      {isLastScreen ? (
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <DownloadIcon className="size-4" />
          )}
          {isSubmitting ? 'Generating…' : 'Generate ZIP'}
        </button>
      ) : (
        <button
          type="button"
          onClick={onNext}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          Next
          <ChevronRightIcon className="size-4" />
        </button>
      )}
    </div>
  )
}
