import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CardContent,
  Collapse,
  Container,
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
import ConceptResultCard from "../components/ConceptResultCard";
import AISummary from "../components/AISummary";
import { groupHits, useSearchStore } from "../stores/searchStore";
import type { ConceptGroup } from "../stores/searchStore";
import { search } from "../api/search";
import { streamSummary, UsageLimitError } from "../api/chat";
import { EXAMPLE_SEARCHES } from "../constants";
import { TypeIcon, typeMeta } from "../typeMeta";

// Results within a type box are always sorted by score (inherited from the concept groups), so the
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

export default function ResultsPage() {
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") ?? "";
  const aiFromUrl = params.get("ai") === "true";
  const rt = params.get("type") || null;
  const {
    query,
    conceptType,
    results,
    loading,
    error,
    setQuery,
    setConceptType,
    setResults,
    setLoading,
    setError,
    aiSummaryEnabled,
    aiSummary,
    aiRun,
    setAiSummaryEnabled,
    setAiSummary,
    startAiRun,
    applyAiEvent,
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
    startAiRun();
    // Once aborted, this call's run has been superseded or abandoned: leave the store alone.
    const live = () => !controller.signal.aborted;
    // Text is held back until the run finishes: a keyword answer streams as a draft that
    // evaluation may still reject. Only the last message is the answer.
    let answer = "";
    try {
      await streamSummary(
        queryStr,
        (event) => {
          if (!live()) return;
          applyAiEvent(event);
          if (event.type === "TEXT_MESSAGE_START") answer = "";
          if (event.type === "TEXT_MESSAGE_CONTENT" && event.delta) answer += event.delta;
          if (event.type === "RUN_FINISHED") setAiSummary(answer);
        },
        controller.signal,
      );
    } catch (e) {
      if (live())
        applyAiEvent(
          e instanceof UsageLimitError
            ? { type: "USAGE_LIMIT", message: e.message }
            : { type: "RUN_ERROR", message: (e as Error).message },
        );
    }
    // Turns a run that never reached RUN_FINISHED/RUN_ERROR into an error; no-op otherwise.
    if (live()) applyAiEvent({ type: "STREAM_CLOSED" });
  };

  useEffect(() => {
    if (!q) return;
    if (q === query && rt === conceptType && results.length > 0) return;
    if (!EXAMPLE_SEARCHES.includes(q)) addRecentSearch(q);
    setQuery(q);
    setConceptType(rt);
    setLoading(true);
    setError(null);
    search(q, rt)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [q, rt]);

  // The summary answers the query alone, so a type filter change leaves it and its run details in place.
  useEffect(() => {
    if (!q) return;
    const newQuery = q !== query;
    if (newQuery) resetAiSummary();
    if (aiFromUrl && (newQuery || (!aiSummary && aiRun?.status !== "running"))) runSummary(q);
  }, [q, aiFromUrl]);

  useEffect(
    () => () => {
      summaryAbortRef.current?.abort();
      // An abandoned run would otherwise stay "running" and block the rerun when the page is revisited.
      if (useSearchStore.getState().aiRun?.status === "running") resetAiSummary();
    },
    [q],
  );

  // Hits grouped per concept (one card each), groups and their hits sorted by score.
  const groups = useMemo<ConceptGroup[]>(() => groupHits(results), [results]);

  // Type boxes for the unfiltered ("All") view: one box per OKF type, each internally sorted
  // by score (inherited from groups), boxes ordered by their own best score descending.
  const typeSections = useMemo(() => {
    const byType = new Map<string, ConceptGroup[]>();
    for (const g of groups) {
      const type = g.concept.type;
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type)!.push(g);
    }
    return Array.from(byType.entries())
      .map(([type, typeGroups]) => ({
        type,
        label: typeMeta(type).label,
        groups: typeGroups,
        topScore: typeGroups[0].hits[0].score,
      }))
      .sort((a, b) => b.topScore - a.topScore);
  }, [groups]);

  const [expandedTypes, setExpandedTypes] = useState<Record<string, boolean>>({});
  useEffect(() => {
    setExpandedTypes({});
  }, [q, rt]);

  const hasResults = groups.length > 0;

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

  const handleConceptType = (next: string | null) => {
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
          conceptType={rt}
          onConceptTypeChange={handleConceptType}
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
          {aiFromUrl && <AISummary query={q} />}

          {!rt ? (
            <>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                {groups.length} result
                {groups.length !== 1 ? "s" : ""} for "
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
                        {initial.map((g, i) => (
                          <ConceptResultCard key={g.concept.id} group={g} index={i} />
                        ))}
                      </Stack>
                      <Collapse in={expanded} unmountOnExit>
                        <Stack spacing={1.5} sx={{ mt: extra.length > 0 ? 1.5 : 0 }}>
                          {extra.map((g, i) => (
                            <ConceptResultCard key={g.concept.id} group={g} index={initialCount + i} />
                          ))}
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
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  mb: 2,
                }}
              >
                <Typography variant="subtitle2" color="text.secondary">
                  {groups.length} {(groups.length === 1 ? typeMeta(rt).name : typeMeta(rt).label).toLowerCase()} for "
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
                  {groups.map((g, i) => (
                    <ConceptResultCard key={g.concept.id} group={g} index={i} />
                  ))}
                </Masonry>
              ) : (
                <Stack spacing={2}>
                  {groups.map((g, i) => (
                    <ConceptResultCard key={g.concept.id} group={g} index={i} />
                  ))}
                </Stack>
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
