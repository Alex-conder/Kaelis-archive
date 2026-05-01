import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SettingsState {
  e2eEncryption: boolean
  setE2EEncryption: (value: boolean) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      e2eEncryption: true,
      setE2EEncryption: (value) => set({ e2eEncryption: value }),
    }),
    {
      name: 'kaelis_settings',
    }
  )
)
