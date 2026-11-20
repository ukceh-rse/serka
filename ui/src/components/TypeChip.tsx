import { Chip } from "@mui/material";
import { typeMeta } from "../typeMeta";

/** Compact chip sizing shared by result-card chips. */
export const CHIP_SX = { fontSize: "0.65rem", height: 20 };

/** An OKF concept type as a chip, coloured to match its TypeIcon. */
export default function TypeChip({ type }: { type: string }) {
  const { name, color } = typeMeta(type);
  return <Chip label={name} size="small" variant="outlined" color={color} sx={CHIP_SX} />;
}
