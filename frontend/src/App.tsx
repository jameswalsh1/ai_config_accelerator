import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { fetchConfigs, fetchWizardConfig } from '@/api/wizardApi'
import type { WizardConfig, WizardConfigSummary, EditableStep } from '@/types/wizard'
import { BotIcon, Loader2Icon } from 'lucide-react'

const Wizard = lazy(() => import('@/components/Wizard').then(m => ({ default: m.Wizard })))
const ConfigEditorEntry = lazy(() => import('@/components/ConfigEditorEntry').then(m => ({ default: m.ConfigEditorEntry })))
const ConfigEditor = lazy(() => import('@/components/ConfigEditor').then(m => ({ default: m.ConfigEditor })))
const AuditLog = lazy(() => import('@/components/AuditLog').then(m => ({ default: m.AuditLog })))
const SnapshotManager = lazy(() => import('@/components/SnapshotManager').then(m => ({ default: m.SnapshotManager })))
const CoverageMatrix = lazy(() => import('@/components/CoverageMatrix').then(m => ({ default: m.CoverageMatrix })))

function LazyFallback() {
  return (
    <div className="flex justify-center py-16">
      <Loader2Icon className="size-8 animate-spin text-indigo-400" />
    </div>
  )
}

const TARGET_LABELS: Record<string, string> = {
  claude: 'Claude',
  cursor: 'Cursor',
  copilot: 'GitHub Copilot',
  all: 'All Tools',
  
}

const TARGET_COLORS: Record<string, string> = {
  claude: 'bg-orange-100 text-orange-700',
  cursor: 'bg-blue-100 text-blue-700',
  copilot: 'bg-green-100 text-green-700',
  all: 'bg-purple-100 text-purple-700',
}

