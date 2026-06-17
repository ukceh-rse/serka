import { Box, Card, CardContent, Link, Typography } from "@mui/material";
import type { SearchHit } from "../stores/searchStore";
import TypeChip from "./TypeChip";

interface Props {
  hit: SearchHit;
}

const TYPE_COLOR: Record<string, "default" | "primary" | "secondary" | "success" | "info" | "warning" | "error"> = {
  "foaf:Person": "info",
  "foaf:Organization": "secondary",
  "skos:Concept": "success",
  "fabio:Expression": "warning",
};

const HIGHLIGHT_PROPS = ["orcid", "url", "notation", "scheme"];

export default function EntityResultCard({ hit }: Props) {
  const { entity } = hit;
  const typeUri = entity.type[0] ?? "";
  const chipColor = TYPE_COLOR[typeUri] ?? "default";

  const extras = HIGHLIGHT_PROPS.flatMap((k) => {
    const v = entity.properties[k];
    return v ? [`${k}: ${v}`] : [];
  });

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
          <Box sx={{ flex: 1 }}>
            <Typography
              component="h2"
              sx={{ fontSize: "0.875rem", fontWeight: 600, lineHeight: 1.4, mb: 0.5 }}
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
            {extras.length > 0 && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ fontSize: "0.75rem" }}
              >
                {extras.join(" · ")}
              </Typography>
            )}
          </Box>
          <TypeChip type={typeUri} color={chipColor} />
        </Box>
      </CardContent>
    </Card>
  );
}
