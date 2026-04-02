import { useEffect, useState } from 'react'
import { fetchConfigs, fetchWizardConfig } from '@/api/wizardApi'
import type { WizardConfig, WizardConfigSummary } from '@/types/wizard'
import { Wizard } from '@/components/Wizard'
import { BotIcon, Loader2Icon } from 'lucide-react'

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
  const [configs, setConfigs] = useState<WizardConfigSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedConfig, setSelectedConfig] = useState<WizardConfig | null>(null)
  const [loadingConfig, setLoadingConfig] = useState<string | null>(null)

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

  const navbar = (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
        <img
          src="https://www.version1.com/wp-content/uploads/2024/04/version1-logo.svg"
          alt="Version 1"
          className="h-8 w-auto"
        />
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
            <Wizard config={selectedConfig} onBack={() => setSelectedConfig(null)} />
          </div>
        </main>
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
