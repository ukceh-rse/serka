import { useState } from "react";
import { Box, Button, Card, CardContent, Collapse, Link, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { useSearchStore } from "../stores/searchStore";
import type { SearchHit } from "../stores/searchStore";
import FeedbackWidget from "./FeedbackWidget";
import TypeChip from "./TypeChip";
import ScoreChip from "./ScoreChip";
import RelationshipPanel from "./RelationshipPanel";
import { TypeIcon, typeMeta } from "../typeMeta";

interface Props {
  hits: SearchHit[]; // all matches for one entity, sorted desc by score
  index?: number;
}

export default function EntityResultCard({ hits, index = 0 }: Props) {
  const { query } = useSearchStore();
  const [expanded, setExpanded] = useState(false);
  const { entity } = hits[0];
  const typeUri = entity.type[0] ?? "";
  const topScore = hits[0].score;

  return (
    <Card variant="outlined">
      <CardContent
        sx={{ p: 1.5, display: "flex", gap: 1.25, "&:last-child": { pb: 1.5 } }}
      >
        <TypeIcon type={typeUri} fontSize="1.75rem" />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
            <Box sx={{ flex: 1 }}>
              <Typography
                component="h2"
                sx={{ fontSize: "0.875rem", fontWeight: 600, lineHeight: 1.4 }}
              >
                <Link
                  href={entity.id}
                  target="_blank"
                  rel="noopener noreferrer"
                  underline="hover"
                  color="primary"
                >
                  {entity.label ?? entity.id}
                </Link>
              </Typography>
              <Typography
                variant="body2"
                noWrap
                sx={{ fontSize: "0.72rem", mb: 0.5 }}
              >
                <Link
                  href={entity.id}
                  target="_blank"
                  rel="noopener noreferrer"
                  underline="hover"
                  sx={{ color: "text.secondary" }}
                >
                  {entity.id}
                </Link>
              </Typography>
            </Box>
            <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexShrink: 0 }}>
              <ScoreChip score={topScore} />
              <TypeChip type={typeUri} color={typeMeta(typeUri).color} />
            </Box>
          </Box>

          <Collapse in={expanded} unmountOnExit>
            <Box>
              {hits.map((hit, i) => (
                <RelationshipPanel key={i} hit={hit} divider={i > 0} />
              ))}
            </Box>
          </Collapse>

          <Box sx={{ display: "flex", alignItems: "center", mt: 0.75 }}>
            <Button
              size="small"
              color="primary"
              onClick={() => setExpanded((v) => !v)}
              startIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              sx={{ fontSize: "0.7rem", textTransform: "none" }}
            >
              {expanded ? "Show less" : "Show more"}
            </Button>
            {expanded && (
              <Box sx={{ ml: "auto" }}>
                <FeedbackWidget
                  context={{ type: "result", index, entity_uri: entity.id, query }}
                />
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
