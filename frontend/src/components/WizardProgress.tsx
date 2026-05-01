interface WizardProgressProps {
  currentScreenIndex: number  // 0-based screen (which is now a step)
  totalScreens: number        // total steps
  currentStepIndex: number    // 0-based
  currentStepTitle: string
  /** Per-step field counts, used to draw proportional step segments */
  stepsFieldCounts: number[]
}

export function WizardProgress({
  currentScreenIndex,
  totalScreens,
  currentStepIndex,
  currentStepTitle,
  stepsFieldCounts,
}: WizardProgressProps) {
  const percentage = ((currentScreenIndex + 1) / totalScreens) * 100

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="font-medium">
          Step {currentScreenIndex + 1} <span className="text-gray-400">of {totalScreens}</span>
        </span>
        <span className="truncate max-w-[200px] text-right">
          <span className="text-gray-700">{currentStepTitle}</span>
        </span>
      </div>

      {/* Overall progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-indigo-600 transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Per-step segments with proportional widths */}
      <div className="flex gap-1">
        {stepsFieldCounts.map((_, si) => {
          const stepDone = currentStepIndex > si
          const stepActive = currentStepIndex === si
          return (
            <div
              key={si}
              className="h-1 flex-1 rounded-full transition-colors duration-200"
              style={{
                backgroundColor: stepDone ? 'rgb(79, 70, 229)' : stepActive ? 'rgb(129, 140, 248)' : 'rgb(229, 231, 235)'
              }}
              title={`Step ${si + 1}`}
            />
          )
        })}
      </div>
    </div>
  )
}
