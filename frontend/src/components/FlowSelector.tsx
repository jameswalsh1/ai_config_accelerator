import { ChevronDownIcon, LayoutListIcon, SettingsIcon, StarIcon } from 'lucide-react'
import type { WizardFlow } from '@/types/wizard'

interface FlowSelectorProps {
  flows: WizardFlow[]
  activeFlow: WizardFlow | null
  isOpen: boolean
  onToggle: () => void
  onSelectFlow: (flow: WizardFlow | null) => void
  onManageFlows?: () => void
}

export function FlowSelector({ flows, activeFlow, isOpen, onToggle, onSelectFlow, onManageFlows }: FlowSelectorProps) {
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm transition hover:border-indigo-300 hover:text-indigo-600"
        title="Choose a wizard flow to customise which steps you see and in what order"
      >
        <LayoutListIcon className="size-3.5" />
        <span className="max-w-[120px] truncate">
          {activeFlow ? activeFlow.name : 'Default Flow'}
        </span>
        <ChevronDownIcon className="size-3" />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-20 mt-1 w-64 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          <div className="border-b border-gray-100 px-3 py-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Wizard Flows</p>
          </div>

          {/* Default (no flow) option */}
          <button
            type="button"
            onClick={() => onSelectFlow(null)}
            className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition hover:bg-gray-50 ${
              !activeFlow ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700'
            }`}
          >
            <LayoutListIcon className="size-3.5 text-gray-400" />
            <span className="flex-1">Default (all steps)</span>
            {!activeFlow && (
              <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">Active</span>
            )}
          </button>

          {flows.map(flow => (
            <button
              key={flow.id}
              type="button"
              onClick={() => onSelectFlow(flow)}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition hover:bg-gray-50 ${
                activeFlow?.id === flow.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700'
              }`}
            >
              {flow.is_default ? (
                <StarIcon className="size-3.5 text-amber-400 fill-amber-400" />
              ) : (
                <LayoutListIcon className="size-3.5 text-gray-400" />
              )}
              <div className="flex-1 min-w-0">
                <span className="block truncate text-sm">{flow.name}</span>
                {flow.description && (
                  <span className="block truncate text-xs text-gray-400">{flow.description}</span>
                )}
              </div>
              {activeFlow?.id === flow.id && (
                <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">Active</span>
              )}
            </button>
          ))}

          {onManageFlows && (
            <div className="border-t border-gray-100 mt-1 pt-1">
              <button
                type="button"
                onClick={() => { onManageFlows(); onToggle(); }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-gray-500 transition hover:bg-gray-50 hover:text-indigo-600"
              >
                <SettingsIcon className="size-3.5" />
                Manage Flows
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
