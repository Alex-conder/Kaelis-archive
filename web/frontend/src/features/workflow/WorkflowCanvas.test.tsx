import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import WorkflowToolbar from './components/WorkflowToolbar'
import NodePalette from './components/NodePalette'
import type { WorkflowNodeDefinition } from './types'

describe('WorkflowToolbar', () => {
  it('renders all buttons', () => {
    render(<WorkflowToolbar nodeCount={3} edgeCount={2} />)
    expect(screen.getByText('Run')).toBeInTheDocument()
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.getByText('Export')).toBeInTheDocument()
    expect(screen.getByText('Import')).toBeInTheDocument()
    expect(screen.getByText('Clear')).toBeInTheDocument()
  })

  it('shows node and edge counts', () => {
    render(<WorkflowToolbar nodeCount={5} edgeCount={3} />)
    expect(screen.getByText('5 nodes · 3 edges')).toBeInTheDocument()
  })

  it('calls onExport when export button clicked', () => {
    const onExport = vi.fn()
    render(<WorkflowToolbar onExport={onExport} />)
    fireEvent.click(screen.getByText('Export'))
    expect(onExport).toHaveBeenCalled()
  })
})

describe('NodePalette', () => {
  const mockNodes: WorkflowNodeDefinition[] = [
    {
      id: 'text_input',
      type: 'input',
      name: 'Text Input',
      description: 'Input text',
      icon: 'text',
      category: 'input',
    },
    {
      id: 'kg_extract',
      type: 'action',
      name: 'KG Extract',
      description: 'Extract knowledge',
      icon: 'brain',
      category: 'knowledge',
    },
  ]

  it('renders nodes grouped by category', () => {
    render(<NodePalette nodes={mockNodes} onDragStart={() => () => {}} />)
    expect(screen.getByText('Text Input')).toBeInTheDocument()
    expect(screen.getByText('KG Extract')).toBeInTheDocument()
  })

  it('calls onDragStart on drag', () => {
    const onDragStart = vi.fn(() => vi.fn())
    render(<NodePalette nodes={mockNodes} onDragStart={onDragStart} />)
    const nodeEl = screen.getByText('Text Input').closest('div')
    if (nodeEl) {
      fireEvent.dragStart(nodeEl)
      expect(onDragStart).toHaveBeenCalled()
    }
  })
})
