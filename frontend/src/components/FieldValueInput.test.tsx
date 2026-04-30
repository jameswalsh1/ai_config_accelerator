// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FieldValueInput } from './FieldValueInput'

describe('FieldValueInput', () => {
  const onChange = vi.fn()
  const onSave = vi.fn()
  const onBlurValidation = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('text field', () => {
    it('renders a text input with value', () => {
      render(
        <FieldValueInput
          field={{ id: 'name', type: 'text', placeholder: 'Enter name' }}
          value="hello"
          onChange={onChange}
          onSave={onSave}
        />
      )
      const input = screen.getByPlaceholderText('Enter name') as HTMLInputElement
      expect(input.value).toBe('hello')
    })

    it('calls onChange on typing', () => {
      render(
        <FieldValueInput
          field={{ id: 'name', type: 'text' }}
          value=""
          onChange={onChange}
          onSave={onSave}
        />
      )
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'new' } })
      expect(onChange).toHaveBeenCalledWith('new')
    })

    it('calls onSave on blur', () => {
      render(
        <FieldValueInput
          field={{ id: 'name', type: 'text' }}
          value="val"
          onChange={onChange}
          onSave={onSave}
        />
      )
      fireEvent.blur(screen.getByRole('textbox'))
      expect(onSave).toHaveBeenCalledWith('val')
    })

    it('calls onBlurValidation on blur when provided', () => {
      render(
        <FieldValueInput
          field={{ id: 'name', type: 'text' }}
          value="val"
          onChange={onChange}
          onSave={onSave}
          onBlurValidation={onBlurValidation}
        />
      )
      fireEvent.blur(screen.getByRole('textbox'))
      expect(onBlurValidation).toHaveBeenCalledWith('name', 'val')
    })

    it('shows validation error when provided', () => {
      render(
        <FieldValueInput
          field={{ id: 'name', type: 'text' }}
          value=""
          onChange={onChange}
          onSave={onSave}
          validationError="Required field"
        />
      )
      expect(screen.getByText('Required field')).toBeInTheDocument()
    })
  })

  describe('number field', () => {
    it('renders a number input', () => {
      render(
        <FieldValueInput
          field={{ id: 'count', type: 'number', placeholder: 'Count' }}
          value={42}
          onChange={onChange}
          onSave={onSave}
        />
      )
      const input = screen.getByPlaceholderText('Count') as HTMLInputElement
      expect(input.type).toBe('number')
      expect(input.value).toBe('42')
    })

    it('converts string to number on change', () => {
      render(
        <FieldValueInput
          field={{ id: 'count', type: 'number' }}
          value={0}
          onChange={onChange}
          onSave={onSave}
        />
      )
      fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '10' } })
      expect(onChange).toHaveBeenCalledWith(10)
    })
  })

  describe('textarea field', () => {
    it('renders a textarea with correct attributes', () => {
      render(
        <FieldValueInput
          field={{ id: 'desc', type: 'textarea', placeholder: 'Description', rows: 6 }}
          value="some text"
          onChange={onChange}
          onSave={onSave}
        />
      )
      const ta = screen.getByPlaceholderText('Description') as HTMLTextAreaElement
      expect(ta.tagName).toBe('TEXTAREA')
      expect(ta.getAttribute('rows')).toBe('6')
    })

    it('defaults to 4 rows when not specified', () => {
      render(
        <FieldValueInput
          field={{ id: 'desc', type: 'textarea' }}
          value=""
          onChange={onChange}
          onSave={onSave}
        />
      )
      const ta = screen.getByRole('textbox') as HTMLTextAreaElement
      expect(ta.getAttribute('rows')).toBe('4')
    })
  })

  describe('select field', () => {
    const options = [
      { value: 'a', label: 'Alpha' },
      { value: 'b', label: 'Beta' },
    ]

    it('renders options', () => {
      render(
        <FieldValueInput
          field={{ id: 'choice', type: 'select', options }}
          value="a"
          onChange={onChange}
          onSave={onSave}
        />
      )
      expect(screen.getByText('Alpha')).toBeInTheDocument()
      expect(screen.getByText('Beta')).toBeInTheDocument()
      expect(screen.getByText('-- Select --')).toBeInTheDocument()
    })

    it('calls onChange and onSave on selection', () => {
      render(
        <FieldValueInput
          field={{ id: 'choice', type: 'select', options }}
          value=""
          onChange={onChange}
          onSave={onSave}
        />
      )
      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b' } })
      expect(onChange).toHaveBeenCalledWith('b')
      expect(onSave).toHaveBeenCalledWith('b')
    })
  })

  describe('multiselect field', () => {
    const options = [
      { value: 'x', label: 'X Option', description: 'X desc' },
      { value: 'y', label: 'Y Option' },
    ]

    it('renders checkboxes for each option', () => {
      render(
        <FieldValueInput
          field={{ id: 'tags', type: 'multi_select', options }}
          value={['x']}
          onChange={onChange}
          onSave={onSave}
        />
      )
      expect(screen.getByText('X Option')).toBeInTheDocument()
      expect(screen.getByText('Y Option')).toBeInTheDocument()
      expect(screen.getByText('X desc')).toBeInTheDocument()
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes[0]).toBeChecked()
      expect(checkboxes[1]).not.toBeChecked()
    })

    it('adds value on check', () => {
      render(
        <FieldValueInput
          field={{ id: 'tags', type: 'multi_select', options }}
          value={['x']}
          onChange={onChange}
          onSave={onSave}
        />
      )
      const checkboxes = screen.getAllByRole('checkbox')
      fireEvent.click(checkboxes[1])
      expect(onChange).toHaveBeenCalledWith(['x', 'y'])
      expect(onSave).toHaveBeenCalledWith(['x', 'y'])
    })

    it('removes value on uncheck', () => {
      render(
        <FieldValueInput
          field={{ id: 'tags', type: 'multi_select', options }}
          value={['x', 'y']}
          onChange={onChange}
          onSave={onSave}
        />
      )
      const checkboxes = screen.getAllByRole('checkbox')
      fireEvent.click(checkboxes[0])
      expect(onChange).toHaveBeenCalledWith(['y'])
    })
  })

  describe('checkbox/boolean field', () => {
    it('renders a checkbox', () => {
      render(
        <FieldValueInput
          field={{ id: 'enabled', type: 'boolean' }}
          value={true}
          onChange={onChange}
          onSave={onSave}
        />
      )
      expect(screen.getByRole('checkbox')).toBeChecked()
      expect(screen.getByText('Enabled')).toBeInTheDocument()
    })

    it('toggles on click', () => {
      render(
        <FieldValueInput
          field={{ id: 'enabled', type: 'checkbox' }}
          value={false}
          onChange={onChange}
          onSave={onSave}
        />
      )
      fireEvent.click(screen.getByRole('checkbox'))
      expect(onChange).toHaveBeenCalledWith(true)
      expect(onSave).toHaveBeenCalledWith(true)
    })
  })

  describe('unsupported field type', () => {
    it('renders fallback message', () => {
      render(
        <FieldValueInput
          field={{ id: 'mystery', type: 'color_picker' }}
          value=""
          onChange={onChange}
          onSave={onSave}
        />
      )
      expect(screen.getByText(/Unsupported field type: color_picker/)).toBeInTheDocument()
    })
  })
})
