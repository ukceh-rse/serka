import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Typography,
} from '@mui/material'
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined'
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined'
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined'

interface Props {
  open: boolean
  onClose: () => void
}

export default function PrivacyPolicyDialog({ open, onClose }: Props) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth scroll="paper">
      <DialogTitle>Privacy Notice</DialogTitle>
      <DialogContent dividers>
        <Typography variant="h6" gutterBottom>
          About this tool
        </Typography>
        <Typography variant="body2" paragraph>
          Serka is an AI-enhanced search tool for the EIDC catalogue and other UKCEH data sources.
          It identifies the most relevant datasets using semantic search and generates answers via
          Retrieval Augmented Generation (RAG) with a Large Language Model (LLM).
        </Typography>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          Feedback
        </Typography>
        <Typography variant="body2" paragraph>
          Serka is a prototype, and your feedback helps us improve it. You can rate search results
          and AI responses using the <ThumbUpOutlinedIcon sx={{ fontSize: 14, verticalAlign: 'middle' }} />{' '}
          /{' '}
          <ThumbDownOutlinedIcon sx={{ fontSize: 14, verticalAlign: 'middle' }} /> buttons, or leave
          more detailed comments via the{' '}
          <CommentOutlinedIcon sx={{ fontSize: 14, verticalAlign: 'middle' }} /> icon. Feedback is
          optional and only available after accepting this notice.
        </Typography>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          What we collect
        </Typography>
        <Typography variant="body2" paragraph>
          If you choose to provide feedback, your search queries and feedback are stored in a
          database. No personal data is collected — we do not record your name, email address, or IP
          address. Your use of this tool is entirely anonymous.
        </Typography>
        <Typography variant="body2" paragraph>
          Once submitted, feedback cannot be withdrawn.
        </Typography>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          How we use it
        </Typography>
        <Typography variant="body2" paragraph>
          Collected queries and feedback are used to evaluate and guide future development of the
          search tool. The data may also be referenced in academic publications about the tool.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} variant="contained">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  )
}
