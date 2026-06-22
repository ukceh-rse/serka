import { Box, Card, CardContent, Link, Typography } from "@mui/material";
import type { SearchHit } from "../stores/searchStore";
import TypeChip from "./TypeChip";
import RelationshipPanel from "./RelationshipPanel";
import { TypeIcon, typeMeta } from "../typeMeta";

interface Props {
  hits: SearchHit[]; // all matches for one entity, sorted desc by score
}

const HIGHLIGHT_PROPS = ["orcid", "url", "notation", "scheme"];

export default function EntityResultCard({ hits }: Props) {
  const { entity } = hits[0];
  const typeUri = entity.type[0] ?? "";

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
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.75,
                fontSize: "0.875rem",
                fontWeight: 600,
                lineHeight: 1.4,
                mb: extras.length > 0 ? 0.5 : 0,
              }}
            >
              <TypeIcon type={typeUri} />
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
          <TypeChip type={typeUri} color={typeMeta(typeUri).color} />
        </Box>
        {hits.map((hit, i) => (
          <RelationshipPanel key={i} hit={hit} />
        ))}
      </CardContent>
    </Card>
  );
}
