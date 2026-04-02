interface WizardProgressProps {
  currentScreenIndex: number  // 0-based
  totalScreens: number
  currentStepIndex: number    // 0-based
  totalSteps: number
  currentStepTitle: string
  /** Per-step field counts, used to draw proportional step segments */
  stepsFieldCounts: number[]
}

export function WizardProgress({
  currentScreenIndex,
  totalScreens,
  currentStepIndex,
  totalSteps,
  currentStepTitle,
  stepsFieldCounts,
}: WizardProgressProps) {
  const percentage = ((currentScreenIndex + 1) / totalScreens) * 100

  // How many screens before each step starts
  const stepOffsets = stepsFieldCounts.reduce<number[]>((acc, _, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + stepsFieldCounts[i - 1])
    return acc
  }, [])

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="font-medium">
          Question {currentScreenIndex + 1} <span className="text-gray-400">of {totalScreens}</span>
        </span>
        <span className="truncate max-w-[200px] text-right">
          Step {currentStepIndex + 1} of {totalSteps}
          {' '}&mdash;{' '}
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
        {stepsFieldCounts.map((count, si) => {
          const offset = stepOffsets[si]
          // How many fields of this step are completed
          const completedInStep = Math.max(
            0,
            Math.min(count, currentScreenIndex - offset + (currentStepIndex > si ? 1 : 0)),
          )
          const stepDone = currentStepIndex > si
          const stepActive = currentStepIndex === si
          return (
            <div
              key={si}
              className="flex gap-0.5"
              style={{ flex: count }}
              title={`Step ${si + 1}`}
            >
              {Array.from({ length: count }).map((_, fi) => (
                <div
                  key={fi}
                  className={`h-1 flex-1 rounded-full transition-colors duration-200 ${
                    stepDone || fi < completedInStep
                      ? 'bg-indigo-600'
                      : stepActive && fi === completedInStep
                      ? 'bg-indigo-300'
                      : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
