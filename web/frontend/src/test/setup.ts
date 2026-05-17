import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Auto cleanup after each test
afterEach(() => {
  cleanup()
})

// Suppress console errors during tests (optional, comment out for debugging)
// vi.spyOn(console, 'error').mockImplementation(() => {})
// vi.spyOn(console, 'warn').mockImplementation(() => {})
