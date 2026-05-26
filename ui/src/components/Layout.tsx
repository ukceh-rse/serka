import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import { Link } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'
import PrivacyConsent from './PrivacyConsent'
import GeneralFeedback from './GeneralFeedback'

interface Props {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  const { themeMode, toggleTheme } = useAppStore()

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
