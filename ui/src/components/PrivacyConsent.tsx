import { useState } from 'react'
import { Box, Button, Paper, Typography, Link } from '@mui/material'
import { useAppStore } from '../stores/appStore'
import PrivacyPolicyDialog from './PrivacyPolicyDialog'

export default function PrivacyConsent() {
  const { consentGiven, setConsent } = useAppStore()
  const [policyOpen, setPolicyOpen] = useState(false)

  if (consentGiven) return null

  return (
    <>
      <Paper
        elevation={4}
        sx={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          p: 3,
          borderTop: '1px solid',
          borderColor: 'divider',
          zIndex: 1300,
        }}
      >
        <Box sx={{ maxWidth: 960, mx: 'auto', display: 'flex', gap: 3, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ flex: 1, minWidth: 240 }}>
            <strong>Feedback &amp; Privacy</strong> — We'd like to collect optional feedback on search
            results and AI responses to improve this service. Your feedback may be used in research
            and academic publications. No personal data is collected. See our{' '}
            <Link
              component="button"
              variant="body2"
              underline="always"
              onClick={() => setPolicyOpen(true)}
              sx={{ verticalAlign: 'baseline' }}
            >
              privacy notice
            </Link>
            .
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexShrink: 0 }}>
            <Button variant="outlined" size="small" onClick={() => setConsent(false)}>
              Decline
            </Button>
            <Button variant="contained" size="small" onClick={() => setConsent(true)}>
              Accept &amp; continue
            </Button>
          </Box>
        </Box>
      </Paper>
      <PrivacyPolicyDialog open={policyOpen} onClose={() => setPolicyOpen(false)} />
    </>
  )
}
