from haystack.dataclasses import ByteStream
from serka.converters import EIDCConverter
import json


def test_run_with_valid_source():
	test_field = "test_field"
	test_val = "test_value"
	test_title = "test_title"
	test_url = "http://example.com"
	test_source = {
		"results": [
			{
				test_field: test_val,
				"title": test_title,
				"resourceIdentifier": [test_url],
			}
		]
	}

	converter = EIDCConverter({"test_field"})
	result = converter.run([ByteStream(json.dumps(test_source).encode())])

	assert "documents" in result
	assert len(result["documents"]) == 1
	assert result["documents"][0].content == test_val
	assert result["documents"][0].meta["section"] == test_field
	assert result["documents"][0].meta["dataset"] == test_title
	assert result["documents"][0].meta["url"] == test_url
