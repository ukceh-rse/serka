import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Link,
  Tooltip,
  Typography,
} from "@mui/material";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import LockIcon from "@mui/icons-material/Lock";
import PublicIcon from "@mui/icons-material/Public";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import GavelIcon from "@mui/icons-material/Gavel";
import LinkIcon from "@mui/icons-material/Link";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import CloseIcon from "@mui/icons-material/Close";
import { useSearchStore } from "../stores/searchStore";
import type { SearchHit } from "../stores/searchStore";
import FeedbackWidget from "./FeedbackWidget";
import TypeChip from "./TypeChip";
import { curieToUrl } from "../ontology";
import { EXPANDED_MAX } from "../constants";

export interface GroupedResult {
  dataset: { uri: string; title: string; properties: Record<string, unknown> };
  hits: SearchHit[]; // sorted desc by score
}

interface Props {
  group: GroupedResult;
  index: number;
  collapsedLines: number;
}

const CHIP_SX = { fontSize: "0.65rem", height: 20 };
const ICON_CHIP_SX = {
  ...CHIP_SX,
  "& .MuiChip-icon": { fontSize: "0.8rem", color: "text.disabled", mx: 0.4 },
  "& .MuiChip-label": { px: 0 },
};
// Shared panel styling for the metadata table and match-result blocks.
const PANEL_SX = {
  bgcolor: "action.hover",
  border: 1,
  borderColor: "divider",
  borderRadius: 1,
  p: 1,
};

// Breadcrumb label for where in the graph a match originated.
const MATCH_LABEL: Record<string, { category: string; sublabel?: string }> = {
  metadata: { category: "Metadata", sublabel: "Title" },
  description: { category: "Metadata", sublabel: "Description" },
  lineage: { category: "Metadata", sublabel: "Lineage" },
  SUPPORTING_DOC: { category: "Supporting Documentation" },
  text: { category: "Text" },
};

const str = (v: unknown): string | null => (v == null ? null : String(v));

function formatDate(v: unknown): string | null {
  const s = str(v);
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toISOString().slice(0, 10);
}

function pickDoi(identifiers: unknown): string | null {
  if (!Array.isArray(identifiers)) return null;
  return identifiers.find((i) => typeof i === "string" && i.includes("doi.org")) ?? null;
}

type MetaItem = { icon: React.ReactElement; label: string; value: string; href?: string };

function metaItems(p: Record<string, unknown>): MetaItem[] {
  const published = formatDate(p.publication_date);
  const start = str(p.temporal_start);
  const end = str(p.temporal_end);
  const coverage = start && end ? `${start} to ${end}` : start ?? end;
  const citations = Number(p.citations);
  const access = str(p.access_rights);
  const licence = str(p.licence);
  const doi = pickDoi(p.identifiers);
  const bbox =
    p.north_boundary != null
      ? `N ${p.north_boundary}, S ${p.south_boundary}, E ${p.east_boundary}, W ${p.west_boundary}`
      : null;

  return [
    published && { icon: <CalendarMonthIcon />, label: "Published", value: published },
    coverage && { icon: <AccessTimeIcon />, label: "Temporal extent", value: coverage },
    citations > 0 && { icon: <FormatQuoteIcon />, label: "Citations", value: String(citations) },
    access && { icon: <LockIcon />, label: "Access rights", value: access },
    licence && { icon: <GavelIcon />, label: "Licence", value: licence, href: licence },
    doi && { icon: <LinkIcon />, label: "DOI", value: doi, href: doi },
    bbox && { icon: <PublicIcon />, label: "Spatial extent", value: bbox },
  ].filter(Boolean) as MetaItem[];
}

const metaLink = (value: string, href: string) => (
  <Link href={href} target="_blank" rel="noopener noreferrer" underline="always" color="primary">
    {value}
  </Link>
);

const trim = (s: string, max = 25): string => (s.length > max ? `${s.slice(0, max)}...` : s);

