import { AppBar, Box, Button, IconButton, Toolbar, Tooltip, Typography } from '@mui/material'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import SearchIcon from '@mui/icons-material/Search'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'
import PrivacyConsent from './PrivacyConsent'
import GeneralFeedback from './GeneralFeedback'

interface Props {
  children: React.ReactNode
}

const navLinkSx = (isActive: boolean) => ({
  fontSize: '0.875rem',
  textTransform: 'none' as const,
  color: isActive ? 'primary.main' : 'text.secondary',
  fontWeight: isActive ? 600 : 400,
  '&:hover': { color: 'text.primary', bgcolor: 'transparent' },
})

export default function Layout({ children }: Props) {
  const { themeMode, toggleTheme } = useAppStore()
  const { pathname } = useLocation()

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 1 }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none', gap: 12 }}>
            <img src={themeMode === 'dark' ? '/ukceh-logo_light.png' : '/ukceh-logo.png'} alt="UKCEH" height={32} />
            <Typography variant="body1" sx={{ color: 'text.primary' }}>
              <strong>Serka</strong>{' '}
              <Typography component="span" variant="body1" sx={{ color: 'text.secondary' }}>
                AI-enhanced search tool
              </Typography>
            </Typography>
          </Link>

          {/* Page navigation — hidden on landing page */}
          <Box sx={{ display: pathname === '/' ? 'none' : 'flex', alignItems: 'center', ml: 3, gap: 0.5 }}>
            <NavLink to="/search" style={{ textDecoration: 'none' }}>
              {({ isActive }) => (
                <Button startIcon={<SearchIcon sx={{ fontSize: '1rem !important' }} />} sx={navLinkSx(isActive)}>
                  Search
                </Button>
              )}
            </NavLink>
            <Tooltip title="Coming soon">
              <span>
                <Button
                  startIcon={<AutoAwesomeIcon sx={{ fontSize: '1rem !important' }} />}
                  disabled
                  sx={{ fontSize: '0.875rem', textTransform: 'none' }}
                >
                  Chat
                </Button>
              </span>
            </Tooltip>
          </Box>

          <Box sx={{ flex: 1 }} />
          <GeneralFeedback />
          <Tooltip title={themeMode === 'dark' ? 'Light mode' : 'Dark mode'}>
            <IconButton onClick={toggleTheme} color="inherit">
              {themeMode === 'dark' ? <LightModeOutlinedIcon /> : <DarkModeOutlinedIcon />}
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flex: 1 }}>
        {children}
      </Box>
      <PrivacyConsent />
    </Box>
  )
}
