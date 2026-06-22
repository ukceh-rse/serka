import { useState } from 'react'
import { Box, Container, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import type { ReturnType } from '../stores/searchStore'
import NaturePeopleOutlinedIcon from '@mui/icons-material/NaturePeopleOutlined'
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined'
import LeaderboardOutlinedIcon from '@mui/icons-material/LeaderboardOutlined'
import SearchBar from '../components/SearchBar'
import { brand } from '../theme'
import { useAppStore } from '../stores/appStore'
import { EXAMPLE_SEARCHES } from '../constants'

// Data lime (#DBFE52) is a dark-background colour per brand guidelines.
// In dark mode it's used as the datasets icon; in light mode land green substitutes.
const SEARCH_CARDS = [
  { query: EXAMPLE_SEARCHES[0], Icon: NaturePeopleOutlinedIcon, color: brand.land },
  { query: EXAMPLE_SEARCHES[1], Icon: LayersOutlinedIcon, color: brand.water },
  { query: EXAMPLE_SEARCHES[2], Icon: LeaderboardOutlinedIcon, color: brand.land, darkColor: brand.data },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const { themeMode } = useAppStore()
  const [returnType, setReturnType] = useState<ReturnType | null>(null)
  const [aiActive, setAiActive] = useState(false)

  const go = (q: string, ai?: boolean) => {
    const sp = new URLSearchParams({ q })
    if (ai) sp.set('ai', 'true')
    if (returnType) sp.set('type', returnType)
    navigate(`/search?${sp}`)
  }

  return (
    <Box
      sx={{
        minHeight: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: (theme) =>
          theme.palette.mode === 'dark'
            ? 'linear-gradient(160deg, #141414 60%, #171f12 100%)'
            : 'linear-gradient(160deg, #f5f5f5 60%, #e8f0e4 100%)',
      }}
    >
      <Container maxWidth="md" sx={{ textAlign: 'center', py: 8 }}>
        <Box
          component="img"
          src={themeMode === 'dark' ? '/ukceh-logo_light.png' : '/ukceh-logo.png'}
          alt="UKCEH"
          sx={{ height: 162, mb: 4, opacity: 0.9 }}
        />
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: 1.5, mb: 5 }}>
          <Typography variant="h2" component="h1" sx={{ fontWeight: 700, letterSpacing: '-1px', fontSize: '2.625rem' }}>
            Serka
          </Typography>
          <Typography variant="h5" color="text.secondary" sx={{ fontWeight: 400, fontSize: '1.05rem' }}>
            AI-enhanced search tool
          </Typography>
        </Box>
        <SearchBar
          size="large"
          onSearch={(q) => go(q, aiActive)}
          onAiSummary={() => setAiActive((v) => !v)}
          aiSummaryActive={aiActive}
          returnType={returnType}
          onReturnTypeChange={setReturnType}
        />
        <Box sx={{ mt: 6, display: 'flex', gap: 2 }}>
          {SEARCH_CARDS.map(({ query, Icon, color, darkColor }) => (
            <Box
              key={query}
              component="button"
              onClick={() => go(query, true)}
              sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 1,
                border: '1px solid',
                borderColor: brand.air,
                borderRadius: 2,
                px: 2,
                py: 2,
                background: 'transparent',
                color: 'text.secondary',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontFamily: 'inherit',
                textAlign: 'center',
                whiteSpace: 'normal',
                transition: 'border-color 0.15s, color 0.15s',
                '&:hover': { borderColor: brand.water, color: 'text.primary' },
              }}
            >
              <Icon sx={{ fontSize: '1.5rem', color: (theme) => theme.palette.mode === 'dark' ? (darkColor ?? color) : color, opacity: 0.9 }} />
              {query}
            </Box>
          ))}
        </Box>
      </Container>
    </Box>
  )
}
