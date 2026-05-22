import { createTheme, type PaletteMode } from '@mui/material'

const brand = {
  black: '#000000',
  white: '#FFFFFF',
  air: '#D6EAE6',
  water: '#477AE2',
  land: '#90A968',
  earth: '#D7B7AA',
  data: '#DBFE52',
}

export const createAppTheme = (mode: PaletteMode) =>
  createTheme({
    palette: {
      mode,
      primary: { main: brand.water },
      secondary: { main: brand.land },
      ...(mode === 'dark'
        ? {
            background: { default: '#0a0a0a', paper: '#111111' },
            text: { primary: brand.white, secondary: '#aaaaaa' },
          }
        : {
            background: { default: '#f5f5f5', paper: brand.white },
            text: { primary: brand.black, secondary: '#555555' },
          }),
    },
    typography: {
      fontFamily: '"DM Sans", system-ui, sans-serif',
      h1: { fontWeight: 500 },
      h2: { fontWeight: 500 },
      h3: { fontWeight: 600 },
      h4: { fontWeight: 600 },
      h5: { fontWeight: 600 },
      h6: { fontWeight: 600 },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: { textTransform: 'none', borderRadius: 2 },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 2 },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: { borderRadius: 4 },
        },
      },
    },
  })

export { brand }
