import { useState } from 'react'
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, TextField, Tooltip, Typography } from '@mui/material'
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined'
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined'
import ThumbUpIcon from '@mui/icons-material/ThumbUp'
import ThumbDownIcon from '@mui/icons-material/ThumbDown'
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined'
import { submitFeedback } from '../api/feedback'
import { useAppStore } from '../stores/appStore'

interface Props {
  context: Record<string, unknown>
  size?: 'small' | 'medium'
}

export default function FeedbackWidget({ context, size = 'small' }: Props) {
  const { consentGiven } = useAppStore()
  const [vote, setVote] = useState<'up' | 'down' | null>(null)
  const [commentOpen, setCommentOpen] = useState(false)
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)

  if (!consentGiven) return null

  const handleVote = async (v: 'up' | 'down') => {
    const newVote = vote === v ? null : v
    setVote(newVote)
    if (newVote) await submitFeedback({ ...context, vote: newVote }).catch(() => null)
  }

  const handleCommentSend = async () => {
    await submitFeedback({ ...context, vote, comment: text }).catch(() => null)
    setSent(true)
    setTimeout(() => { setCommentOpen(false); setSent(false); setText('') }, 1500)
  }

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Tooltip title="Helpful">
          <IconButton size={size} onClick={() => handleVote('up')} color={vote === 'up' ? 'primary' : 'default'}>
            {vote === 'up' ? <ThumbUpIcon fontSize={size} /> : <ThumbUpOutlinedIcon fontSize={size} />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Not helpful">
          <IconButton size={size} onClick={() => handleVote('down')} color={vote === 'down' ? 'error' : 'default'}>
            {vote === 'down' ? <ThumbDownIcon fontSize={size} /> : <ThumbDownOutlinedIcon fontSize={size} />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Add comment">
          <IconButton size={size} onClick={() => setCommentOpen(true)}>
            <CommentOutlinedIcon fontSize={size} />
          </IconButton>
        </Tooltip>
      </Box>

      <Dialog open={commentOpen} onClose={() => setCommentOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add comment</DialogTitle>
        <DialogContent>
          {sent ? (
            <Typography>Thanks for your feedback!</Typography>
          ) : (
            <TextField
              autoFocus
              fullWidth
              multiline
              rows={3}
              placeholder="Tell us more…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              variant="outlined"
              sx={{ mt: 1 }}
            />
          )}
        </DialogContent>
        {!sent && (
          <DialogActions>
            <Button onClick={() => setCommentOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleCommentSend} disabled={!text.trim()}>Send</Button>
          </DialogActions>
        )}
      </Dialog>
    </>
  )
}
