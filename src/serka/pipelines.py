from dataclasses import dataclass
from haystack import Pipeline
from serka.graph.extractors import EntityExtractor, DocumentTruncator
from serka.fetchers import ConceptHierarchyFetcher, EIDCFetcher, LegiloFetcher
from serka.okf.writer import OKFBundleWriter


@dataclass
class PipelineBuilder:
	okf_bundle_dir: str
	legilo_pat: str

	def build_graph_pipeline(self) -> Pipeline:
		"""Fetches EIDC records and Legilo supporting files and writes them as an OKF bundle."""
		p = Pipeline()
		p.add_component("eidc_fetcher", EIDCFetcher())
		p.add_component(
			"legilo_fetcher",
			LegiloFetcher(token=self.legilo_pat),
		)
		p.add_component("ent_extractor", EntityExtractor())
		p.add_component("concept_hierarchy", ConceptHierarchyFetcher())
		p.add_component("truncator", DocumentTruncator())
		p.add_component("okf_writer", OKFBundleWriter(bundle_dir=self.okf_bundle_dir))

		p.connect("eidc_fetcher", "ent_extractor")
		p.connect("eidc_fetcher", "legilo_fetcher")
		p.connect("eidc_fetcher", "okf_writer.records")

		p.connect("legilo_fetcher.documents", "truncator.documents")
		p.connect("truncator.documents", "okf_writer.documents")

		p.connect("ent_extractor.nodes", "concept_hierarchy.nodes")
		p.connect("ent_extractor.relationships", "concept_hierarchy.relationships")
		p.connect("concept_hierarchy.nodes", "okf_writer.nodes")
		p.connect("concept_hierarchy.relationships", "okf_writer.relationships")
		return p
