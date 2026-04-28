import { useState } from 'react'
import { X, Plus, Copy } from 'lucide-react'
import { createLanguageConfig, type CreateLanguagePayload, type LanguageOption } from '@/api/wizardApi'

interface CreateLanguageModalProps {
  existingLanguages: LanguageOption[]
  onCreated: (language: LanguageOption) => void
  onClose: () => void
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function CreateLanguageModal({ existingLanguages, onCreated, onClose }: CreateLanguageModalProps) {
  const [title, setTitle] = useState('')
  const [languageId, setLanguageId] = useState('')
  const [description, setDescription] = useState('')
  const [basedOn, setBasedOn] = useState('')
  const [idManuallyEdited, setIdManuallyEdited] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleTitleChange = (value: string) => {
    setTitle(value)
    if (!idManuallyEdited) {
      setLanguageId(slugify(value))
    }
  }

  const handleIdChange = (value: string) => {
    setLanguageId(value.toLowerCase().replace(/[^a-z0-9-]/g, ''))
    setIdManuallyEdited(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!title.trim()) { setError('Title is required'); return }
    if (!languageId.trim()) { setError('Language ID is required'); return }

    const payload: CreateLanguagePayload = {
      language_id: languageId.trim(),
      title: title.trim(),
      description: description.trim() || undefined,
      based_on: basedOn || undefined,
    }

    try {
      setSaving(true)
      const created = await createLanguageConfig(payload)
      onCreated(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create language')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative w-full max-w-lg mx-4 bg-white rounded-xl shadow-2xl border border-gray-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-100">
              <Plus className="size-4 text-indigo-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">New Language Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Title */}
          <div>
            <label htmlFor="lang-title" className="block text-sm font-medium text-gray-700 mb-1.5">
              Display Name <span className="text-red-500">*</span>
            </label>
            <input
              id="lang-title"
              type="text"
              value={title}
              onChange={e => handleTitleChange(e.target.value)}
              placeholder="e.g. Python – Data Science"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              autoFocus
            />
            <p className="mt-1 text-xs text-gray-500">
              Shown in the language dropdown throughout the app.
            </p>
          </div>

          {/* Language ID */}
          <div>
            <label htmlFor="lang-id" className="block text-sm font-medium text-gray-700 mb-1.5">
              Language ID <span className="text-red-500">*</span>
            </label>
            <input
              id="lang-id"
              type="text"
              value={languageId}
              onChange={e => handleIdChange(e.target.value)}
              placeholder="e.g. python-datascience"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            <p className="mt-1 text-xs text-gray-500">
              Unique slug used in config files. Lowercase, alphanumeric, hyphens only.
            </p>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="lang-desc" className="block text-sm font-medium text-gray-700 mb-1.5">
              Description
            </label>
            <textarea
              id="lang-desc"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="e.g. NumPy, pandas, PyTorch and Jupyter stack"
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
            />
          </div>

          {/* Based On */}
          <div>
            <label htmlFor="lang-based-on" className="block text-sm font-medium text-gray-700 mb-1.5">
              <span className="inline-flex items-center gap-1.5">
                <Copy className="size-3.5" />
                Copy settings from existing language
              </span>
            </label>
            <select
              id="lang-based-on"
              value={basedOn}
              onChange={e => setBasedOn(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">Start from scratch</option>
              {existingLanguages.map(lang => (
                <option key={lang.id} value={lang.id}>
                  {lang.title}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Copies field overrides and presets as a starting point — you can edit them after creation.
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? 'Creating…' : 'Create Language'}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
