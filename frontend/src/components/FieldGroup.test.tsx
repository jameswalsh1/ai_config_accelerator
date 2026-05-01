import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FieldGroup, groupFieldsByStatus } from './FieldGroup'
import type { EditableField } from '@/types/wizard'

describe('FieldGroup', () => {
  it('renders title and count', () => {
    render(
      <FieldGroup title="Locked Fields" count={3} isExpanded={false} onToggle={() => {}} icon="red">
        <div>child content</div>
      </FieldGroup>
    )
    expect(screen.getByText('Locked Fields')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('hides children when collapsed', () => {
    render(
      <FieldGroup title="Test" count={1} isExpanded={false} onToggle={() => {}} icon="gray">
        <div>hidden child</div>
      </FieldGroup>
    )
    expect(screen.queryByText('hidden child')).not.toBeInTheDocument()
  })

  it('shows children when expanded', () => {
    render(
      <FieldGroup title="Test" count={1} isExpanded={true} onToggle={() => {}} icon="gray">
        <div>visible child</div>
      </FieldGroup>
    )
    expect(screen.getByText('visible child')).toBeInTheDocument()
  })

  it('calls onToggle when header is clicked', () => {
    const onToggle = vi.fn()
    render(
      <FieldGroup title="Test" count={1} isExpanded={false} onToggle={onToggle} icon="indigo">
        <div>child</div>
      </FieldGroup>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })
})

describe('groupFieldsByStatus', () => {
  function makeField(overrides: Partial<EditableField>): EditableField {
    return {
      id: 'f1',
      type: 'text',
      label: 'Field',
      required: false,
      editability: 'free',
      is_locked: false,
      is_default: true,
      ...overrides,
    } as EditableField
  }

  it('groups locked fields correctly', () => {
    const fields = [
      makeField({ id: 'a', is_locked: true }),
      makeField({ id: 'b', is_locked: false, is_default: true }),
    ]
    const result = groupFieldsByStatus(fields)
    expect(result.locked).toHaveLength(1)
    expect(result.locked[0].id).toBe('a')
    expect(result.default).toHaveLength(1)
    expect(result.default[0].id).toBe('b')
  })

  it('groups overridden fields (not default, not locked)', () => {
    const fields = [
      makeField({ id: 'a', is_locked: false, is_default: false }),
    ]
    const result = groupFieldsByStatus(fields)
    expect(result.overridden).toHaveLength(1)
    expect(result.overridden[0].id).toBe('a')
  })

  it('groups suggested fields', () => {
    const fields = [
      makeField({ id: 'a', is_locked: false, is_default: true, editability: 'suggested' }),
    ]
    const result = groupFieldsByStatus(fields)
    expect(result.suggested).toHaveLength(1)
    expect(result.default).toHaveLength(0)
  })

  it('returns empty arrays when no fields', () => {
    const result = groupFieldsByStatus([])
    expect(result.overridden).toHaveLength(0)
    expect(result.default).toHaveLength(0)
    expect(result.locked).toHaveLength(0)
    expect(result.suggested).toHaveLength(0)
  })

  it('handles mixed field statuses', () => {
    const fields = [
      makeField({ id: 'locked1', is_locked: true }),
      makeField({ id: 'locked2', is_locked: true }),
      makeField({ id: 'overridden1', is_locked: false, is_default: false }),
      makeField({ id: 'suggested1', is_locked: false, is_default: true, editability: 'suggested' }),
      makeField({ id: 'default1', is_locked: false, is_default: true, editability: 'free' }),
      makeField({ id: 'default2', is_locked: false, is_default: true, editability: 'defaulted' }),
    ]
    const result = groupFieldsByStatus(fields)
    expect(result.locked).toHaveLength(2)
    expect(result.overridden).toHaveLength(1)
    expect(result.suggested).toHaveLength(1)
    expect(result.default).toHaveLength(2)
  })
})
