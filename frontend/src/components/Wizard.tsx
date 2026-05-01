import { useState, useEffect } from 'react'
import { generateFiles, previewFiles, fetchWizardConfig } from '@/api/wizardApi'
import type { PreviewFile } from '@/api/wizardApi'
import type { WizardConfig } from '@/types/wizard'
import { useWizard } from '@/hooks/useWizard'
import { WizardComplete } from './WizardComplete'
import { WizardFieldScreen } from './WizardFieldScreen'
import { WizardNavigation } from './WizardNavigation'
import { WizardProgress } from './WizardProgress'
import { GeneratePreview } from './GeneratePreview'

interface WizardProps {
  config: WizardConfig
  onBack: () => void
}

export function Wizard({ config, onBack }: WizardProps) {
  const [currentConfig, setCurrentConfig] = useState<WizardConfig>(config)
  const [languageLoaded, setLanguageLoaded] = useState(false)
  
  const {
    screens,
    currentScreenIndex,
    currentScreen,
    answers,
    activeTags,
    fieldError,
    isFirstScreen,
    isLastScreen,
    setFieldValue,
    nextScreen,
    prevScreen,
    reset,
  } = useWizard(currentConfig)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isDone, setIsDone] = useState(false)
  // Preview state — set when user reaches the last step and clicks "Preview & Download"
  const [previewFiles_, setPreviewFiles] = useState<PreviewFile[] | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

  // Detect when language is selected and refetch config with language filter
  useEffect(() => {
    if (languageLoaded) return

    // Look for language selection in any step containing primary_language or language field
    let selectedLanguage: string | undefined
    for (const step of currentConfig.steps) {
      // Check for primary_language field (demo.json)
      const langField = step.fields.find(f => f.id === 'primary_language' || f.id === 'language')
      if (langField) {
        selectedLanguage = (answers[step.id]?.[langField.id] as string | undefined)
        if (selectedLanguage) {
          break
        }
      }
    }

    if (!selectedLanguage) return

    // Language selected - refetch config with language filter
    setLanguageLoaded(true)
    fetchWizardConfig(currentConfig.id, selectedLanguage)
      .then(filteredConfig => {
        setCurrentConfig(filteredConfig)
      })
      .catch(err => {
        console.error('Failed to fetch language-filtered config:', err)
        // Continue with unfiltered config if fetch fails
      })
  }, [answers, currentConfig.id, currentConfig.steps, languageLoaded])

  const stepsFieldCounts = currentConfig.steps.map(s => s.fields.length)

  const handleSubmit = async () => {
    const canProceed = nextScreen()
    if (!canProceed) return

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const preview = await previewFiles(currentConfig.id, answers)
      setPreviewFiles(preview.files)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDownload = async () => {
    setIsDownloading(true)
    try {
      await generateFiles(currentConfig.id, answers)
      setIsDone(true)
      setPreviewFiles(null)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setIsDownloading(false)
    }
  }

  const handleReset = () => {
    reset()
    setIsDone(false)
    setPreviewFiles(null)
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
        <h1 className="text-lg font-semibold text-gray-900">{currentConfig.title}</h1>
        <span className="ml-auto rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500 capitalize">
          {currentConfig.target}
        </span>
      </div>

      {!isDone && !previewFiles_ && (
        <WizardProgress
          currentScreenIndex={currentScreenIndex}
          totalScreens={screens.length}
          currentStepIndex={currentScreen.stepIndex}
          currentStepTitle={currentScreen.step.title}
          stepsFieldCounts={stepsFieldCounts}
        />
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {isDone ? (
          <WizardComplete configTitle={currentConfig.title} onReset={handleReset} />
        ) : previewFiles_ ? (
          <>
            <GeneratePreview
              files={previewFiles_}
              configTitle={currentConfig.title}
              isDownloading={isDownloading}
              onDownload={() => { void handleDownload() }}
            />
            {submitError && (
              <div className="mt-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
                {submitError}
              </div>
            )}
            <div className="mt-4 flex justify-start">
              <button
                type="button"
                onClick={() => setPreviewFiles(null)}
                className="text-sm text-gray-500 hover:text-gray-700 transition"
              >
                ← Back to wizard
              </button>
            </div>
          </>
        ) : (
          <>
            <WizardFieldScreen
              screen={currentScreen}
              answers={answers}
              activeTags={activeTags}
              targetTag={currentConfig.target}
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
                onSubmit={() => { void handleSubmit() }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
