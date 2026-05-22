import { useState, type FormEvent } from 'react'
import { CircularProgress, Divider, IconButton, InputBase, Paper, Tooltip } from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'

interface Props {
  onSearch: (query: string) => void
  loading?: boolean
  initialValue?: string
  size?: 'normal' | 'large'
  onAiSummary?: () => void
  aiSummaryActive?: boolean
  aiSummaryLoading?: boolean
}

export default function SearchBar({
  onSearch,
  loading,
  initialValue = '',
  size = 'normal',
  onAiSummary,
  aiSummaryActive,
  aiSummaryLoading,
}: Props) {
  const [value, setValue] = useState(initialValue)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim()) onSearch(value.trim())
  }

  return (
    <Paper
      component="form"
      onSubmit={handleSubmit}
      elevation={2}
      sx={{
        display: 'flex',
        alignItems: 'center',
        px: 2,
        py: size === 'large' ? 1.5 : 0.5,
        borderRadius: 2,
        width: '100%',
      }}
    >
      <InputBase
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search environmental datasets…"
        sx={{ flex: 1, fontSize: size === 'large' ? '1.1rem' : undefined }}
        inputProps={{ 'aria-label': 'search datasets' }}
        autoFocus={size === 'large'}
      />
      <IconButton type="submit" aria-label="search" disabled={loading || !value.trim()}>
        {loading ? <CircularProgress size={20} /> : <SearchIcon />}
      </IconButton>
      {onAiSummary && (
        <>
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5, my: 0.75 }} />
          <Tooltip title={aiSummaryActive ? 'Hide AI summary' : 'Generate AI summary'}>
            <span>
              <IconButton
                aria-label="AI summary"
                onClick={onAiSummary}
                disabled={aiSummaryLoading}
                color={aiSummaryActive ? 'primary' : 'default'}
                sx={{ opacity: aiSummaryActive ? 1 : 0.6 }}
              >
                {aiSummaryLoading ? <CircularProgress size={20} /> : <AutoAwesomeIcon />}
              </IconButton>
            </span>
          </Tooltip>
        </>
      )}
    </Paper>
  )
}
