import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CardContent,
  Collapse,
  Container,
  Divider,
  IconButton,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import ViewModuleIcon from "@mui/icons-material/ViewModule";
import ViewListIcon from "@mui/icons-material/ViewList";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import Masonry from "@mui/lab/Masonry";
import SearchBar from "../components/SearchBar";
import DatasetResultCard from "../components/DatasetResultCard";
import EntityResultCard from "../components/EntityResultCard";
import AISummary from "../components/AISummary";
import { useSearchStore } from "../stores/searchStore";
import type { Entity, ReturnType, SearchHit } from "../stores/searchStore";
import { search } from "../api/search";
import { streamSummary } from "../api/chat";
import { EXAMPLE_SEARCHES } from "../constants";
import { TYPE_ORDER, TypeIcon, typeMeta } from "../typeMeta";

// Results within a type box are always sorted by score (inherited from unifiedGroups), so the
// first group's top hit is that type's best score. Boxes whose best score trails the overall
// best by a wide margin start collapsed to 1-2 items instead of the full 3 — a big relevance
// gap is a signal the type is a weaker match, not worth as much initial screen space.
const INITIAL_COUNT_MAX = 3;

function initialCountFor(topScore: number, bestOverallScore: number): number {
  if (bestOverallScore <= 0) return INITIAL_COUNT_MAX;
  const ratio = topScore / bestOverallScore;
  if (ratio >= 0.85) return INITIAL_COUNT_MAX;
  if (ratio >= 0.6) return 2;
  return 1;
}

const ENTITY_TYPE_ORDER = TYPE_ORDER.filter((t) => t !== "dcat:Dataset");

type EntityGroup = { entity: Entity; hits: SearchHit[] };

const isDataset = (g: EntityGroup) => g.entity["@type"].includes("dcat:Dataset");
const entityKey = (e: Entity) => e["@id"] ?? "";

