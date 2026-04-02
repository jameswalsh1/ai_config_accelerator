import { ChevronDownIcon, ChevronUpIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import type { AgentEntry, WizardField } from '@/types/wizard'

interface AgentListFieldProps {
  field: WizardField
  value: AgentEntry[]
  error?: string
  onChange: (value: AgentEntry[]) => void
}

const EMPTY_AGENT = (defaultModel = ''): AgentEntry => ({
  name: '',
  description: '',
  tools: [],
  model: defaultModel,
  system_prompt: '',
})

function slugify(s: string) {
  return s.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
}

function AgentCard({
  agent,
  idx,
  availableTools,
  availableModels,
  onUpdate,
  onRemove,
}: {
  agent: AgentEntry
  idx: number
  availableTools: string[]
  availableModels: string[]
  onUpdate: (patch: Partial<AgentEntry>) => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(true)

  const toggleTool = (tool: string) => {
    const current = agent.tools ?? []
    onUpdate({ tools: current.includes(tool) ? current.filter(t => t !== tool) : [...current, tool] })
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
          {idx + 1}
        </div>
        <span className="flex-1 text-sm font-semibold text-gray-800 truncate">
          {agent.name || <span className="text-gray-400 font-normal italic">Unnamed agent</span>}
        </span>
        {agent.description && (
          <span className="hidden sm:block text-xs text-gray-400 truncate max-w-[180px]">{agent.description}</span>
        )}
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="rounded p-1 text-gray-400 hover:bg-gray-200 transition"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUpIcon className="size-4" /> : <ChevronDownIcon className="size-4" />}
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="rounded p-1 text-gray-400 hover:bg-red-100 hover:text-red-500 transition"
          aria-label="Remove agent"
        >
          <Trash2Icon className="size-4" />
        </button>
      </div>

      {expanded && (
        <div className="flex flex-col gap-4 p-4">
          {/* Row: Name + Description */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">
                Agent Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={agent.name}
                placeholder="e.g. security-reviewer"
                onChange={e => onUpdate({ name: slugify(e.target.value) })}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="text-xs text-gray-400">Lowercase + hyphens — becomes the filename.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Description</label>
              <input
                type="text"
                value={agent.description ?? ''}
                placeholder="What this agent does in one sentence"
                onChange={e => onUpdate({ description: e.target.value })}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Model */}
          {availableModels.length > 0 && (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-600">Model</label>
              <select
                value={agent.model ?? ''}
                onChange={e => onUpdate({ model: e.target.value })}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500 w-full sm:w-48"
              >
                <option value="">Default</option>
                {availableModels.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          )}

          {/* Allowed tools */}
          {availableTools.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-600">Allowed Tools</label>
              <div className="flex flex-wrap gap-1.5">
                {availableTools.map(tool => {
                  const active = (agent.tools ?? []).includes(tool)
                  return (
                    <button
                      key={tool}
                      type="button"
                      onClick={() => toggleTool(tool)}
                      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition ${
                        active
                          ? 'border-indigo-400 bg-indigo-100 text-indigo-700'
                          : 'border-gray-200 bg-gray-50 text-gray-500 hover:border-indigo-200 hover:text-indigo-600'
                      }`}
                    >
                      {tool}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* System prompt */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">System Prompt / Instructions</label>
            <textarea
              value={agent.system_prompt ?? ''}
              placeholder="Describe what this agent should do, its responsibilities, and how it should approach tasks..."
              rows={4}
              onChange={e => onUpdate({ system_prompt: e.target.value })}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-y"
            />
          </div>
        </div>
      )}
    </div>
  )
}

export function AgentListField({ field, value, error, onChange }: AgentListFieldProps) {
  const agentCfg = field.agent_config
  const availableTools = agentCfg?.available_tools ?? []
  const availableModels = agentCfg?.available_models ?? []

  const update = (idx: number, patch: Partial<AgentEntry>) => {
    const next = [...value]
    next[idx] = { ...next[idx], ...patch }
    onChange(next)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <label className="text-sm font-medium text-gray-700">
          {field.label}
          {field.required && <span className="ml-1 text-red-500">*</span>}
        </label>
        {field.description && (
          <p className="text-xs text-gray-500">{field.description}</p>
        )}
      </div>

      {value.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
          No agents defined yet. Click "Add Agent" below or use a preset role to get started.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {value.map((agent, idx) => (
          <AgentCard
            key={idx}
            agent={agent}
            idx={idx}
            availableTools={availableTools}
            availableModels={availableModels}
            onUpdate={patch => update(idx, patch)}
            onRemove={() => onChange(value.filter((_, i) => i !== idx))}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={() => onChange([...value, EMPTY_AGENT(agentCfg?.default_model ?? '')])}
        className="inline-flex items-center gap-2 self-start rounded-md border border-dashed border-indigo-300 px-4 py-2 text-sm font-medium text-indigo-600 transition hover:border-indigo-500 hover:bg-indigo-50"
      >
        <PlusIcon className="size-4" />
        Add Agent
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
