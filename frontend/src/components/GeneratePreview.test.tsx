import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GeneratePreview } from './GeneratePreview'
import type { PreviewFile } from '@/api/wizardApi'

const sampleFiles: PreviewFile[] = [
  {
    path: 'config/settings.json',
    content: '{"key": "value", "count": 42, "active": true}',
    language: 'json',
  },
  {
    path: 'docs/README.md',
    content: '# Title\n\nSome text\n\n- list item\n',
    language: 'markdown',
  },
  {
    path: 'config/rules.md',
    content: '---\ntitle: Rules\n---\nContent here',
    language: 'markdown',
  },
]

describe('GeneratePreview', () => {
  const onDownload = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders file count and config title', () => {
    render(
      <GeneratePreview
        files={sampleFiles}
        configTitle="Test Config"
        isDownloading={false}
        onDownload={onDownload}
      />
    )
    expect(screen.getByText(/3 files/)).toBeInTheDocument()
    expect(screen.getByText('Test Config')).toBeInTheDocument()
  })

  it('renders download button', () => {
    render(
      <GeneratePreview
        files={sampleFiles}
        configTitle="Test"
        isDownloading={false}
        onDownload={onDownload}
      />
    )
    const btn = screen.getByRole('button', { name: /Download ZIP/ })
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(onDownload).toHaveBeenCalledTimes(1)
  })

  it('shows downloading state', () => {
    render(
      <GeneratePreview
        files={sampleFiles}
        configTitle="Test"
        isDownloading={true}
        onDownload={onDownload}
      />
    )
    expect(screen.getByText('Downloading…')).toBeInTheDocument()
  })

  it('renders file tree with directory structure', () => {
    render(
      <GeneratePreview
        files={sampleFiles}
        configTitle="Test"
        isDownloading={false}
        onDownload={onDownload}
      />
    )
    // Should show directory names
    expect(screen.getByText('config/')).toBeInTheDocument()
    expect(screen.getByText('docs/')).toBeInTheDocument()
  })

  it('selects first file by default and shows its content', () => {
    render(
      <GeneratePreview
        files={sampleFiles}
        configTitle="Test"
        isDownloading={false}
        onDownload={onDownload}
      />
    )
    // First file path should be shown in the tab bar
    expect(screen.getByText('config/settings.json')).toBeInTheDocument()
    // JSON content should be tokenised and rendered
    expect(screen.getByText('"key"')).toBeInTheDocument()
  })

  it('renders singular file text for single file', () => {
    render(
      <GeneratePreview
        files={[sampleFiles[0]]}
        configTitle="Test"
        isDownloading={false}
        onDownload={onDownload}
      />
    )
    expect(screen.getByText(/1 file/)).toBeInTheDocument()
  })
})
