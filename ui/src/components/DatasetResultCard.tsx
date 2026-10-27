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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { useSearchStore } from "../stores/searchStore";
import type { SearchHit } from "../stores/searchStore";
import FeedbackWidget from "./FeedbackWidget";
import TypeChip from "./TypeChip";
import ScoreChip from "./ScoreChip";
import RelationshipPanel from "./RelationshipPanel";
import { TypeIcon } from "../typeMeta";
import { curieToUrl } from "../ontology";

export interface GroupedResult {
  dataset: { uri: string; title: string; properties: Record<string, unknown> };
  hits: SearchHit[]; // sorted desc by score
}

interface Props {
  group: GroupedResult;
  index: number;
}

const CHIP_SX = { fontSize: "0.65rem", height: 20 };
const ICON_CHIP_SX = {
  ...CHIP_SX,
  "& .MuiChip-icon": { fontSize: "0.8rem", color: "text.disabled", mx: 0.4 },
  "& .MuiChip-label": { px: 0 },
};
// Plain (no background/border box, no divider — this is always the first/only content block).
const PANEL_SX = {
  mt: 0.5,
  mb: 1,
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
  return (
    identifiers.find((i) => typeof i === "string" && i.includes("doi.org")) ??
    null
  );
}

type MetaItem = {
  icon: React.ReactElement;
  label: string;
  value: string;
  href?: string;
};

// "POLYGON((W S, E S, E N, W N, W S))" (dcat:bbox WKT) -> "N .., S .., E .., W .."
function wktBbox(wkt: unknown): string | null {
  const nums = typeof wkt === "string" ? wkt.match(/-?\d+(\.\d+)?/g)?.map(Number) : undefined;
  if (!nums || nums.length < 6) return null;
  const [w, s, e, , , n] = nums;
  return `N ${n}, S ${s}, E ${e}, W ${w}`;
}

function metaItems(p: Record<string, unknown>): MetaItem[] {
  const published = formatDate(p.publication_date);
  const temporal = (p.temporal ?? {}) as { start_date?: unknown; end_date?: unknown };
  const start = str(temporal.start_date);
  const end = str(temporal.end_date);
  const coverage = start && end ? `${start} to ${end}` : (start ?? end);
  const citations = Number(p.citations);
  const access = str(p.access_rights);
  const licence = str(p.licence);
  const doi = pickDoi(p.identifiers);
  const bbox = wktBbox(p.bbox);

  return [
    published && {
      icon: <CalendarMonthIcon />,
      label: "Published",
      value: published,
    },
    coverage && {
      icon: <AccessTimeIcon />,
      label: "Temporal extent",
      value: coverage,
    },
    citations > 0 && {
      icon: <FormatQuoteIcon />,
      label: "Citations",
      value: String(citations),
    },
    access && { icon: <LockIcon />, label: "Access rights", value: access },
    licence && {
      icon: <GavelIcon />,
      label: "Licence",
      value: licence,
      href: licence,
    },
    doi && { icon: <LinkIcon />, label: "DOI", value: doi, href: doi },
    bbox && { icon: <PublicIcon />, label: "Spatial extent", value: bbox },
  ].filter(Boolean) as MetaItem[];
}

const metaLink = (value: string, href: string) => (
  <Link
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    underline="always"
    color="primary"
  >
    {value}
  </Link>
);

const trim = (s: string, max = 25): string =>
  s.length > max ? `${s.slice(0, max)}...` : s;

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
            sx={{
              maxWidth: 160,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              px: 0.5,
            }}
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

function MetaToggleChip({
  open,
  onClick,
}: {
  open: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip title={open ? "hide metadata" : "show metadata"}>
      <Chip
        icon={open ? <CloseIcon /> : <MoreHorizIcon />}
        label=""
        onClick={onClick}
        size="small"
        variant="outlined"
        sx={{
          ...ICON_CHIP_SX,
          cursor: "pointer",
          "& .MuiChip-label": { px: 0 },
        }}
      />
    </Tooltip>
  );
}

function MetaChips({ items }: { items: MetaItem[] }) {
  return (
    <Box
      sx={{
        display: "flex",
        gap: 0.5,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      {items.slice(0, 3).map((it) => (
        <MetaChip key={it.label} {...it} />
      ))}
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
        <Box
          sx={{
            display: "flex",
            "& svg": { fontSize: "0.95rem", color: "text.disabled" },
          }}
        >
          <AccountTreeIcon />
        </Box>
        <Box sx={{ fontWeight: 600 }}>Type</Box>
        <Box sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
          {curieToUrl(type) ? metaLink(type, curieToUrl(type)!) : type}
        </Box>
      </Box>
      {items.map((it) => (
        <Box key={it.label} sx={{ display: "contents" }}>
          <Box
            sx={{
              display: "flex",
              "& svg": { fontSize: "0.95rem", color: "text.disabled" },
            }}
          >
            {it.icon}
          </Box>
          <Box sx={{ fontWeight: 600 }}>{it.label}</Box>
          <Box sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
            {it.href ? metaLink(it.value, it.href) : it.value}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

export default function DatasetResultCard({ group, index }: Props) {
  const { query } = useSearchStore();
  const [expanded, setExpanded] = useState(false);
  const [metaOpen, setMetaOpen] = useState(false);
  const { dataset, hits } = group;
  const items = metaItems(dataset.properties);
  const topScore = hits[0].score;

  return (
    <Card variant="outlined">
      <CardContent
        sx={{ p: 1.5, display: "flex", gap: 1.25, "&:last-child": { pb: 1.5 } }}
      >
        <TypeIcon type="dcat:Dataset" fontSize="1.75rem" />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{ display: "flex", alignItems: "flex-start", gap: 0.5, mb: 0.5 }}
          >
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
            <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexShrink: 0 }}>
              <ScoreChip score={topScore} />
              <TypeChip type="dcat:Dataset" color="primary" />
            </Box>
          </Box>

          <Typography
            variant="body2"
            noWrap
            sx={{ fontSize: "0.72rem", mb: 0.5 }}
          >
            <Link
              href={dataset.uri}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
              sx={{ color: "text.secondary" }}
            >
              {dataset.uri}
            </Link>
          </Typography>

          {items.length > 0 && (
            <Box
              sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center", mb: 0.5 }}
            >
              {!metaOpen && <MetaChips items={items} />}
              {items.length > 3 && (
                <MetaToggleChip
                  open={metaOpen}
                  onClick={() => setMetaOpen((v) => !v)}
                />
              )}
            </Box>
          )}

          <Collapse in={metaOpen} unmountOnExit>
            <MetaTable items={items} type="dcat:Dataset" />
          </Collapse>

          <Collapse in={expanded} unmountOnExit>
            <Box>
              {hits.map((r, i) => (
                <RelationshipPanel
                  key={i}
                  hit={r}
                  fallbackTitle={dataset.title}
                  divider={i > 0}
                />
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
                  context={{
                    type: "result",
                    index,
                    dataset_uri: dataset.uri,
                    query,
                  }}
                />
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
