import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  Card,
  CardContent,
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
import Masonry from "@mui/lab/Masonry";
import SearchBar from "../components/SearchBar";
import DatasetResultCard, {
  type GroupedResult,
} from "../components/DatasetResultCard";
import EntityResultCard from "../components/EntityResultCard";
import AISummary from "../components/AISummary";
import { useSearchStore } from "../stores/searchStore";
import type { SearchHit } from "../stores/searchStore";
import { search } from "../api/search";
import { streamSummary } from "../api/chat";
import { EXAMPLE_SEARCHES } from "../constants";

const TYPE_SECTION_LABEL: Record<string, string> = {
  "foaf:Person": "People",
  "foaf:Organization": "Organisations",
  "skos:Concept": "Concepts",
  "fabio:Expression": "Documents",
};

const ENTITY_TYPE_ORDER = [
  "foaf:Person",
  "foaf:Organization",
  "skos:Concept",
  "fabio:Expression",
];

export default function ResultsPage() {
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") ?? "";
  const aiFromUrl = params.get("ai") === "true";
  const {
    query,
    results,
    loading,
    error,
    setQuery,
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
    if (q === query && results.length > 0) return;
    if (!EXAMPLE_SEARCHES.includes(q)) addRecentSearch(q);
    setQuery(q);
    resetAiSummary();
    setLoading(true);
    setError(null);
    search(q)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    if (aiFromUrl) runSummary(q);
    return () => {
      summaryAbortRef.current?.abort();
    };
  }, [q]);

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

  // Group dcat:Dataset hits (text + metadata) by URI
  const datasetGroups = useMemo<GroupedResult[]>(() => {
    const map = new Map<string, GroupedResult>();
    for (const r of results) {
      if (!r.entity.type.includes("dcat:Dataset")) continue;
      const key = r.entity.id;
      if (!map.has(key))
        map.set(key, {
          dataset: {
            uri: r.entity.id,
            title: r.entity.label ?? r.entity.id,
            properties: r.entity.properties,
          },
          hits: [],
        });
      map.get(key)!.hits.push(r);
    }
    return Array.from(map.values())
      .map((g) => ({ ...g, hits: g.hits.sort((a, b) => b.score - a.score) }))
      .sort((a, b) => b.hits[0].score - a.hits[0].score);
  }, [results]);

  // Deduplicated non-dataset hits, grouped by DOO type
  const entityByType = useMemo<Map<string, SearchHit[]>>(() => {
    const map = new Map<string, SearchHit[]>();
    const seen = new Set<string>();
    for (const r of results) {
      if (r.entity.type.includes("dcat:Dataset")) continue;
      if (seen.has(r.entity.id)) continue;
      seen.add(r.entity.id);
      const type = r.entity.type[0] ?? "unknown";
      if (!map.has(type)) map.set(type, []);
      map.get(type)!.push(r);
    }
    return map;
  }, [results]);

  const hasResults = datasetGroups.length > 0 || entityByType.size > 0;

  const [viewMode, setViewMode] = useState<"masonry" | "list">("list");

  const handleSearch = (newQ: string) => {
    const sp = new URLSearchParams({ q: newQ });
    if (aiFromUrl) sp.set("ai", "true");
    navigate(`/search?${sp}`);
  };

  const handleExampleSearch = (newQ: string) => {
    const sp = new URLSearchParams({ q: newQ, ai: "true" });
    navigate(`/search?${sp}`);
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
                      key={g.dataset.uri}
                      group={g}
                      index={i}
                      collapsedLines={Math.min(g.hits.length * 3 + 2, 20)}
                    />
                  ))}
                </Masonry>
              ) : (
                <Stack spacing={2}>
                  {datasetGroups.map((g, i) => (
                    <DatasetResultCard
                      key={g.dataset.uri}
                      group={g}
                      index={i}
                      collapsedLines={5}
                    />
                  ))}
                </Stack>
              )}
            </>
          )}

          {entityByType.size > 0 &&
            ENTITY_TYPE_ORDER.filter((t) => entityByType.has(t)).map((type) => {
              const hits = entityByType.get(type)!;
              const label = TYPE_SECTION_LABEL[type] ?? type;
              return (
                <Box key={type} sx={{ mt: datasetGroups.length > 0 ? 4 : 0 }}>
                  {datasetGroups.length > 0 && <Divider sx={{ mb: 3 }} />}
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    sx={{ mb: 2 }}
                  >
                    {hits.length} {label.toLowerCase()} for "
                    <strong>{q}</strong>"
                  </Typography>
                  <Stack spacing={1.5}>
                    {hits.map((hit) => (
                      <EntityResultCard key={hit.entity.id} hit={hit} />
                    ))}
                  </Stack>
                </Box>
              );
            })}
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
