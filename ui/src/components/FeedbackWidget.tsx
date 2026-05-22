import { useState } from 'react'
import { Box, IconButton, Tooltip, Typography, Collapse, TextField, Button } from '@mui/material'
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
  const [showText, setShowText] = useState(false)
  const [text, setText] = useState('')
  const [submitted, setSubmitted] = useState(false)

  if (!consentGiven) return null

  const handleVote = async (v: 'up' | 'down') => {
    const newVote = vote === v ? null : v
    setVote(newVote)
    if (newVote) {
      await submitFeedback({ ...context, vote: newVote }).catch(() => null)
      setShowText(true)
    }
  }

  const handleTextSubmit = async () => {
    await submitFeedback({ ...context, vote, comment: text }).catch(() => null)
    setSubmitted(true)
    setShowText(false)
  }

  return (
    <Box>
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
        {!submitted && (
          <Tooltip title="Add comment">
            <IconButton size={size} onClick={() => setShowText((v) => !v)} color={showText ? 'primary' : 'default'}>
              <CommentOutlinedIcon fontSize={size} />
            </IconButton>
          </Tooltip>
        )}
        {submitted && (
          <Typography variant="caption" color="text.secondary">
            Thanks!
          </Typography>
        )}
      </Box>
      <Collapse in={showText && !submitted}>
        <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
          <TextField
            size="small"
            placeholder="Optional comment…"
            multiline
            maxRows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            sx={{ flex: 1 }}
          />
          <Button size="small" variant="outlined" onClick={handleTextSubmit}>
            Send
          </Button>
          <Button size="small" onClick={() => setShowText(false)}>
            Skip
          </Button>
        </Box>
      </Collapse>
    </Box>
  )
}
