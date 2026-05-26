import { useEffect, useRef, type KeyboardEvent } from 'react'
import {
  Box,
  CircularProgress,
  Container,
  Divider,
  IconButton,
  InputBase,
  Paper,
  Tooltip,
  Typography,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { useChatStore, type ChatMessage } from '../stores/chatStore'
import FeedbackWidget from '../components/FeedbackWidget'
import { streamChat } from '../api/chat'
import { useState } from 'react'

function MessageBubble({ msg, index }: { msg: ChatMessage; index: number }) {
  const isUser = msg.role === 'user'
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          px: 2,
          py: 1.5,
          maxWidth: '80%',
          bgcolor: isUser ? 'primary.main' : 'action.hover',
          color: isUser ? 'primary.contrastText' : 'text.primary',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        }}
      >
        {msg.thinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <CircularProgress size={10} color="inherit" sx={{ opacity: 0.6 }} />
            <Typography variant="caption" sx={{ opacity: 0.6 }}>
              Thinking…
            </Typography>
          </Box>
        )}
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
          {msg.content || (msg.thinking ? '' : '…')}
        </Typography>
      </Paper>
      {!isUser && msg.content && !msg.thinking && (
        <Box sx={{ mt: 0.5, ml: 1 }}>
          <FeedbackWidget context={{ type: 'chat_response', index }} />
        </Box>
      )}
    </Box>
  )
}

export default function ChatPage() {
  const { messages, loading, threadId, addMessage, appendToLast, setLoading, setLastThinking, clearMessages } =
    useChatStore()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    addMessage({ id: crypto.randomUUID(), role: 'user', content: text })
    addMessage({ id: crypto.randomUUID(), role: 'assistant', content: '', thinking: true })
    setLoading(true)

    const history = [...messages, { role: 'user' as const, content: text }]

    try {
      await streamChat(history, threadId, (event) => {
        if (event.type === 'THINKING_START') setLastThinking(true)
        if (event.type === 'THINKING_END') setLastThinking(false)
        if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) {
          setLastThinking(false)
          appendToLast(event.delta)
        }
        if (event.type === 'RUN_FINISHED') setLoading(false)
      })
    } catch {
      appendToLast('Sorry, something went wrong.')
      setLoading(false)
    }
  }

  const handleKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <Container maxWidth="md" sx={{ py: 4, height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Chat</Typography>
        <Tooltip title="Clear conversation">
          <span>
            <IconButton size="small" onClick={clearMessages} disabled={messages.length === 0}>
              <DeleteOutlineIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', pr: 1 }}>
        {messages.length === 0 && (
          <Box sx={{ textAlign: 'center', mt: 8 }}>
            <Typography color="text.secondary" variant="body2">
              Ask a question about EIDC environmental datasets
            </Typography>
          </Box>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={msg.id} msg={msg} index={i} />
        ))}
        <div ref={bottomRef} />
      </Box>

      <Divider sx={{ my: 2 }} />

      <Paper
        elevation={2}
        sx={{ display: 'flex', alignItems: 'flex-end', p: 1, gap: 1, borderRadius: 3 }}
      >
        <InputBase
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about datasets…"
          multiline
          maxRows={4}
          sx={{ flex: 1, px: 1 }}
          inputProps={{ 'aria-label': 'chat input' }}
        />
        <IconButton onClick={send} disabled={!input.trim() || loading} color="primary">
          {loading ? <CircularProgress size={20} /> : <SendIcon />}
        </IconButton>
      </Paper>
    </Container>
  )
}
