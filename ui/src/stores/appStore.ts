import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PaletteMode } from '@mui/material'

interface AppState {
  themeMode: PaletteMode
  consentGiven: boolean
  toggleTheme: () => void
  setConsent: (v: boolean) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      themeMode: (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') as PaletteMode,
      consentGiven: false,
      toggleTheme: () =>
        set((s) => ({ themeMode: s.themeMode === 'dark' ? 'light' : 'dark' })),
      setConsent: (v) => set({ consentGiven: v }),
    }),
    { name: 'serka-app' }
  )
)
