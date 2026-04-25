import { create } from 'zustand'
import { persist } from 'zustand/middleware'
// import type { AgentCapability } from './types'  // unused, kept for reference

interface CapabilityLayout {
  id: string
  x: number
  y: number
  w: number
  h: number
}

interface CapabilityStore {
  favorites: string[]
  layout: CapabilityLayout[]
  toggleFavorite: (id: string) => void
  updateLayout: (layout: CapabilityLayout[]) => void
  isFavorite: (id: string) => boolean
}

export const useCapabilityStore = create<CapabilityStore>()(
  persist(
    (set, get) => ({
      favorites: [],
      layout: [],
      toggleFavorite: (id: string) => {
        const current = get().favorites
        if (current.includes(id)) {
          set({ favorites: current.filter((f) => f !== id) })
        } else {
          set({ favorites: [...current, id] })
        }
      },
      updateLayout: (layout: CapabilityLayout[]) => set({ layout }),
      isFavorite: (id: string) => get().favorites.includes(id),
    }),
    {
      name: 'kaelis-capability-store',
    }
  )
)
