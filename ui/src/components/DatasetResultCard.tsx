import { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  IconButton,
  Link,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { useSearchStore } from "../stores/searchStore";
import type { SearchHit } from "../stores/searchStore";
import FeedbackWidget from "./FeedbackWidget";
import { EXPANDED_MAX } from "../constants";

export interface GroupedResult {
  dataset: { uri: string; title: string };
  hits: SearchHit[]; // sorted desc by score
}

interface Props {
  group: GroupedResult;
  index: number;
  collapsedLines: number;
}

const TRUNCATE_THRESHOLD = 120;
const CHIP_SX = { fontSize: "0.65rem", height: 18, opacity: 0.6 };

// "description" -> "dcterms:description", "lineage" -> "dcterms:provenance", etc.
const FIELD_TO_DOO: Record<string, string> = {
  description: "dcterms:description",
  lineage: "dcterms:provenance",
  SUPPORTING_DOC: "dcterms:hasPart",
};

function matchedOnLabel(matched_on: string): string {
  return FIELD_TO_DOO[matched_on] ?? matched_on;
}

export default function DatasetResultCard({ group, index, collapsedLines }: Props) {
  const { query } = useSearchStore();
  const [expanded, setExpanded] = useState(false);
  const { dataset, hits } = group;
  const top = hits[0];
  const needsExpand =
    hits.length > 1 || (top.excerpt?.length ?? 0) > TRUNCATE_THRESHOLD;

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 0.5, mb: 1 }}>
          <Typography
            component="h2"
            sx={{ fontSize: "0.875rem", fontWeight: 600, flex: 1, lineHeight: 1.4 }}
          >
            <Link
              href={dataset.uri}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
              color="primary"
            >
              {dataset.title || dataset.uri}
            </Link>
          </Typography>
          {hits.length > 1 && (
            <Chip
              label={hits.length}
              size="small"
              variant="outlined"
              sx={{ flexShrink: 0, opacity: 0.6, fontSize: "0.7rem", height: 18, alignSelf: "center" }}
            />
          )}
          {needsExpand && (
            <IconButton
              size="small"
              onClick={() => setExpanded((v) => !v)}
              sx={{ p: 0.25, flexShrink: 0 }}
            >
              {expanded ? (
                <ExpandLessIcon sx={{ fontSize: "1rem" }} />
              ) : (
                <ExpandMoreIcon sx={{ fontSize: "1rem" }} />
              )}
            </IconButton>
          )}
        </Box>

        <Box
          sx={(theme) => ({
            position: "relative",
            ...(!expanded &&
              needsExpand && {
                "&::after": {
                  content: '""',
                  position: "absolute",
                  bottom: 0,
                  left: 0,
                  right: 0,
                  height: "1.5rem",
                  background: `linear-gradient(transparent, ${theme.palette.background.paper})`,
                  pointerEvents: "none",
                },
              }),
          })}
        >
          <Box
            sx={{
              maxHeight: expanded ? EXPANDED_MAX : `${collapsedLines * 1.17}rem`,
              overflow: "hidden",
              transition: "max-height 0.3s ease-in-out",
            }}
          >
            {hits.map((r, i) => (
              <Box key={i}>
                {i > 0 && <Divider sx={{ my: 1 }} />}
                {r.excerpt != null ? (
                  <>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ fontSize: "0.78rem", lineHeight: 1.5, mb: 0.5, textAlign: "left" }}
                    >
                      {`… ${r.excerpt} …`}
                    </Typography>
                    <Chip
                      label={matchedOnLabel(r.matched_on)}
                      size="small"
                      variant="outlined"
                      sx={CHIP_SX}
                    />
                  </>
                ) : (
                  <Chip label="dcat:Dataset" size="small" variant="outlined" sx={CHIP_SX} />
                )}
              </Box>
            ))}
          </Box>
        </Box>

        <Divider sx={{ mt: 1, mb: 0.75 }} />
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <Box sx={{ ml: "auto" }}>
            <FeedbackWidget
              context={{ type: "result", index, dataset_uri: dataset.uri, query }}
            />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
