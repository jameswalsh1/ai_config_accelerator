import { useEffect, useState } from 'react'
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

interface ConfigEditorEntryProps {
  onConfigSelected: (editableConfig: EditableStep) => void
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
          setSelectedStep('') // Reset step selection when tool/language changes
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
    }
  }, [selectedTool, selectedLanguage])

  const handleLoadConfig = async () => {
    if (!selectedTool || !selectedLanguage || !selectedStep) return

    try {
      setLoadingConfig(true)
      const editableConfig = await fetchEditableConfig(selectedTool, selectedLanguage, selectedStep)
      onConfigSelected(editableConfig)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config')
    } finally {
      setLoadingConfig(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-md">
        <div className="text-red-700">{error}</div>
        <button
          onClick={() => setError(null)}
          className="mt-2 px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
        >
          Dismiss
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-sm border">
      <h2 className="text-2xl font-bold mb-6 text-gray-900">Config Editor</h2>

      <div className="space-y-6">
        {/* Tool Selection */}
        <div>
          <label htmlFor="tool-select" className="block text-sm font-medium text-gray-700 mb-2">
            Tool
          </label>
          <select
            id="tool-select"
            value={selectedTool}
            onChange={(e) => setSelectedTool(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select a tool...</option>
            {tools.map((tool) => (
              <option key={tool.id} value={tool.id}>
                {tool.title}
              </option>
            ))}
          </select>
          {selectedTool && (
            <p className="mt-1 text-sm text-gray-500">
              {tools.find(t => t.id === selectedTool)?.description}
            </p>
          )}
        </div>

        {/* Language Selection */}
        <div>
          <label htmlFor="language-select" className="block text-sm font-medium text-gray-700 mb-2">
            Language
          </label>
          <select
            id="language-select"
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select a language...</option>
            {languages.map((language) => (
              <option key={language.id} value={language.id}>
                {language.title}
              </option>
            ))}
          </select>
          {selectedLanguage && (
            <p className="mt-1 text-sm text-gray-500">
              {languages.find(l => l.id === selectedLanguage)?.description}
            </p>
          )}
        </div>

        {/* Step Selection */}
        <div>
          <label htmlFor="step-select" className="block text-sm font-medium text-gray-700 mb-2">
            Step
          </label>
          <select
            id="step-select"
            value={selectedStep}
            onChange={(e) => setSelectedStep(e.target.value)}
            disabled={!selectedTool || !selectedLanguage || loadingSteps}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          >
            <option value="">
              {loadingSteps ? 'Loading steps...' : 'Select a step...'}
            </option>
            {steps.map((step) => (
              <option key={step.id} value={step.id}>
                {step.title}
              </option>
            ))}
          </select>
          {selectedStep && (
            <p className="mt-1 text-sm text-gray-500">
              {steps.find(s => s.id === selectedStep)?.description}
            </p>
          )}
        </div>

        {/* Load Config Button */}
        <div className="pt-4">
          <button
            onClick={handleLoadConfig}
            disabled={!selectedTool || !selectedLanguage || !selectedStep || loadingConfig}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loadingConfig ? 'Loading Config...' : 'Load Editable Config'}
          </button>
        </div>
      </div>
    </div>
  )
}