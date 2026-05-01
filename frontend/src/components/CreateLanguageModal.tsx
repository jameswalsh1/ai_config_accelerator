import { useState, useEffect, useRef } from 'react'
import { X, Plus, Copy, ArrowRight, Tag } from 'lucide-react'
import { createLanguageConfig, fetchLanguageTags, type CreateLanguagePayload, type LanguageOption } from '@/api/wizardApi'

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
  const [description, setDescription] = useState('')
  const [basedOn, setBasedOn] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Clone & Diverge state
  const [sourceTags, setSourceTags] = useState<string[]>([])
  const [tagsLoading, setTagsLoading] = useState(false)
  // tagRemap: entries the user has configured — { from: string, to: string }
  const [tagRemap, setTagRemap] = useState<Array<{ from: string; to: string }>>([])

  // Derived language ID shown as a preview
  const derivedId = slugify(title)

  // Refs to read current values without adding them as effect dependencies
  const derivedIdRef = useRef(derivedId)
  derivedIdRef.current = derivedId
  const basedOnRef = useRef(basedOn)
  basedOnRef.current = basedOn

  // When basedOn changes, fetch the source language's tags and pre-populate remap
  useEffect(() => {
    if (!basedOn) {
      setSourceTags([])
      setTagRemap([])
      return
    }
    setTagsLoading(true)
    fetchLanguageTags(basedOn)
      .then(tags => {
        setSourceTags(tags)
        const currentId = derivedIdRef.current
        setTagRemap(tags.map(t => ({ from: t, to: t === basedOn ? (currentId || t) : t })))
      })
      .catch(() => {
        setSourceTags([])
        setTagRemap([])
      })
      .finally(() => setTagsLoading(false))
  }, [basedOn])

  // When derived ID changes, update any remap "to" that was auto-set from basedOn
  useEffect(() => {
    const currentBasedOn = basedOnRef.current
    if (!currentBasedOn) return
    setTagRemap(prev => {
      if (prev.length === 0) return prev
      return prev.map(entry =>
        entry.from === currentBasedOn && entry.to === currentBasedOn ? { ...entry, to: derivedId || currentBasedOn } : entry
      )
    })
  }, [derivedId])

  const handleTagToChange = (index: number, value: string) => {
    setTagRemap(prev => prev.map((entry, i) => i === index ? { ...entry, to: value.toLowerCase().replace(/[^a-z0-9-]/g, '') } : entry))
  }

  const buildTagRemapPayload = (): Record<string, string> | undefined => {
    if (!basedOn || tagRemap.length === 0) return undefined
    const result: Record<string, string> = {}
    for (const { from, to } of tagRemap) {
      if (from !== to && from && to) result[from] = to
    }
    return Object.keys(result).length > 0 ? result : undefined
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!title.trim()) { setError('Title is required'); return }

    const payload: CreateLanguagePayload = {
      title: title.trim(),
      description: description.trim() || undefined,
      based_on: basedOn || undefined,
      tag_remap: buildTagRemapPayload(),
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

  const isCloning = !!basedOn
  const sourceLanguageTitle = existingLanguages.find(l => l.id === basedOn)?.title ?? basedOn

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative w-full max-w-lg mx-4 bg-white rounded-xl shadow-2xl border border-gray-200 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-100">
              {isCloning ? <Copy className="size-4 text-indigo-600" /> : <Plus className="size-4 text-indigo-600" />}
            </div>
            <h2 className="text-lg font-semibold text-gray-900">
              {isCloning ? 'Clone & Diverge' : 'New Language Configuration'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Scrollable form body */}
        <form onSubmit={e => { void handleSubmit(e) }} className="px-6 py-5 space-y-5 overflow-y-auto">
          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Based On — shown first so the heading can react to it */}
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
              Copies all field overrides, metadata overrides, and step overrides as a starting point.
            </p>
          </div>

          {/* Title */}
          <div>
            <label htmlFor="lang-title" className="block text-sm font-medium text-gray-700 mb-1.5">
              Display Name <span className="text-red-500">*</span>
            </label>
            <input
              id="lang-title"
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Python – Data Science"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              autoFocus
            />
            {derivedId && (
              <p className="mt-1 text-xs text-gray-500">
                ID: <span className="font-mono text-gray-700">{derivedId}</span>
              </p>
            )}
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

          {/* Clone & Diverge: tag remap section — only shown when cloning */}
          {isCloning && (
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Tag className="size-4 text-indigo-600 shrink-0" />
                <span className="text-sm font-medium text-indigo-900">Preset tag remapping</span>
              </div>
              <p className="text-xs text-indigo-700">
                Presets from <strong>{sourceLanguageTitle}</strong> will be copied. Rename any tags that should differ in the new language (e.g. <code className="font-mono bg-white/60 px-1 rounded">{basedOn}</code> → <code className="font-mono bg-white/60 px-1 rounded">{derivedId || 'new-id'}</code>).
              </p>

              {tagsLoading && (
                <p className="text-xs text-indigo-500 animate-pulse">Loading tags…</p>
              )}

              {!tagsLoading && sourceTags.length === 0 && (
                <p className="text-xs text-indigo-500 italic">No tags found in source language presets.</p>
              )}

              {!tagsLoading && tagRemap.length > 0 && (
                <div className="space-y-2">
                  <div className="grid grid-cols-[1fr_auto_1fr] gap-2 text-xs font-medium text-indigo-700 px-1">
                    <span>Source tag</span>
                    <span />
                    <span>New tag</span>
                  </div>
                  {tagRemap.map((entry, i) => (
                    <div key={entry.from} className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                      <div className="px-2 py-1.5 rounded bg-white border border-indigo-200 text-xs font-mono text-gray-700 truncate">
                        {entry.from}
                      </div>
                      <ArrowRight className="size-3.5 text-indigo-400 shrink-0" />
                      <input
                        type="text"
                        value={entry.to}
                        onChange={e => handleTagToChange(i, e.target.value)}
                        placeholder={entry.from}
                        className="px-2 py-1.5 rounded border border-indigo-200 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-transparent bg-white"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving
                ? (isCloning ? 'Cloning…' : 'Creating…')
                : (isCloning ? 'Clone & Diverge' : 'Create Language')}
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
