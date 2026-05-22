import { Box, Container, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import SearchBar from '../components/SearchBar'
import { brand } from '../theme'
import { useSearchStore } from '../stores/searchStore'

export default function LandingPage() {
  const navigate = useNavigate()
  const { aiSummaryEnabled, toggleAiSummary } = useSearchStore()

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
            ? 'linear-gradient(160deg, #0a0a0a 60%, #0d1a10 100%)'
            : 'linear-gradient(160deg, #f5f5f5 60%, #e8f0e4 100%)',
      }}
    >
      <Container maxWidth="md" sx={{ textAlign: 'center', py: 8 }}>
        <Box
          component="img"
          src="/ukceh-logo.png"
          alt="UKCEH"
          sx={{ height: 108, mb: 4, opacity: 0.9 }}
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
          onSearch={(q) => navigate(`/search?q=${encodeURIComponent(q)}`)}
        />
        <Box
          sx={{
            mt: 6,
            display: 'flex',
            justifyContent: 'center',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          {[
            'How are butterflies monitored in the UK?',
            'What are the LCM classes?',
            'What are the most popular datasets?',
          ].map((t) => (
            <Box
              key={t}
              component="button"
              onClick={() => {
                if (!aiSummaryEnabled) toggleAiSummary()
                navigate(`/search?q=${encodeURIComponent(t)}`)
              }}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 2,
                px: 2,
                py: 0.75,
                background: 'transparent',
                color: 'text.secondary',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontFamily: 'inherit',
                transition: 'border-color 0.15s, color 0.15s',
                '&:hover': { borderColor: brand.water, color: brand.water },
              }}
            >
              {t}
            </Box>
          ))}
        </Box>
      </Container>
    </Box>
  )
}
