"""The final report must fail closed and render measured results safely."""

import copy
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[4]
SCRIPTS = PROJECT / ".agents/skills/joso-jdrt-runner/scripts"
sys.path.insert(0, str(SCRIPTS))
import jdrt_cell as cell
import jdrt_results as report


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "table":
            self.tables.append(0)
        if tag == "tr":
            self.tables[-1] += 1


class ResultsTests(unittest.TestCase):
    def test_unfinished_experiment_is_refused(self):
        current = cell.status(PROJECT)
        if current["next_incomplete"] is None:
            self.skipTest("The real experiment has already completed")
        with self.assertRaisesRegex(ValueError, "must be completed and recorded"):
            report.collect(PROJECT)

    def test_failed_collection_never_creates_or_replaces_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / report.OUTPUT_REL
            with patch.object(report, "collect", side_effect=ValueError("incomplete experiment")):
                with self.assertRaises(ValueError):
                    report.generate(root)
                self.assertFalse(output.exists())
                output.parent.mkdir(parents=True)
                original = b"existing generated artifact"
                output.write_bytes(original)
                with self.assertRaises(ValueError):
                    report.generate(root)
                self.assertEqual(output.read_bytes(), original)

    def test_html_renders_every_measured_row_with_correct_denominators_and_escaping(self):
        parameters = cell._json(PROJECT / cell.PARAMETERS_REL)
        measured = [json.loads(line) for line in (PROJECT / cell.LEDGER_REL).read_text(encoding="utf-8").splitlines() if line.strip()]
        measured.sort(key=lambda result: result["core_index"])
        data = {"parameters": parameters, "results": measured, "sources_sha256": {}, "excluded": []}
        data = copy.deepcopy(data)
        injected = '<script>alert("unsafe")</script>'
        data["results"][0]["run_id"] = injected
        document = report.render(PROJECT, data, PROJECT / report.OUTPUT_REL)
        parsed = Rows()
        parsed.feed(document)
        self.assertEqual(parsed.tables[:2], [len(measured) + 1] * 2)
        self.assertNotIn("script", parsed.tags)
        self.assertIn(escape(injected), document)
        result = measured[-1]
        denominator = parameters["population"]["type4"]
        self.assertIn(f'{result["type4_evacuated"]} / {denominator}<br>{result["type4_evacuated"] / denominator * 100:.3f}%', document)
        self.assertIn('lang="ja"', document)
        self.assertIn("人口全体", document)
        self.assertIn("母数", document)


if __name__ == "__main__":
    unittest.main()
