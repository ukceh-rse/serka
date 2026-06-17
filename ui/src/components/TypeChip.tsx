import { Chip, Link, Tooltip } from "@mui/material";
import type { ComponentProps } from "react";
import { curieToUrl } from "../ontology";

type ChipColor = ComponentProps<typeof Chip>["color"];

const CHIP_SX = { fontSize: "0.65rem", height: 20 };

/** A DOO type as a chip; links to the defining ontology term when resolvable. */
export default function TypeChip({ type, color = "default" }: { type: string; color?: ChipColor }) {
  const url = curieToUrl(type);
  const chip = (
    <Chip
      label={type}
      size="small"
      variant="outlined"
      color={color}
      clickable={!!url}
      component={url ? Link : "div"}
      {...(url && { href: url, target: "_blank", rel: "noopener noreferrer" })}
      sx={{ ...CHIP_SX, cursor: url ? "pointer" : "default" }}
    />
  );
  return url ? <Tooltip title={`${type} — view in ontology`}>{chip}</Tooltip> : chip;
}
