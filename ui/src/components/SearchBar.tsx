import { useState, type FormEvent } from 'react'
import { CircularProgress, IconButton, InputBase, Paper } from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'

interface Props {
  onSearch: (query: string) => void
  loading?: boolean
  initialValue?: string
  size?: 'normal' | 'large'
}

export default function SearchBar({ onSearch, loading, initialValue = '', size = 'normal' }: Props) {
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
    </Paper>
  )
}