// Static chip: icon + value, tooltip "Label: value".
function MetaChip({ icon, label, value, href }: MetaItem) {
  const display = trim(value);
  return (
    <Tooltip title={`${label}: ${value}`}>
      <Chip
        icon={icon}
        label={
          <Box
            component="span"
            sx={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", px: 0.5 }}
          >
            {href ? metaLink(display, href) : display}
          </Box>
        }
        size="small"
        variant="outlined"
        sx={ICON_CHIP_SX}
      />
    </Tooltip>
  );
}

function MetaToggleChip({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <Tooltip title={open ? "hide metadata" : "show metadata"}>
      <Chip
        icon={open ? <CloseIcon /> : <MoreHorizIcon />}
        label=""
        onClick={onClick}
        size="small"
        variant="outlined"
        sx={{ ...ICON_CHIP_SX, cursor: "pointer", "& .MuiChip-label": { px: 0 } }}
      />
    </Tooltip>
  );
}

function MetaChips({ items }: { items: MetaItem[] }) {
  return (
    <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", alignItems: "center", justifyContent: "flex-end", flexShrink: 0 }}>
      {items.slice(0, 3).map((it) => <MetaChip key={it.label} {...it} />)}
    </Box>
  );
}

function MetaTable({ items, type }: { items: MetaItem[]; type: string }) {
  return (
    <Box
      sx={{
        ...PANEL_SX,
        display: "grid",
        gridTemplateColumns: "auto auto 1fr",
        alignItems: "center",
        columnGap: 1,
        rowGap: 0.5,
        fontSize: "0.72rem",
        color: "text.secondary",
        mb: 1,
      }}
    >
      <Box sx={{ display: "contents" }}>
        <Box sx={{ display: "flex", "& svg": { fontSize: "0.95rem", color: "text.disabled" } }}>
          <AccountTreeIcon />
        </Box>
        <Box sx={{ fontWeight: 600 }}>Type</Box>
        <Box sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          {curieToUrl(type) ? metaLink(type, curieToUrl(type)!) : type}
        </Box>
      </Box>
      {items.map((it) => (
        <Box key={it.label} sx={{ display: "contents" }}>
          <Box sx={{ display: "flex", "& svg": { fontSize: "0.95rem", color: "text.disabled" } }}>{it.icon}</Box>
          <Box sx={{ fontWeight: 600 }}>{it.label}</Box>
          <Box sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
            {it.href ? metaLink(it.value, it.href) : it.value}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

function MatchBlock({ hit, title }: { hit: SearchHit; title: string }) {
  const { category, sublabel } = MATCH_LABEL[hit.matched_on] ?? { category: hit.matched_on };
  const isSupportingDoc = hit.matched_on === "SUPPORTING_DOC" && hit.via.length > 0;
  return (
    <Box sx={{ ...PANEL_SX, mt: 1 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: hit.excerpt != null ? 0.5 : 0 }}>
        <Typography component="span" sx={{ fontSize: "0.68rem", fontWeight: 600, color: "text.secondary" }}>
          {category}
        </Typography>
        {(sublabel || isSupportingDoc) && (
          <ChevronRightIcon sx={{ fontSize: "0.85rem", color: "text.disabled" }} />
        )}
        {isSupportingDoc ? (
          <Link
            href={hit.via[0].id}
            target="_blank"
            rel="noopener noreferrer"
            underline="hover"
            sx={{ fontSize: "0.68rem", color: "text.secondary" }}
          >
            {hit.via[0].label ?? hit.via[0].id}
          </Link>
        ) : (
          sublabel && (
            <Typography component="span" sx={{ fontSize: "0.68rem", fontWeight: 600, color: "text.secondary" }}>
              {sublabel}
            </Typography>
          )
        )}
        <Chip label={`score ${hit.score.toFixed(2)}`} size="small" variant="outlined" sx={{ ...CHIP_SX, ml: "auto" }} />
      </Box>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ fontSize: "0.78rem", lineHeight: 1.5, textAlign: "left" }}
      >
        {hit.excerpt != null ? `… ${hit.excerpt} …` : title}
      </Typography>
    </Box>
  );
}

export default function DatasetResultCard({ group, index, collapsedLines }: Props) {
  const { query } = useSearchStore();
  const [expanded, setExpanded] = useState(false);
  const [metaOpen, setMetaOpen] = useState(false);
  const { dataset, hits } = group;
  const top = hits[0];
  const needsExpand = hits.length > 1 || (top.excerpt?.length ?? 0) > 120;
  const items = metaItems(dataset.properties);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 0.5, mb: 0.5 }}>
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
          {!metaOpen && items.length > 0 && <MetaChips items={items} />}
          {!metaOpen && <TypeChip type="dcat:Dataset" color="primary" />}
          {items.length > 3 && (
            <MetaToggleChip open={metaOpen} onClick={() => setMetaOpen((v) => !v)} />
          )}
        </Box>

        <Collapse in={metaOpen} unmountOnExit>
          <MetaTable items={items} type="dcat:Dataset" />
        </Collapse>

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
              maxHeight: expanded ? EXPANDED_MAX : `${collapsedLines * 1.5}rem`,
              overflow: "hidden",
              transition: "max-height 0.3s ease-in-out",
            }}
          >
            {hits.map((r, i) => (
              <MatchBlock key={i} hit={r} title={dataset.title} />
            ))}
          </Box>
        </Box>

        {needsExpand && (
          <Box sx={{ display: "flex", justifyContent: "center", mt: "4px" }}>
            <Button
              size="small"
              color="primary"
              onClick={() => setExpanded((v) => !v)}
              sx={{ fontSize: "0.7rem", textTransform: "none" }}
            >
              {expanded ? "Show less" : "Show more"}
            </Button>
          </Box>
        )}

        <Box sx={{ display: "flex", alignItems: "center", mt: 0.75 }}>
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
