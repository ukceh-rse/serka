import { AppBar, Box, IconButton, Toolbar, Tooltip } from '@mui/material'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline'
import SearchIcon from '@mui/icons-material/Search'
import { Link, useLocation } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'
import PrivacyConsent from './PrivacyConsent'
import GeneralFeedback from './GeneralFeedback'

interface Props {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  const { themeMode, toggleTheme } = useAppStore()
  const location = useLocation()

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 1 }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none' }}>
            <img src="/ukceh-logo.png" alt="UKCEH" height={32} />
          </Link>
          <Box sx={{ flex: 1 }} />
          <GeneralFeedback />
          {location.pathname !== '/search' && (
            <Tooltip title="Search">
              <IconButton component={Link} to="/search" color="inherit">
                <SearchIcon />
              </IconButton>
            </Tooltip>
          )}
          {location.pathname !== '/chat' && (
            <Tooltip title="Chat">
              <IconButton component={Link} to="/chat" color="inherit">
                <ChatBubbleOutlineIcon />
              </IconButton>
            </Tooltip>
          )}
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
