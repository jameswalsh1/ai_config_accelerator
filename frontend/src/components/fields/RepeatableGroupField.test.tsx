import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { WizardField } from '@/types/wizard'
import { RepeatableGroupField } from './RepeatableGroupField'

const field: WizardField = {
  id: 'rules',
  type: 'repeatable_group',
  label: 'Cursor Rules',
  description: 'Define one or more Cursor rule files.',
  required: true,
  fields: [
    {
      id: 'rule_file_name',
      type: 'text',
      label: 'Rule file name',
      description: 'Filename relative to .cursor/rules/',
      placeholder: 'security.mdc',
      required: true,
      render: false,
    },
    {
      id: 'rules_content',
      type: 'textarea',
      label: 'Rule Instructions',
      description: 'The guidance for this specific rule file.',
      placeholder: 'Add focused rules for this file...',
      rows: 5,
      required: true,
    },
  ],
}

function RenderWrapper() {
  const [value, setValue] = useState<Record<string, unknown>[]>([])

  return (
    <RepeatableGroupField field={field} value={value} onChange={setValue} />
  )
}

describe('RepeatableGroupField', () => {
  it('renders the empty state and allows adding a new rule entry', async () => {
    render(<RenderWrapper />)
    expect(screen.getByText('No entries yet. Click "Add Cursor Rule" to create the first cursor rule.')).toBeInTheDocument()

    const addButton = screen.getByRole('button', { name: /add cursor rule/i })
    await userEvent.click(addButton)

    expect(screen.getByText('Cursor Rule 1')).toBeInTheDocument()
    // Optional nested field (render:false) should show an include checkbox
    expect(screen.getByLabelText(/include this optional field/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Add focused rules for this file...')).toBeInTheDocument()
  })

  it('supports multiple entries and removal of an entry', async () => {
    render(<RenderWrapper />)

    const addButton = screen.getByRole('button', { name: /add cursor rule/i })
    await userEvent.click(addButton)
    await userEvent.click(addButton)

    expect(screen.getByText('Cursor Rule 1')).toBeInTheDocument()
    expect(screen.getByText('Cursor Rule 2')).toBeInTheDocument()

    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    expect(removeButtons).toHaveLength(2)

    await userEvent.click(removeButtons[0])
    expect(screen.getByText('Cursor Rule 1')).toBeInTheDocument()
    expect(screen.queryByText('Cursor Rule 2')).not.toBeInTheDocument()
  })

  it('updates nested textarea value when typing', async () => {
    render(<RenderWrapper />)

    const addButton = screen.getByRole('button', { name: /add cursor rule/i })
    await userEvent.click(addButton)

    const textarea = screen.getByPlaceholderText('Add focused rules for this file...')
    await userEvent.type(textarea, 'Protect sensitive APIs.')

    expect(textarea).toHaveValue('Protect sensitive APIs.')
  })
})
