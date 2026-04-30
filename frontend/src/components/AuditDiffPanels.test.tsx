import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ActionBadge, ScopeBadge, Value, DiffRow, FieldDiffPanel, StepDiffPanel } from './AuditDiffPanels'
import type { AuditFieldDiff, AuditStepDiff } from '@/api/wizardApi'

describe('ActionBadge', () => {
  it('renders create action with text', () => {
    render(<ActionBadge action="create" />)
    expect(screen.getByText('create')).toBeInTheDocument()
  })

  it('renders update action', () => {
    render(<ActionBadge action="update" />)
    expect(screen.getByText('update')).toBeInTheDocument()
  })

  it('renders delete action', () => {
    render(<ActionBadge action="delete" />)
    expect(screen.getByText('delete')).toBeInTheDocument()
  })
})

describe('ScopeBadge', () => {
  it('renders scope text', () => {
    render(<ScopeBadge scope="language" />)
    expect(screen.getByText('language')).toBeInTheDocument()
  })

  it('handles unknown scope', () => {
    render(<ScopeBadge scope="custom" />)
    expect(screen.getByText('custom')).toBeInTheDocument()
  })
})

describe('Value', () => {
  it('renders null as dash', () => {
    const { container } = render(<Value val={null} />)
    expect(container.textContent).toBe('—')
  })

  it('renders undefined as dash', () => {
    const { container } = render(<Value val={undefined} />)
    expect(container.textContent).toBe('—')
  })

  it('renders strings directly', () => {
    const { container } = render(<Value val="hello world" />)
    expect(container.textContent).toBe('hello world')
  })

  it('renders empty string as (empty)', () => {
    const { container } = render(<Value val="" />)
    expect(container.textContent).toBe('(empty)')
  })

  it('renders objects as formatted JSON', () => {
    const { container } = render(<Value val={{ key: 'val' }} />)
    expect(container.textContent).toContain('"key"')
    expect(container.textContent).toContain('"val"')
  })

  it('renders booleans', () => {
    const { container } = render(<Value val={true} />)
    expect(container.textContent).toBe('true')
  })
})

describe('DiffRow', () => {
  it('renders label and before/after values', () => {
    render(<DiffRow label="Title" before="old" after="new" />)
    expect(screen.getByText('Title')).toBeInTheDocument()
    expect(screen.getByText('old')).toBeInTheDocument()
    expect(screen.getByText('new')).toBeInTheDocument()
  })
})

describe('FieldDiffPanel', () => {
  function makeDiff(overrides: Partial<AuditFieldDiff> = {}): AuditFieldDiff {
    return {
      field_id: 'test_field',
      field_type: 'text',
      change_type: 'modified',
      value_changed: false,
      before_value: null,
      after_value: null,
      label_changed: false,
      before_label: null,
      after_label: null,
      description_changed: false,
      preset_changes: [],
      locking_changes: null,
      hidden_changed: false,
      before_hidden: null,
      after_hidden: null,
      ...overrides,
    }
  }

  it('renders nothing when no changes', () => {
    const { container } = render(<FieldDiffPanel fd={makeDiff()} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders field id when value changed', () => {
    render(
      <FieldDiffPanel
        fd={makeDiff({
          value_changed: true,
          before_value: 'old',
          after_value: 'new',
        })}
      />
    )
    expect(screen.getByText('test_field')).toBeInTheDocument()
    expect(screen.getByText('value')).toBeInTheDocument()
  })

  it('shows locking badge when locking changes', () => {
    render(
      <FieldDiffPanel
        fd={makeDiff({
          locking_changes: {
            change_type: 'modified',
            before_state: 'free',
            after_state: 'locked',
          },
        })}
      />
    )
    expect(screen.getByText('locking')).toBeInTheDocument()
  })

  it('expands to show diff details on click', () => {
    render(
      <FieldDiffPanel
        fd={makeDiff({
          value_changed: true,
          before_value: 'old_val',
          after_value: 'new_val',
        })}
      />
    )
    // Initially collapsed — diff rows not visible
    expect(screen.queryByText('old_val')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByText('test_field'))
    expect(screen.getByText('old_val')).toBeInTheDocument()
    expect(screen.getByText('new_val')).toBeInTheDocument()
  })

  it('shows preset changes count badge', () => {
    render(
      <FieldDiffPanel
        fd={makeDiff({
          preset_changes: [
            { change_type: 'added', label: 'preset1', before_value: null, after_value: 'x' },
            { change_type: 'added', label: 'preset2', before_value: null, after_value: 'y' },
          ],
        })}
      />
    )
    expect(screen.getByText('2 presets')).toBeInTheDocument()
  })
})

describe('StepDiffPanel', () => {
  function makeStepDiff(overrides: Partial<AuditStepDiff> = {}): AuditStepDiff {
    return {
      step_id: 'test_step',
      change_type: 'modified',
      title_changed: false,
      before_title: null,
      after_title: null,
      description_changed: false,
      before_description: null,
      after_description: null,
      fields_added: [],
      fields_removed: [],
      field_diffs: [],
      ...overrides,
    }
  }

  it('renders step id and change count', () => {
    render(
      <StepDiffPanel
        sd={makeStepDiff({
          fields_added: ['new_field'],
          fields_removed: ['old_field'],
        })}
      />
    )
    expect(screen.getByText('test_step')).toBeInTheDocument()
    expect(screen.getByText('2 changes')).toBeInTheDocument()
  })

  it('renders singular change text', () => {
    render(
      <StepDiffPanel
        sd={makeStepDiff({
          fields_added: ['new_field'],
        })}
      />
    )
    expect(screen.getByText('1 change')).toBeInTheDocument()
  })

  it('expands to show field details on click', () => {
    render(
      <StepDiffPanel
        sd={makeStepDiff({
          fields_added: ['added_field'],
          fields_removed: ['removed_field'],
        })}
      />
    )
    // Click to expand
    fireEvent.click(screen.getByText('test_step'))
    expect(screen.getByText(/added_field/)).toBeInTheDocument()
    expect(screen.getByText(/removed_field/)).toBeInTheDocument()
  })
})
