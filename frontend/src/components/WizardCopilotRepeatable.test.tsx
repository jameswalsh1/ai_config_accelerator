import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { WizardConfig } from '@/types/wizard'
import { Wizard } from './Wizard'

const mockConfig: WizardConfig = {
  id: 'copilot',
  title: 'Copilot',
  description: 'Copilot test config',
  target: 'copilot',
  steps: [
    {
      id: 'path_instructions',
      title: 'Path Instructions',
      description: 'Provide file-specific instructions',
      output_file: '.copilot/instructions/',
      fields: [
        {
          id: 'path_instructions',
          type: 'repeatable_group',
          label: 'Path Instructions',
          description: 'One instruction per file path',
          required: true,
          fields: [
            {
              id: 'file_name',
              type: 'text',
              label: 'File name',
              placeholder: 'src/app/main.py',
              required: true,
            },
            {
              id: 'instruction_body',
              type: 'textarea',
              label: 'Instruction body',
              placeholder: 'When editing this file, do X and Y...',
              required: true,
              rows: 4,
            },
          ],
        },
      ],
    },
  ],
}

describe('Wizard copilot repeatable groups', () => {
  it('renders copilot path_instructions repeatable group and allows adding an entry', async () => {
    render(<Wizard config={mockConfig} onBack={() => {}} />)

    // Empty state should prompt adding the first Path Instruction
    expect(screen.getByText('No entries yet. Click "Add Path Instruction" to create the first path instruction.')).toBeInTheDocument()

    const add = screen.getByRole('button', { name: /add path instruction/i })
    await userEvent.click(add)

    expect(screen.getByText('Path Instruction 1')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('When editing this file, do X and Y...')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('src/app/main.py')).toBeInTheDocument()
  })
})