function App() {
  const [mode, setMode] = useState<'config-selection' | 'wizard' | 'config-editor' | 'audit-log' | 'coverage'>('config-selection')
  const [configs, setConfigs] = useState<WizardConfigSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedConfig, setSelectedConfig] = useState<WizardConfig | null>(null)
  const [loadingConfig, setLoadingConfig] = useState<string | null>(null)
  const [editableConfig, setEditableConfig] = useState<EditableStep | null>(null)
  const [selectedTool, setSelectedTool] = useState<string>('')
  const [selectedLanguage, setSelectedLanguage] = useState<string>('')
  const [snapshotReloadTrigger, setSnapshotReloadTrigger] = useState(0)
  /** Set when navigating from the coverage matrix to pre-select tool/language in the editor. */
  const [preselectedTool, setPreselectedTool] = useState<string | undefined>()
  const [preselectedLanguage, setPreselectedLanguage] = useState<string | undefined>()

  const handleConfigSelected = useCallback((config: EditableStep, tool: string, language: string) => {
    setEditableConfig(config)
    setSelectedTool(tool)
    setSelectedLanguage(language)
  }, [])

  useEffect(() => {
    fetchConfigs()
      .then(setConfigs)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load configurations'))
      .finally(() => setLoading(false))
  }, [])

  const handleSelectConfig = async (id: string) => {
    setLoadingConfig(id)
    try {
      const config = await fetchWizardConfig(id)
      setSelectedConfig(config)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoadingConfig(null)
    }
  }

  const handleFieldChange = (fieldId: string, value: unknown, source?: string) => {
    if (!editableConfig) return
    setEditableConfig(prev => {
      if (!prev) return prev
      return {
        ...prev,
        step: {
          ...prev.step,
          fields: prev.step.fields.map(field =>
            field.id === fieldId ? { ...field, current_value: value, current_value_source: source } : field
          )
        }
      }
    })
  }

  const handleMetadataUpdate = (updatedStep: EditableStep) => {
    setEditableConfig(updatedStep)
  }

  const navbar = (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
        <img
          src="https://www.version1.com/wp-content/uploads/2024/04/version1-logo.svg"
          alt="Version 1"
          className="h-8 w-auto"
        />
        <nav className="flex items-center gap-4" aria-label="Main navigation">
          <button
            onClick={() => {
              setMode('config-selection')
              setSelectedConfig(null)
              setEditableConfig(null)
            }}
            aria-current={mode === 'config-selection' ? 'page' : undefined}
            className={`px-3 py-1 text-sm rounded ${
              mode === 'config-selection'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Config Wizard
          </button>
          <button
            onClick={() => {
              setMode('config-editor')
              setSelectedConfig(null)
              setEditableConfig(null)
            }}
            aria-current={mode === 'config-editor' ? 'page' : undefined}
            className={`px-3 py-1 text-sm rounded ${
              mode === 'config-editor'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Config Editor
          </button>
          <button
            onClick={() => {
              setMode('audit-log')
              setSelectedConfig(null)
              setEditableConfig(null)
            }}
            aria-current={mode === 'audit-log' ? 'page' : undefined}
            className={`px-3 py-1 text-sm rounded ${
              mode === 'audit-log'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Audit Log
          </button>
          <button
            onClick={() => {
              setMode('coverage')
              setSelectedConfig(null)
              setEditableConfig(null)
            }}
            aria-current={mode === 'coverage' ? 'page' : undefined}
            className={`px-3 py-1 text-sm rounded ${
              mode === 'coverage'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Coverage
          </button>
        </nav>
        <span className="text-xs font-medium uppercase tracking-widest text-gray-400">
          AI Config Accelerator
        </span>
      </div>
    </header>
  )

  if (selectedConfig) {
    return (
      <>
        {navbar}
        <main className="min-h-screen bg-gray-50 px-4 py-10">
          <div className="mx-auto max-w-2xl">
            <Suspense fallback={<LazyFallback />}>
              <Wizard config={selectedConfig} onBack={() => setSelectedConfig(null)} />
            </Suspense>
          </div>
        </main>
      </>
    )
  }
  if (mode === 'coverage') {
    return (
      <>
        {navbar}
        <main className="min-h-screen bg-gray-50 px-4 py-12">
          <div className="mx-auto max-w-5xl">
            <Suspense fallback={<LazyFallback />}>
              <CoverageMatrix
                onNavigateToEditor={(toolId, languageId) => {
                  setPreselectedTool(toolId)
                  setPreselectedLanguage(languageId)
                  setSelectedTool(toolId)
                  setSelectedLanguage(languageId)
                  setEditableConfig(null)
                  setMode('config-editor')
                }}
              />
            </Suspense>
          </div>
        </main>
      </>
    )
  }
  if (mode === 'audit-log') {
    return (
      <>
        {navbar}
        <main className="min-h-screen bg-gray-50 px-4 py-12">
          <div className="mx-auto max-w-4xl">
            <Suspense fallback={<LazyFallback />}>
              <AuditLog />
            </Suspense>
          </div>
        </main>
      </>
    )
  }
  if (mode === 'config-editor') {
    return (
      <>
        {navbar}
        <Suspense fallback={<LazyFallback />}>
          <ConfigEditorEntry
            reloadTrigger={snapshotReloadTrigger}
            initialTool={preselectedTool}
            initialLanguage={preselectedLanguage}
            onConfigSelected={handleConfigSelected}
          />
          <main className="min-h-screen bg-gray-50 px-6 py-8">
            <div className="mx-auto max-w-5xl">
              {editableConfig ? (
                <div className="flex flex-col gap-4">
                  <ConfigEditor
                    editableStep={editableConfig}
                    onFieldChange={handleFieldChange}
                    onMetadataUpdate={handleMetadataUpdate}
                    tool={selectedTool}
                    language={selectedLanguage}
                  />
                  {selectedLanguage && (
                    <SnapshotManager
                      scope="language"
                      target={selectedLanguage}
                      onRestored={() => setSnapshotReloadTrigger(t => t + 1)}
                    />
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-24 text-center text-gray-400">
                  <p className="text-lg font-medium">Select a tool and language above to get started</p>
                  <p className="text-sm mt-1">Steps will load automatically</p>
                </div>
              )}
            </div>
          </main>
        </Suspense>
      </>
    )
  }
  return (
    <>
      {navbar}
      <main className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-10 flex flex-col items-center gap-3 text-center">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-600 shadow-md">
            <BotIcon className="size-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">AI Config Accelerator</h1>
          <p className="text-sm text-gray-500 max-w-sm">
            Pick a configuration wizard below. Answer a few questions and download a ready-to-use
            config ZIP for your AI coding assistant.
          </p>
        </div>

        {loading && (
          <div className="flex justify-center py-16">
            <Loader2Icon className="size-8 animate-spin text-indigo-400" />
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            <strong>Error:</strong> {error}
            <p className="mt-1 text-xs text-red-500">Make sure the backend is running on port 8000.</p>
          </div>
        )}

        {!loading && !error && configs.length === 0 && (
          <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
            No configurations found. Add a JSON file to{' '}
            <code className="font-mono text-xs">backend/app/data/wizard_configs/</code>.
          </div>
        )}

        {!loading && configs.length > 0 && (
          <div className="grid gap-4">
            {configs.map(cfg => (
              <button
                key={cfg.id}
                type="button"
                onClick={() => handleSelectConfig(cfg.id)}
                disabled={loadingConfig === cfg.id}
                className="group flex w-full items-start gap-4 rounded-xl border border-gray-200 bg-white p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md disabled:opacity-60"
              >
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100 transition">
                  {loadingConfig === cfg.id ? (
                    <Loader2Icon className="size-5 animate-spin" />
                  ) : (
                    <BotIcon className="size-5" />
                  )}
                </div>
                <div className="flex flex-1 flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">{cfg.title}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        TARGET_COLORS[cfg.target] ?? 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {TARGET_LABELS[cfg.target] ?? cfg.target}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">{cfg.description}</p>
                </div>
                <span className="self-center text-gray-300 transition group-hover:text-indigo-400">→</span>
              </button>
            ))}
          </div>
        )}
      </div>
      </main>
    </>
  )
}

export default App
