import { useMemo, useState } from 'react'
import { FileIcon, DownloadIcon, Loader2Icon, ChevronRightIcon } from 'lucide-react'
import type { PreviewFile } from '@/api/wizardApi'

interface GeneratePreviewProps {
  files: PreviewFile[]
  configTitle: string
  isDownloading: boolean
  onDownload: () => void
}

// Very small syntax tokeniser — avoids a heavy dependency.
// Returns an array of {text, className} spans.
function tokenise(content: string, language: string): { text: string; cls: string }[] {
  if (language === 'json') return tokeniseJson(content)
  if (language === 'markdown' || language === 'text') return tokeniseMd(content)
  return [{ text: content, cls: '' }]
}

function tokeniseJson(src: string): { text: string; cls: string }[] {
  // Split on JSON tokens: strings, numbers, booleans, null, structural chars
  const re = /("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}[\]:,]|\s+)/g
  const out: { text: string; cls: string }[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    if (m.index > last) out.push({ text: src.slice(last, m.index), cls: '' })
    const tok = m[0]
    let cls = ''
    if (tok.startsWith('"')) cls = 'text-green-400'
    else if (/^-?\d/.test(tok)) cls = 'text-yellow-300'
    else if (tok === 'true' || tok === 'false' || tok === 'null') cls = 'text-purple-300'
    else if (/[{}[\]]/.test(tok)) cls = 'text-gray-300 font-semibold'
    out.push({ text: tok, cls })
    last = m.index + tok.length
  }
  if (last < src.length) out.push({ text: src.slice(last), cls: '' })
  return out
}

function tokeniseMd(src: string): { text: string; cls: string }[] {
  const lines = src.split('\n')
  const out: { text: string; cls: string }[] = []
  for (const line of lines) {
    if (/^#{1,6} /.test(line)) {
      out.push({ text: line, cls: 'text-indigo-300 font-semibold' })
    } else if (/^---/.test(line)) {
      out.push({ text: line, cls: 'text-yellow-400' })
    } else if (/^\s*[-*+] /.test(line)) {
      out.push({ text: line, cls: 'text-gray-200' })
    } else if (/^\s*[a-zA-Z_]+:/.test(line)) {
      const colon = line.indexOf(':')
      out.push({ text: line.slice(0, colon + 1), cls: 'text-sky-300' })
      out.push({ text: line.slice(colon + 1), cls: 'text-gray-200' })
    } else {
      out.push({ text: line, cls: 'text-gray-300' })
    }
    out.push({ text: '\n', cls: '' })
  }
  return out
}

// Build a tree structure for the file browser sidebar
interface FileNode {
  name: string
  path: string
  isDir: boolean
  children: FileNode[]
  file?: PreviewFile
}

function buildTree(files: PreviewFile[]): FileNode[] {
  const root: FileNode[] = []

  for (const file of files) {
    const parts = file.path.split('/')
    let nodes = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isLast = i === parts.length - 1
      let node = nodes.find(n => n.name === part)
      if (!node) {
        node = { name: part, path: parts.slice(0, i + 1).join('/'), isDir: !isLast, children: [] }
        if (isLast) node.file = file
        nodes.push(node)
      }
      nodes = node.children
    }
  }

  const sort = (ns: FileNode[]) => {
    ns.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    ns.forEach(n => sort(n.children))
  }
  sort(root)
  return root
}

function FileTree({
  nodes,
  selected,
  onSelect,
  depth = 0,
}: {
  nodes: FileNode[]
  selected: string
  onSelect: (f: PreviewFile) => void
  depth?: number
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})

  return (
    <ul className="text-sm">
      {nodes.map(node => (
        <li key={node.path}>
          {node.isDir ? (
            <>
              <button
                onClick={() => setOpen(p => ({ ...p, [node.path]: !p[node.path] }))}
                className="flex w-full items-center gap-1.5 px-2 py-1 text-left text-gray-400 hover:text-gray-200 transition-colors"
                style={{ paddingLeft: `${depth * 12 + 8}px` }}
              >
                <ChevronRightIcon
                  className={`size-3 shrink-0 transition-transform ${open[node.path] ? 'rotate-90' : ''}`}
                />
                <span className="font-medium text-gray-300">{node.name}/</span>
              </button>
              {open[node.path] && (
                <FileTree nodes={node.children} selected={selected} onSelect={onSelect} depth={depth + 1} />
              )}
            </>
          ) : (
            <button
              onClick={() => node.file && onSelect(node.file)}
              className={`flex w-full items-center gap-1.5 py-1 text-left transition-colors rounded-sm ${
                selected === node.path
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              }`}
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
            >
              <FileIcon className="size-3 shrink-0" />
              <span className="truncate">{node.name}</span>
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function GeneratePreview({ files, configTitle, isDownloading, onDownload }: GeneratePreviewProps) {
  const [selected, setSelected] = useState<PreviewFile>(files[0])
  const tree = useMemo(() => buildTree(files), [files])
  const tokens = useMemo(() => tokenise(selected.content, selected.language), [selected.content, selected.language])

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Preview Generated Files</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {files.length} file{files.length !== 1 ? 's' : ''} ready for{' '}
            <span className="font-medium text-gray-700">{configTitle}</span>
          </p>
        </div>
        <button
          onClick={onDownload}
          disabled={isDownloading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {isDownloading ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <DownloadIcon className="size-4" />
          )}
          {isDownloading ? 'Downloading…' : 'Download ZIP'}
        </button>
      </div>

      {/* File browser + content pane */}
      <div className="flex rounded-xl border border-gray-200 overflow-hidden shadow-sm" style={{ minHeight: '520px' }}>
        {/* Sidebar — file tree */}
        <div className="w-56 shrink-0 bg-gray-800 border-r border-gray-700 overflow-y-auto py-2">
          <p className="px-3 pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Files
          </p>
          <FileTree nodes={tree} selected={selected.path} onSelect={setSelected} />
        </div>

        {/* Content pane */}
        <div className="flex-1 flex flex-col bg-gray-900 overflow-hidden">
          {/* Tab bar */}
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-700 bg-gray-800">
            <FileIcon className="size-3.5 text-gray-400 shrink-0" />
            <span className="text-xs text-gray-300 font-mono truncate">{selected.path}</span>
            <span className="ml-auto text-xs text-gray-500 shrink-0">{selected.language}</span>
          </div>

          {/* Code */}
          <div className="flex-1 overflow-auto">
            <pre className="p-4 text-xs font-mono leading-relaxed text-gray-200 min-h-full">
              <code>
                {tokens.map((tok, i) =>
                  tok.cls ? (
                    <span key={i} className={tok.cls}>{tok.text}</span>
                  ) : (
                    tok.text
                  )
                )}
              </code>
            </pre>
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-center">
        Review your configuration files above, then click <strong>Download ZIP</strong> to save them.
      </p>
    </div>
  )
}
