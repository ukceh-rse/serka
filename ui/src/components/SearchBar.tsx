import { useState, useRef, useEffect, type FormEvent } from 'react'
import {
  Box, ButtonBase, Divider, IconButton, InputBase, Paper, Tooltip, Typography,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import HistoryIcon from '@mui/icons-material/History'
import { EXAMPLE_SEARCHES } from '../constants'
import { useSearchStore } from '../stores/searchStore'

interface Props {
  onSearch: (query: string) => void
  loading?: boolean
  initialValue?: string
  size?: 'normal' | 'large'
  onAiSummary?: () => void
  aiSummaryActive?: boolean
  showSuggestions?: boolean
  onFocusChange?: (focused: boolean) => void
  onExampleSearch?: (q: string) => void
}

const isMac = navigator.platform.toUpperCase().includes('MAC') || navigator.userAgent.includes('Mac')

export default function SearchBar({
  onSearch,
  initialValue = '',
  size = 'normal',
  onAiSummary,
  aiSummaryActive,
  showSuggestions,
  onFocusChange,
  onExampleSearch,
}: Props) {
  const [value, setValue] = useState(initialValue)
  const [focused, setFocused] = useState(false)
  const [aiButtonClicked, setAiButtonClicked] = useState(aiSummaryActive ?? false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { recentSearches } = useSearchStore()

  const showDropdown = focused && showSuggestions

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleFocus = () => {
    setFocused(true)
    onFocusChange?.(true)
  }

  const handleBlur = () => {
    setFocused(false)
    onFocusChange?.(false)
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim()) onSearch(value.trim())
  }

  const handleSuggestion = (q: string) => {
    setValue(q)
    onSearch(q)
  }

  return (
    <Box sx={{ position: 'relative', width: '100%' }}>
      <Paper
        component="form"
        onSubmit={handleSubmit}
        elevation={focused ? 4 : 2}
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: 2,
          py: size === 'large' ? 1.5 : 0.5,
          borderRadius: showDropdown ? '8px 8px 0 0' : 2,
          width: '100%',
          transition: 'box-shadow 0.2s',
        }}
      >
        <InputBase
          inputRef={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={(e) => { if (e.key === 'Escape') inputRef.current?.blur() }}
          placeholder="Search environmental datasets…"
          sx={{ flex: 1, fontSize: size === 'large' ? '1.1rem' : undefined }}
          inputProps={{ 'aria-label': 'search datasets' }}
          autoFocus={size === 'large'}
        />
        {showSuggestions && !focused && (
          <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.7rem', mr: 0.5, userSelect: 'none', whiteSpace: 'nowrap' }}>
            {isMac ? '⌘K' : 'Ctrl+K'}
          </Typography>
        )}
        <IconButton type="submit" aria-label="search" disabled={!value.trim()}>
          <SearchIcon />
        </IconButton>
        {onAiSummary && (
          <>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.5, my: 0.75 }} />
            <Tooltip title={aiSummaryActive ? 'Disable AI summary' : 'Enable AI summary'}>
              <span>
                <IconButton
                  aria-label="AI summary"
                  onClick={() => { setAiButtonClicked(true); onAiSummary() }}
                  color={aiSummaryActive ? 'primary' : 'default'}
                  sx={(theme) => ({
                    opacity: aiSummaryActive ? 1 : 0.6,
                    ...(!aiSummaryActive && !aiButtonClicked && {
                      '@keyframes subtlePulse': {
                        '0%, 100%': { opacity: 0.4, color: theme.palette.text.secondary },
                        '50%': { opacity: 1, color: theme.palette.primary.main },
                      },
                      animation: 'subtlePulse 2s ease-in-out 4',
                    }),
                  })}
                >
                  <AutoAwesomeIcon />
                </IconButton>
              </span>
            </Tooltip>
          </>
        )}
      </Paper>

      {showDropdown && (
        <Paper
          elevation={4}
          sx={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10, borderRadius: '0 0 8px 8px', overflow: 'hidden' }}
        >
          {recentSearches.length > 0 && (
            <>
              <Typography variant="caption" sx={{ px: 2, pt: 1.5, pb: 0.5, display: 'block', color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', fontSize: '0.65rem' }}>
                Recent searches
              </Typography>
              {recentSearches.map((q) => (
                <ButtonBase
                  key={q}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSuggestion(q)}
                  sx={{ width: '100%', px: 2, py: 0.75, display: 'flex', alignItems: 'center', gap: 1.5, justifyContent: 'flex-start', '&:hover': { bgcolor: 'action.hover' } }}
                >
                  <HistoryIcon sx={{ fontSize: '0.95rem', color: 'text.disabled', flexShrink: 0 }} />
                  <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>{q}</Typography>
                </ButtonBase>
              ))}
              <Divider />
            </>
          )}
          <Typography variant="caption" sx={{ px: 2, pt: 1.5, pb: 0.5, display: 'block', color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', fontSize: '0.65rem' }}>
            Try asking
          </Typography>
          {EXAMPLE_SEARCHES.map((q) => (
            <ButtonBase
              key={q}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onExampleSearch ? onExampleSearch(q) : handleSuggestion(q)}
              sx={{ width: '100%', px: 2, py: 0.75, display: 'flex', alignItems: 'center', gap: 1.5, justifyContent: 'flex-start', '&:hover': { bgcolor: 'action.hover' } }}
            >
              <AutoAwesomeIcon sx={{ fontSize: '0.95rem', color: 'primary.main', opacity: 0.7, flexShrink: 0 }} />
              <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>{q}</Typography>
            </ButtonBase>
          ))}
          <Box sx={{ pb: 0.75 }} />
        </Paper>
      )}
    </Box>
  )
}
