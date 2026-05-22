import { Box, Container, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import SearchBar from '../components/SearchBar'
import { brand } from '../theme'

export default function LandingPage() {
  const navigate = useNavigate()

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
          sx={{ height: 72, mb: 4, opacity: 0.9 }}
        />
        <Typography
          variant="h2"
          component="h1"
          sx={{ fontWeight: 600, mb: 0.5, letterSpacing: '-1px' }}
        >
          Serka
        </Typography>
        <Typography
          variant="h5"
          color="text.secondary"
          sx={{ fontWeight: 400, mb: 5 }}
        >
          AI-enhanced search tool
        </Typography>
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
          {['Water quality', 'Land use', 'Biodiversity', 'Climate', 'Soil carbon'].map((t) => (
            <Box
              key={t}
              component="button"
              onClick={() => navigate(`/search?q=${encodeURIComponent(t)}`)}
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
