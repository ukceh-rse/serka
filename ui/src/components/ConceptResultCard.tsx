import { useState } from "react";
import { Box, Button, Card, CardContent, Collapse, Link, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { useSearchStore } from "../stores/searchStore";
import type { ConceptGroup } from "../stores/searchStore";
import FeedbackWidget from "./FeedbackWidget";
import TypeChip from "./TypeChip";
import ScoreChip from "./ScoreChip";
import { TypeIcon } from "../typeMeta";

const CATALOGUE = "https://catalogue.ceh.ac.uk/id/";

/** A passage as plain text: markdown links keep only their text, headings and list markers go. */
export function plainText(markdown: string): string {
  return markdown
    .replace(/\[((?:\\.|[^\]\\])*)\]\([^)]*\)/g, "$1")
    .replace(/\\([[\]\\])/g, "$1")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** The catalogue page of the dataset a supporting document belongs to (datasets/<id>/docs/... -> <id>). */
export function documentDataset(conceptId: string): string | null {
  const match = /^datasets\/([^/]+)\/docs\//.exec(conceptId);
  return match ? CATALOGUE + match[1] : null;
}

interface Props {
  group: ConceptGroup;
  index?: number;
}

function Passage({ text }: { text: string }) {
  return (
    <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem", lineHeight: 1.5 }}>
      {plainText(text)}
    </Typography>
  );
}

/** One concept with its best-matching passage; its other passages are collapsed. */
export default function ConceptResultCard({ group, index = 0 }: Props) {
  const query = useSearchStore((s) => s.query);
  const [expanded, setExpanded] = useState(false);
  const { concept, hits } = group;
  const [best, ...more] = hits;
  const datasetUrl = concept.type === "document" ? documentDataset(concept.id) : null;
  const facts = [
    concept.published && `Published ${concept.published}`,
    concept.citations ? `${concept.citations} citation${concept.citations === 1 ? "" : "s"}` : null,
  ].filter(Boolean);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, display: "flex", gap: 1.25, "&:last-child": { pb: 1.5 } }}>
        <TypeIcon type={concept.type} fontSize="1.75rem" />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
            <Box sx={{ flex: 1 }}>
              <Typography component="h2" sx={{ fontSize: "0.875rem", fontWeight: 600, lineHeight: 1.4 }}>
                {concept.resource ? (
                  <Link href={concept.resource} target="_blank" rel="noopener noreferrer" underline="hover">
                    {concept.title}
                  </Link>
                ) : (
                  concept.title
                )}
              </Typography>
              {datasetUrl && (
                <Typography variant="body2" sx={{ fontSize: "0.72rem" }}>
                  <Link href={datasetUrl} target="_blank" rel="noopener noreferrer" underline="hover" color="text.secondary">
                    Supporting document of this dataset
                  </Link>
                </Typography>
              )}
              {facts.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  {facts.join(" · ")}
                </Typography>
              )}
            </Box>
            <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexShrink: 0 }}>
              <ScoreChip score={best.score} />
              <TypeChip type={concept.type} />
            </Box>
          </Box>

          {concept.description && (
            <Typography variant="body2" sx={{ fontSize: "0.8rem", mt: 0.5 }}>
              {concept.description}
            </Typography>
          )}
          <Box sx={{ mt: 0.75, pl: 1, borderLeft: 2, borderColor: "divider" }}>
            <Passage text={best.text} />
            <Collapse in={expanded} unmountOnExit>
              {more.map((hit) => (
                <Box key={hit.chunk_id} sx={{ mt: 0.75 }} data-testid="more-passage">
                  <Passage text={hit.text} />
                </Box>
              ))}
            </Collapse>
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", mt: 0.75 }}>
            {more.length > 0 && (
              <Button
                size="small"
                color="primary"
                onClick={() => setExpanded((v) => !v)}
                startIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                sx={{ fontSize: "0.7rem", textTransform: "none" }}
              >
                {expanded
                  ? "Show fewer passages"
                  : `${more.length} more passage${more.length === 1 ? "" : "s"}`}
              </Button>
            )}
            <Box sx={{ ml: "auto" }}>
              <FeedbackWidget
                context={{ type: "result", index, concept_id: concept.id, entity_uri: concept.resource ?? concept.id, query }}
              />
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
