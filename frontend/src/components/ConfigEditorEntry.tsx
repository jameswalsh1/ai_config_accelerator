import { useEffect, useState } from 'react'
import { Plus, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  fetchAvailableTools,
  fetchAvailableLanguages,
  fetchAvailableSteps,
  fetchEditableConfig,
  type ToolOption,
  type LanguageOption,
  type StepOption,
  type EditableStep,
} from '@/api/wizardApi'
import { CreateLanguageModal } from './CreateLanguageModal'

interface ConfigEditorEntryProps {
  onConfigSelected: (editableConfig: EditableStep, tool: string, language: string) => void
}

export function ConfigEditorEntry({ onConfigSelected }: ConfigEditorEntryProps) {
  const [tools, setTools] = useState<ToolOption[]>([])
  const [languages, setLanguages] = useState<LanguageOption[]>([])
  const [steps, setSteps] = useState<StepOption[]>([])
  const [selectedTool, setSelectedTool] = useState<string>('')
  const [selectedLanguage, setSelectedLanguage] = useState<string>('')
  const [selectedStep, setSelectedStep] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [loadingSteps, setLoadingSteps] = useState(false)
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCreateLanguage, setShowCreateLanguage] = useState(false)
  // Track whether a config has been loaded at least once (to show step nav)
  const [configLoaded, setConfigLoaded] = useState(false)

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setLoading(true)
        const [toolsData, languagesData] = await Promise.all([
          fetchAvailableTools(),
          fetchAvailableLanguages(),
        ])
        setTools(toolsData)
        setLanguages(languagesData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadInitialData()
  }, [])

  useEffect(() => {
    if (selectedTool && selectedLanguage) {
      const loadSteps = async () => {
        try {
          setLoadingSteps(true)
          const stepsData = await fetchAvailableSteps(selectedTool, selectedLanguage)
          setSteps(stepsData)
          // Auto-select and auto-load the first step
          if (stepsData.length > 0) {
            setSelectedStep(stepsData[0].id)
            await loadStep(stepsData[0].id, selectedTool, selectedLanguage)
          } else {
            setSelectedStep('')
            setConfigLoaded(false)
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to load steps')
        } finally {
          setLoadingSteps(false)
        }
      }

      loadSteps()
    } else {
      setSteps([])
      setSelectedStep('')
      setConfigLoaded(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTool, selectedLanguage])

  const loadStep = async (stepId: string, tool = selectedTool, language = selectedLanguage) => {
    if (!tool || !language || !stepId) return
    try {
      setLoadingConfig(true)
      const editableConfig = await fetchEditableConfig(tool, language, stepId)
      onConfigSelected(editableConfig, tool, language)
      setConfigLoaded(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config')
    } finally {
      setLoadingConfig(false)
    }
  }

  const currentStepIndex = steps.findIndex(s => s.id === selectedStep)

  const handlePrev = () => {
    if (currentStepIndex <= 0) return
    const prevId = steps[currentStepIndex - 1].id
    setSelectedStep(prevId)
    loadStep(prevId)
  }

  const handleNext = () => {
    if (currentStepIndex >= steps.length - 1) return
    const nextId = steps[currentStepIndex + 1].id
    setSelectedStep(nextId)
    loadStep(nextId)
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 text-sm text-gray-500">
        <span>Loading…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 px-4 py-2 bg-red-50 border-b border-red-200 text-sm text-red-700">
        <span>{error}</span>
        <button onClick={() => setError(null)} className="underline">Dismiss</button>
      </div>
    )
  }

  return (
    <>
      {/* ── Sticky control bar ── */}
      <div className="sticky top-[57px] z-40 bg-white border-b border-gray-200 shadow-sm">
        <div className="mx-auto max-w-5xl px-6 py-3 flex flex-wrap items-center gap-3">

          {/* Tool */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="tool-select" className="text-xs font-medium text-gray-500 shrink-0">Tool</label>
            <select
              id="tool-select"
              value={selectedTool}
              onChange={(e) => setSelectedTool(e.target.value)}
              className="text-sm px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select…</option>
              {tools.map((tool) => (
                <option key={tool.id} value={tool.id}>{tool.title}</option>
              ))}
            </select>
          </div>

          <div className="h-5 w-px bg-gray-300" />

          {/* Language */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="language-select" className="text-xs font-medium text-gray-500 shrink-0">Language</label>
            <select
              id="language-select"
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="text-sm px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select…</option>
              {languages.map((language) => (
                <option key={language.id} value={language.id}>{language.title}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowCreateLanguage(true)}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded hover:bg-indigo-100 transition-colors"
            >
              <Plus className="size-3" />
              New
            </button>
          </div>

          {/* Step nav — only once tool + language chosen */}
          {selectedTool && selectedLanguage && (
            <>
              <div className="h-5 w-px bg-gray-300" />

              {loadingSteps ? (
                <span className="text-xs text-gray-400">Loading steps…</span>
              ) : steps.length > 0 ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={handlePrev}
                    disabled={currentStepIndex <= 0 || loadingConfig}
                    className="p-1.5 rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    title="Previous step"
                  >
                    <ChevronLeft className="size-4" />
                  </button>

                  <select
                    id="step-select"
                    value={selectedStep}
                    onChange={(e) => { setSelectedStep(e.target.value); loadStep(e.target.value) }}
                    disabled={loadingConfig}
                    className="text-sm px-2 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed max-w-[240px]"
                  >
                    {steps.map((step) => (
                      <option key={step.id} value={step.id}>{step.title}</option>
                    ))}
                  </select>

                  <button
                    onClick={handleNext}
                    disabled={currentStepIndex >= steps.length - 1 || loadingConfig}
                    className="p-1.5 rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    title="Next step"
                  >
                    <ChevronRight className="size-4" />
                  </button>

                  <span className="text-xs text-gray-400 tabular-nums shrink-0">
                    {currentStepIndex >= 0 ? `${currentStepIndex + 1} / ${steps.length}` : `${steps.length} steps`}
                  </span>

                  {loadingConfig && (
                    <span className="text-xs text-indigo-500">Loading…</span>
                  )}
                </div>
              ) : (
                <span className="text-xs text-gray-400">No steps available</span>
              )}
            </>
          )}
        </div>
      </div>

      {showCreateLanguage && (
        <CreateLanguageModal
          existingLanguages={languages}
          onCreated={(newLang) => {
            setLanguages(prev => [...prev, newLang].sort((a, b) => a.title.localeCompare(b.title)))
            setSelectedLanguage(newLang.id)
            setShowCreateLanguage(false)
          }}
          onClose={() => setShowCreateLanguage(false)}
        />
      )}
    </>
  )
}
