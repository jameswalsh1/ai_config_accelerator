import { useState } from 'react'
import { generateFiles } from '@/api/wizardApi'
import type { WizardConfig } from '@/types/wizard'
import { useWizard } from '@/hooks/useWizard'
import { WizardComplete } from './WizardComplete'
import { WizardFieldScreen } from './WizardFieldScreen'
import { WizardNavigation } from './WizardNavigation'
import { WizardProgress } from './WizardProgress'

interface WizardProps {
  config: WizardConfig
  onBack: () => void
}

export function Wizard({ config, onBack }: WizardProps) {
  const {
    screens,
    currentScreenIndex,
    currentScreen,
    answers,
    fieldError,
    isFirstScreen,
    isLastScreen,
    setFieldValue,
    nextScreen,
    prevScreen,
    reset,
  } = useWizard(config)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isDone, setIsDone] = useState(false)

  const stepsFieldCounts = config.steps.map(s => s.fields.length)

  const handleSubmit = async () => {
    const canProceed = nextScreen()
    if (!canProceed) return

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await generateFiles(config.id, answers)
      setIsDone(true)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    reset()
    setIsDone(false)
    setSubmitError(null)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-gray-400 hover:text-gray-600 transition"
        >
          ← Back to configs
        </button>
        <span className="text-gray-300">|</span>
        <h1 className="text-lg font-semibold text-gray-900">{config.title}</h1>
        <span className="ml-auto rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500 capitalize">
          {config.target}
        </span>
      </div>

      {!isDone && (
        <WizardProgress
          currentScreenIndex={currentScreenIndex}
          totalScreens={screens.length}
          currentStepIndex={currentScreen.stepIndex}
          totalSteps={config.steps.length}
          currentStepTitle={currentScreen.step.title}
          stepsFieldCounts={stepsFieldCounts}
        />
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {isDone ? (
          <WizardComplete configTitle={config.title} onReset={handleReset} />
        ) : (
          <>
            <WizardFieldScreen
              screen={currentScreen}
              answers={answers}
              fieldError={fieldError}
              onFieldChange={(fieldId, value) =>
                setFieldValue(currentScreen.step.id, fieldId, value)
              }
            />

            {submitError && (
              <div className="mt-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
                {submitError}
              </div>
            )}

            <div className="mt-6">
              <WizardNavigation
                isFirstScreen={isFirstScreen}
                isLastScreen={isLastScreen}
                isSubmitting={isSubmitting}
                onPrev={prevScreen}
                onNext={nextScreen}
                onSubmit={handleSubmit}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
