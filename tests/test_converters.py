from haystack.dataclasses import ByteStream
from serka.converters import EIDCConverter, HTMLConverter
from haystack.components.preprocessors import DocumentSplitter
from haystack import Pipeline
import json


def test_html_converter_with_valid_source():
	test_text = "This is some test text for the web page"
	test_title = "Page title"
	test_date = "2025-01-01"
	test_author = "Joe Bloggs"
	test_html = f"""
	<html>
		<head>
			<title>{test_title}</title>
			<meta name="author" content="{test_author}">
			<meta name="date" content="{test_date}">
		</head>
		<body>
			<section>
				<p>{test_text}</p>
			</section>
		</body>
	</html>
	"""
	input = [ByteStream(test_html.encode()), ByteStream(test_html.encode())]
	converter = HTMLConverter()
	result = converter.run(input)

	assert "documents" in result
	assert len(result["documents"]) == 2
	doc = result["documents"][0]
	assert doc.content == test_text
	assert doc.meta["title"] == test_title
	assert doc.meta["author"] == test_author
	assert doc.meta["date"] == test_date


def test_html_converter_integration():
	p = Pipeline()
	p.add_component("convter", HTMLConverter())
	p.add_component("splitter", DocumentSplitter())
	p.connect("convter", "splitter")
	p.run(
		data={
			"convter": {
				"sources": [ByteStream(b"<html><body><p>Test</p></body></html>")]
			}
		}
	)


def test_eidc_converter_with_valid_source():
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
