from pandas import DataFrame, to_datetime
from typing import List, Dict, Tuple
import re


class KGBuilder:
	def __init__(self, data):
		self.df: DataFrame = DataFrame(data)

	def pad_lists(self, columns):
		def pad_row(row):
			max_length = max(len(row[col]) for col in columns)
			return {
				col: row[col] + [None] * (max_length - len(row[col])) for col in columns
			}

		self.df[columns] = self.df.apply(pad_row, axis=1, result_type="expand")

	def extract(self, column_mapping: Dict[str, str]):
		columns = list(column_mapping.keys())
		self.pad_lists(columns)
		extracted_data = self.df[columns].explode(columns).to_dict(orient="records")
		details = [
			{column_mapping[k]: v for k, v in item.items() if v is not None}
			for item in extracted_data
		]
		return [item for item in details if "uri" in item]

	def extract_authors(self):
		column_mapping = {
			"authorGivenName": "forename",
			"authorFamilyName": "surname",
			"authorOrcid": "uri",
		}
		return self.extract(column_mapping)

	def extract_orgs(self) -> List[Dict[str, str]]:
		column_mapping = {"authorAffiliation": "name", "authorRor": "uri"}
		return self.extract(column_mapping)

	def extract_datasets(self) -> List[Dict[str, str]]:
		self.df["publicationDate"] = to_datetime(
			self.df["publicationDate"], errors="coerce"
		)
		column_mapping = {
			"resourceIdentifier": "uri",
			"title": "title",
			"description": "description",
			"lineage": "lineage",
			"publicationDate": "date",
		}
		columns = column_mapping.keys()
		datasets = self.df[columns].to_dict(orient="records")
		dataset_details = [
			{column_mapping[k]: v for k, v in dataset.items() if v is not None}
			for dataset in datasets
		]
		for dataset in dataset_details:
			dataset["uri"] = self.get_doi_from_list(dataset["uri"])
		return dataset_details

	def extract_affiliations(self) -> List[Tuple[str]]:
		columns = ["authorOrcid", "authorRor"]
		self.pad_lists(columns)
		affiliations = self.df.explode(columns, ignore_index=True)
		affiliations = affiliations.dropna(subset=columns)
		return list(zip(affiliations["authorOrcid"], affiliations["authorRor"]))

	def get_doi_from_list(self, uris: List[str]):
		for uri in uris:
			match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", uri, re.IGNORECASE)
			if match:
				return f"https://doi.org/{match.group(0)}"
		return None

	def extract_authorship(self) -> List[Tuple[str]]:
		columns = ["authorOrcid"]
		authorship_df = self.df.explode(columns, ignore_index=True)
		authorshipDetails = list(
			zip(authorship_df["resourceIdentifier"], authorship_df["authorOrcid"])
		)
		authorshipDetails = [
			(authorship[0], authorship[1])
			for authorship in authorshipDetails
			if authorship[1] is not None and authorship[0] is not None
		]
		return [
			(self.get_doi_from_list(authorship[0]), authorship[1])
			for authorship in authorshipDetails
		]
