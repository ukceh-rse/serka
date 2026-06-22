import { Fragment } from "react";
import { Box, Chip, Link, Typography } from "@mui/material";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import type { SearchHit } from "../stores/searchStore";
import { connectionLabel, curiePrefix, curieToUrl } from "../ontology";

const CHIP_SX = { fontSize: "0.65rem", height: 20 };
const PANEL_SX = {
  bgcolor: "action.hover",
  border: 1,
  borderColor: "divider",
  borderRadius: 1,
  p: 1,
  mt: 1,
};

// The relationship role (e.g. "Author"), prefixed with its ontology and linking to the term.
function RoleChip({ predicate }: { predicate: string }) {
  const url = curieToUrl(predicate);
  const prefix = curiePrefix(predicate);
  return (
    <Chip
      label={
        <Box component="span">
          {prefix && (
            <Box
              component="span"
              sx={{ opacity: 0.6, mr: 0.25 }}
            >{`${prefix}:`}</Box>
          )}
          {connectionLabel(predicate)}
        </Box>
      }
      size="small"
      variant="outlined"
      clickable={!!url}
      component={url ? Link : "div"}
      {...(url && { href: url, target: "_blank", rel: "noopener noreferrer" })}
      sx={{ ...CHIP_SX, fontWeight: 600, cursor: url ? "pointer" : "default" }}
    />
  );
}

// Shows why a result surfaced: the relationship chain from the entity to the matched
// content (e.g. "scoro:Author › Land Cover Map") plus the matching excerpt.
export default function RelationshipPanel({
  hit,
  fallbackTitle,
}: {
  hit: SearchHit;
  fallbackTitle?: string;
}) {
  const body = hit.excerpt != null ? `… ${hit.excerpt} …` : fallbackTitle;
  // Nothing to convey (a direct name/title match with no chain and no excerpt): render nothing.
  if (hit.path.length === 0 && !body) return null;
  const links = hit.path.flatMap((step) => [
    <RoleChip key={`${step.predicate}-role`} predicate={step.predicate} />,
    <Link
      key={`${step.entity.id}-entity`}
      href={step.entity.id}
      target="_blank"
      rel="noopener noreferrer"
      underline="hover"
      sx={{ fontSize: "0.72rem", color: "text.secondary" }}
    >
      {step.entity.label ?? step.entity.id}
    </Link>,
  ]);

  return (
    <Box sx={PANEL_SX}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 0.5,
          mb: body ? 0.5 : 0,
        }}
      >
        {links.map((el, i) => (
          <Fragment key={i}>
            {i > 0 && (
              <ChevronRightIcon
                sx={{ fontSize: "0.85rem", color: "text.disabled" }}
              />
            )}
            {el}
          </Fragment>
        ))}
        <Chip
          label={`score ${hit.score.toFixed(2)}`}
          size="small"
          variant="outlined"
          sx={{ ...CHIP_SX, ml: "auto" }}
        />
      </Box>
      {body && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ fontSize: "0.78rem", lineHeight: 1.5, textAlign: "left" }}
        >
          {body}
        </Typography>
      )}
    </Box>
  );
}
