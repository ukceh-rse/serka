import { useState } from 'react'
import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Tooltip, Typography } from '@mui/material'
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

// Matches the small outlined chip language used for type/score/meta chips elsewhere in results.
const CHIP_SX = {
  fontSize: '0.65rem',
  height: 20,
  cursor: 'pointer',
  '& .MuiChip-icon': { fontSize: '0.8rem', mx: 0.4 },
  '& .MuiChip-label': { px: 0 },
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
          <Chip
            icon={vote === 'up' ? <ThumbUpIcon /> : <ThumbUpOutlinedIcon />}
            label=""
            size={size}
            variant="outlined"
            clickable
            onClick={() => handleVote('up')}
            sx={{ ...CHIP_SX, '& .MuiChip-icon': { ...CHIP_SX['& .MuiChip-icon'], color: vote === 'up' ? '#90A968' : 'text.secondary' } }}
          />
        </Tooltip>
        <Tooltip title="Not helpful">
          <Chip
            icon={vote === 'down' ? <ThumbDownIcon /> : <ThumbDownOutlinedIcon />}
            label=""
            size={size}
            variant="outlined"
            clickable
            onClick={() => handleVote('down')}
            sx={{ ...CHIP_SX, '& .MuiChip-icon': { ...CHIP_SX['& .MuiChip-icon'], color: vote === 'down' ? '#b07070' : 'text.secondary' } }}
          />
        </Tooltip>
        <Tooltip title="Add comment">
          <Chip
            icon={<CommentOutlinedIcon />}
            label=""
            size={size}
            variant="outlined"
            clickable
            onClick={() => setCommentOpen(true)}
            sx={{ ...CHIP_SX, '& .MuiChip-icon': { ...CHIP_SX['& .MuiChip-icon'], color: 'text.secondary' } }}
          />
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
