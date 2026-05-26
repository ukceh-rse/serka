import { useState } from 'react'
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material'
import FeedbackOutlinedIcon from '@mui/icons-material/FeedbackOutlined'
import { submitFeedback } from '../api/feedback'
import { useAppStore } from '../stores/appStore'

export default function GeneralFeedback() {
  const { consentGiven } = useAppStore()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)

  if (!consentGiven) return null

  const handleSend = async () => {
    await submitFeedback({ type: 'general', comment: text }).catch(() => null)
    setSent(true)
    setTimeout(() => { setOpen(false); setSent(false); setText('') }, 1500)
  }

  return (
    <>
      <Button
        size="small"
        startIcon={<FeedbackOutlinedIcon />}
        onClick={() => setOpen(true)}
        color="inherit"
        sx={{ opacity: 0.7 }}
      >
        Feedback
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Share feedback</DialogTitle>
        <DialogContent>
          {sent ? (
            <Typography>Thanks for your feedback!</Typography>
          ) : (
            <TextField
              autoFocus
              fullWidth
              multiline
              rows={4}
              placeholder="Tell us what you think…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              variant="outlined"
              sx={{ mt: 1 }}
            />
          )}
        </DialogContent>
        {!sent && (
          <DialogActions>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleSend} disabled={!text.trim()}>
              Send
            </Button>
          </DialogActions>
        )}
      </Dialog>
    </>
  )
}