export default function ResultsPage() {
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") ?? "";
  const aiFromUrl = params.get("ai") === "true";
  const rt = (params.get("type") as ReturnType) || null;
  const {
    query,
    returnType,
    results,
    loading,
    error,
    setQuery,
    setReturnType,
    setResults,
    setLoading,
    setError,
    aiSummaryEnabled,
    aiSummary,
    aiLoading,
    setAiSummaryEnabled,
    appendAiSummary,
    setAiModel,
    setAiDate,
    setAiThinking,
    setAiLoading,
    resetAiSummary,
    addRecentSearch,
  } = useSearchStore();

  const [searchFocused, setSearchFocused] = useState(false);
  useEffect(() => {
    setSearchFocused(false);
  }, [q]);

  useEffect(() => {
    if (aiFromUrl !== aiSummaryEnabled) setAiSummaryEnabled(aiFromUrl);
  }, [aiFromUrl]);

  const summaryAbortRef = useRef<AbortController | null>(null);

  const runSummary = async (queryStr: string) => {
    summaryAbortRef.current?.abort();
    const controller = new AbortController();
    summaryAbortRef.current = controller;
    setAiLoading(true);
    try {
      await streamSummary(
        queryStr,
        (event) => {
          if (event.type === "RUN_METADATA" && event.model)
            setAiModel(event.model);
          if (event.type === "THINKING_START") setAiThinking(true);
          if (event.type === "THINKING_END") setAiThinking(false);
          if (event.type === "TEXT_MESSAGE_CONTENT" && event.delta)
            appendAiSummary(event.delta);
          if (event.type === "RUN_FINISHED") {
            setAiDate(
              new Date().toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
              }),
            );
            setAiLoading(false);
          }
        },
        controller.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") setAiLoading(false);
    }
  };

  useEffect(() => {
    if (!q) return;
    if (q === query && rt === returnType && results.length > 0) return;
    if (!EXAMPLE_SEARCHES.includes(q)) addRecentSearch(q);
    setQuery(q);
    setReturnType(rt);
    resetAiSummary();
    setLoading(true);
    setError(null);
    search(q, rt)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    if (aiFromUrl) runSummary(q);
    return () => {
      summaryAbortRef.current?.abort();
    };
  }, [q, rt]);

  useEffect(() => {
    if (
      aiFromUrl &&
      q &&
      q === query &&
      results.length > 0 &&
      !aiSummary &&
      !aiLoading
    ) {
      runSummary(q);
    }
  }, [aiFromUrl]);

  // All hits grouped per entity, hits sorted by score, groups sorted by relevance.
  // The dataset and per-type views below are derived from this single pass; the
  // unified list ("Any" search) uses it directly.
  const unifiedGroups = useMemo<EntityGroup[]>(() => {
    const byId = new Map<string, EntityGroup>();
    for (const r of results) {
      const key = r.entity["@id"] ?? r.excerpt ?? "";
      const g = byId.get(key) ?? { entity: r.entity, hits: [] };
      g.hits.push(r);
      byId.set(key, g);
    }
    return Array.from(byId.values())
      .map((g) => ({
        ...g,
        hits: [...g.hits].sort((a, b) => b.score - a.score),
      }))
      .sort((a, b) => b.hits[0].score - a.hits[0].score);
  }, [results]);

  const datasetGroups = useMemo(
    () => unifiedGroups.filter(isDataset),
    [unifiedGroups],
  );

  // Non-dataset groups bucketed by DOO type; relevance order is preserved from unifiedGroups.
  const entityByType = useMemo<Map<string, EntityGroup[]>>(() => {
    const byType = new Map<string, EntityGroup[]>();
    for (const g of unifiedGroups) {
      if (isDataset(g)) continue;
      const type = g.entity["@type"][0] ?? "unknown";
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type)!.push(g);
    }
    return byType;
  }, [unifiedGroups]);

  // Type boxes for the unfiltered ("Any") view: one box per DOO type, each internally sorted
  // by score (inherited from unifiedGroups), boxes ordered by their own best score descending.
  const typeSections = useMemo(() => {
    const byType = new Map<string, EntityGroup[]>();
    for (const g of unifiedGroups) {
      const type = isDataset(g) ? "dcat:Dataset" : (g.entity["@type"][0] ?? "unknown");
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type)!.push(g);
    }
    return Array.from(byType.entries())
      .map(([type, groups]) => ({
        type,
        label: typeMeta(type).label,
        groups,
        topScore: groups[0].hits[0].score,
      }))
      .sort((a, b) => b.topScore - a.topScore);
  }, [unifiedGroups]);

  const [expandedTypes, setExpandedTypes] = useState<Record<string, boolean>>({});
  useEffect(() => {
    setExpandedTypes({});
  }, [q, rt]);

  const hasResults = unifiedGroups.length > 0;

  const [viewMode, setViewMode] = useState<"masonry" | "list">("list");

  const handleSearch = (newQ: string) => {
    const sp = new URLSearchParams({ q: newQ });
    if (aiFromUrl) sp.set("ai", "true");
    if (rt) sp.set("type", rt);
    navigate(`/search?${sp}`);
  };

  const handleExampleSearch = (newQ: string) => {
    const sp = new URLSearchParams({ q: newQ, ai: "true" });
    if (rt) sp.set("type", rt);
    navigate(`/search?${sp}`);
  };

  const handleReturnType = (next: ReturnType | null) => {
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev);
      if (next) sp.set("type", next);
      else sp.delete("type");
      return sp;
    });
  };

  const handleAiSummary = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (prev.get("ai") === "true") next.delete("ai");
      else next.set("ai", "true");
      return next;
    });
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {searchFocused && (
        <Box
          sx={{
            position: "fixed",
            inset: 0,
            zIndex: 1101,
            bgcolor: "rgba(0,0,0,0.35)",
            backdropFilter: "blur(4px)",
          }}
        />
      )}
      <Box
        sx={{
          mb: 4,
          position: "relative",
          zIndex: searchFocused ? 1102 : "auto",
        }}
      >
        <SearchBar
          key={q}
          onSearch={handleSearch}
          initialValue={q}
          onAiSummary={!loading && hasResults ? handleAiSummary : undefined}
          aiSummaryActive={aiFromUrl}
          showSuggestions
          onFocusChange={setSearchFocused}
          onExampleSearch={handleExampleSearch}
          returnType={rt}
          onReturnTypeChange={handleReturnType}
        />
      </Box>

      {loading && (
        <Stack spacing={2}>
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} variant="outlined">
              <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
                <Skeleton variant="text" width="70%" sx={{ mb: 1 }} />
                <Skeleton variant="text" width="100%" />
                <Skeleton variant="text" width="100%" />
                <Skeleton variant="text" width="55%" />
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      {error && (
        <Typography color="error" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}

      {!loading && hasResults && (
        <>
          <AISummary query={q} />

          {!rt ? (
            <>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                {unifiedGroups.length} result
                {unifiedGroups.length !== 1 ? "s" : ""} for "
                <strong>{q}</strong>"
              </Typography>
              <Stack spacing={2}>
                {typeSections.map((section) => {
                  const bestOverallScore = typeSections[0].topScore;
                  const initialCount = Math.min(
                    initialCountFor(section.topScore, bestOverallScore),
                    section.groups.length,
                  );
                  const expanded = expandedTypes[section.type] ?? false;
                  const initial = section.groups.slice(0, initialCount);
                  const extra = section.groups.slice(initialCount);
                  const isDatasetType = section.type === "dcat:Dataset";
                  const canCollapse = extra.length > 0;

                  return (
                    <Box
                      key={section.type}
                      sx={{
                        border: 1,
                        borderColor: "divider",
                        borderRadius: 2,
                        p: 2,
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 0.75,
                          mb: 1.5,
                        }}
                      >
                        <TypeIcon type={section.type} />
                        <Typography
                          variant="subtitle2"
                          sx={{ fontWeight: 600 }}
                        >
                          {section.label}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                        >
                          ({section.groups.length})
                        </Typography>
                      </Box>
                      <Stack spacing={1.5}>
                        {initial.map((g, i) =>
                          isDatasetType ? (
                            <DatasetResultCard
                              key={entityKey(g.entity)}
                              hits={g.hits}
                              index={i}
                            />
                          ) : (
                            <EntityResultCard
                              key={entityKey(g.entity)}
                              hits={g.hits}
                              index={i}
                            />
                          ),
                        )}
                      </Stack>
                      <Collapse in={expanded} unmountOnExit>
                        <Stack spacing={1.5} sx={{ mt: extra.length > 0 ? 1.5 : 0 }}>
                          {extra.map((g, i) =>
                            isDatasetType ? (
                              <DatasetResultCard
                                key={entityKey(g.entity)}
                                hits={g.hits}
                                index={initialCount + i}
                              />
                            ) : (
                              <EntityResultCard
                                key={entityKey(g.entity)}
                                hits={g.hits}
                                index={initialCount + i}
                              />
                            ),
                          )}
                        </Stack>
                      </Collapse>
                      {canCollapse && (
                        <Button
                          size="small"
                          onClick={() =>
                            setExpandedTypes((s) => ({
                              ...s,
                              [section.type]: !expanded,
                            }))
                          }
                          startIcon={
                            expanded ? (
                              <ExpandLessIcon />
                            ) : (
                              <ExpandMoreIcon />
                            )
                          }
                          sx={{ mt: 1, textTransform: "none" }}
                        >
                          {expanded
                            ? `Show fewer ${section.label.toLowerCase()}`
                            : `Show more ${section.label.toLowerCase()} (${
                                section.groups.length - initialCount
                              } more)`}
                        </Button>
                      )}
                    </Box>
                  );
                })}
              </Stack>
            </>
          ) : (
            <>
              {datasetGroups.length > 0 && (
                <>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      mb: 2,
                    }}
                  >
                    <Typography variant="subtitle2" color="text.secondary">
                      {datasetGroups.length} dataset
                      {datasetGroups.length !== 1 ? "s" : ""} for "
                      <strong>{q}</strong>"
                    </Typography>
                    <Box>
                      <Tooltip title="Grid view">
                        <IconButton
                          size="small"
                          onClick={() => setViewMode("masonry")}
                          color={viewMode === "masonry" ? "primary" : "default"}
                        >
                          <ViewModuleIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="List view">
                        <IconButton
                          size="small"
                          onClick={() => setViewMode("list")}
                          color={viewMode === "list" ? "primary" : "default"}
                        >
                          <ViewListIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>

                  {viewMode === "masonry" ? (
                    <Masonry columns={{ xs: 1, sm: 2, md: 3 }} spacing={2}>
                      {datasetGroups.map((g, i) => (
                        <DatasetResultCard
                          key={entityKey(g.entity)}
                          hits={g.hits}
                          index={i}
                        />
                      ))}
                    </Masonry>
                  ) : (
                    <Stack spacing={2}>
                      {datasetGroups.map((g, i) => (
                        <DatasetResultCard
                          key={entityKey(g.entity)}
                          hits={g.hits}
                          index={i}
                        />
                      ))}
                    </Stack>
                  )}
                </>
              )}

              {entityByType.size > 0 &&
                ENTITY_TYPE_ORDER.filter((t) => entityByType.has(t)).map(
                  (type) => {
                    const groups = entityByType.get(type)!;
                    const label = typeMeta(type).label;
                    return (
                      <Box
                        key={type}
                        sx={{ mt: datasetGroups.length > 0 ? 4 : 0 }}
                      >
                        {datasetGroups.length > 0 && <Divider sx={{ mb: 3 }} />}
                        <Typography
                          variant="subtitle2"
                          color="text.secondary"
                          sx={{ mb: 2 }}
                        >
                          {groups.length} {label.toLowerCase()} for "
                          <strong>{q}</strong>"
                        </Typography>
                        <Stack spacing={1.5}>
                          {groups.map((g, i) => (
                            <EntityResultCard
                              key={entityKey(g.entity)}
                              hits={g.hits}
                              index={i}
                            />
                          ))}
                        </Stack>
                      </Box>
                    );
                  },
                )}
            </>
          )}
        </>
      )}

      {!loading && !error && !hasResults && q && (
        <Box sx={{ mt: 4 }}>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            No results found for "<strong>{q}</strong>". Try one of these
            instead:
          </Typography>
          <Stack spacing={1} sx={{ maxWidth: 560 }}>
            {EXAMPLE_SEARCHES.map((t) => (
              <Box
                key={t}
                component="button"
                onClick={() => handleExampleSearch(t)}
                sx={{
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 2,
                  px: 2,
                  py: 1.25,
                  background: "transparent",
                  color: "text.secondary",
                  cursor: "pointer",
                  fontSize: "0.875rem",
                  fontFamily: "inherit",
                  textAlign: "left",
                  transition: "border-color 0.15s, color 0.15s",
                  "&:hover": {
                    borderColor: "primary.main",
                    color: "text.primary",
                  },
                }}
              >
                {t}
              </Box>
            ))}
          </Stack>
        </Box>
      )}
    </Container>
  );
}
