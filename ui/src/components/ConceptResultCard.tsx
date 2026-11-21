import { useState, type ComponentProps, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

/** The EIDC ID of the dataset a supporting document belongs to (datasets/<id>/docs/... -> <id>). */
export function documentDataset(conceptId: string): string | null {
  const match = /^datasets\/([^/]+)\/docs\//.exec(conceptId);
  return match ? match[1] : null;
}

interface Props {
  group: ConceptGroup;
  index?: number;
}

const passageHeading = ({ children }: { children?: ReactNode }) => (
  <Typography component="p" variant="body2" sx={{ fontSize: "0.8rem", fontWeight: 600, mt: 0.5 }}>
    {children}
  </Typography>
);

/** Passage markdown in the card's small type. Bundle-relative links have no page in the UI, so only their text is kept. */
const passageComponents: ComponentProps<typeof ReactMarkdown>["components"] = {
  h1: passageHeading,
  h2: passageHeading,
  h3: passageHeading,
  h4: passageHeading,
  h5: passageHeading,
  h6: passageHeading,
  p: ({ children }) => (
    <Typography variant="body2" sx={{ fontSize: "inherit", my: 0.5, "&:first-of-type": { mt: 0 }, "&:last-child": { mb: 0 } }}>
      {children}
    </Typography>
  ),
  ul: ({ children }) => <Box component="ul" sx={{ my: 0.5, pl: 2.5 }}>{children}</Box>,
  ol: ({ children }) => <Box component="ol" sx={{ my: 0.5, pl: 2.5 }}>{children}</Box>,
  a: ({ href, children }) =>
    href && /^https?:\/\//.test(href) ? (
      <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
        {children}
      </Link>
    ) : (
      <>{children}</>
    ),
};

function Passage({ text }: { text: string }) {
  return (
    <Box sx={{ fontSize: "0.8rem", lineHeight: 1.5, color: "text.secondary", overflowWrap: "anywhere" }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={passageComponents}>
        {text}
      </ReactMarkdown>
    </Box>
  );
}

/** One concept with its best-matching passage; its other passages are collapsed. */
export default function ConceptResultCard({ group, index = 0 }: Props) {
  const query = useSearchStore((s) => s.query);
  const [expanded, setExpanded] = useState(false);
  const { concept, hits } = group;
  const [best, ...more] = hits;
  const datasetId = concept.type === "document" ? documentDataset(concept.id) : null;
  // The search API doesn't return a document's dataset title; use it when the dataset is among the results.
  const datasetTitle = useSearchStore(
    (s) => s.results.find((h) => h.concept.id === `datasets/${datasetId}`)?.concept.title,
  );
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
              {datasetId && (
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.72rem" }}>
                  Supporting document of{" "}
                  <Link href={CATALOGUE + datasetId} target="_blank" rel="noopener noreferrer" underline="hover" color="text.secondary">
                    {datasetTitle ?? `dataset ${datasetId}`}
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
