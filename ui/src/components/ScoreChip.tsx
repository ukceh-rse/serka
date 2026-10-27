import { Chip, Tooltip } from "@mui/material";

const CHIP_SX = { fontSize: "0.65rem", height: 20 };

/** A relevance score as a chip, styled to match TypeChip. */
export default function ScoreChip({ score }: { score: number }) {
  return (
    <Tooltip title="Relevance score">
      <Chip label={`Relevance: ${score.toFixed(2)}`} size="small" variant="outlined" sx={CHIP_SX} />
    </Tooltip>
  );
}
