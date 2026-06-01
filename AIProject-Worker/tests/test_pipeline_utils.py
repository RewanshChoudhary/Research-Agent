import unittest

from bs4 import BeautifulSoup

from worker.agents.fact_checker import calculate_confidence
from worker.agents.report_builder import build_worker_request
from worker.agents.scraper import chunk_text, extract_main_text
from worker.agents.search import rank_and_filter_results
from worker.agents.search import _fallback_search_phrases, _should_optimize_query
from worker.agent_output import ResearchContext
from worker.core.consumer import extract_job_id
from worker.enums import Depth, Domain
from worker.schemas import WorkerJobDetailsResponse


class PipelineUtilityTests(unittest.TestCase):
    def test_search_ranking_filters_excluded_and_prefers_trusted(self):
        results = [
            {"url": "https://reddit.com/r/x", "title": "Semaglutide", "snippet": "forum"},
            {"url": "https://pubmed.ncbi.nlm.nih.gov/123", "title": "Semaglutide trial", "snippet": "clinical study"},
            {"url": "https://example.com/a", "title": "Semaglutide", "snippet": "overview"},
        ]

        ranked = rank_and_filter_results(
            results,
            "semaglutide clinical study",
            {"trusted_sources": ["pubmed.ncbi.nlm.nih.gov"], "excluded_sources": ["reddit.com"]},
            [],
            [],
            5,
        )

        self.assertEqual("https://pubmed.ncbi.nlm.nih.gov/123", ranked[0]["url"])
        self.assertEqual(2, len(ranked))

    def test_scraper_extracts_main_text_and_chunks_with_overlap(self):
        soup = BeautifulSoup(
            "<html><body><nav>menu</nav><main><p>Hello world.</p><p>Useful text.</p></main></body></html>",
            "html.parser",
        )

        self.assertEqual("Hello world. Useful text.", extract_main_text(soup))
        chunks = chunk_text(" ".join(str(i) for i in range(12)), chunk_size=5, overlap=2)
        self.assertEqual(["0 1 2 3 4", "3 4 5 6 7", "6 7 8 9 10", "9 10 11"], chunks)

    def test_confidence_is_clamped_and_penalized(self):
        self.assertEqual(0.85, calculate_confidence(9, 10, 1))
        self.assertEqual(0.0, calculate_confidence(0, 0, 0))

    def test_report_payload_is_valid_with_fallback_findings(self):
        request = WorkerJobDetailsResponse(
            jobId="00000000-0000-0000-0000-000000000001",
            query="test query",
            domain=Domain.GENERAL,
            depth=Depth.QUICK,
            factCheckEnabled=False,
            maxSources=1,
        )
        ctx = ResearchContext(request=request)
        ctx.urls = ["https://example.com/a"]
        ctx.search_results = {"https://example.com/a": {"title": "A", "domain": "example.com"}}
        ctx.scraped_content = {"https://example.com/a": "content"}
        ctx.source_summaries = {"https://example.com/a": "summary"}
        ctx.combined_summary = "First finding. Second finding. Third finding."

        payload = build_worker_request(ctx, 12)

        self.assertEqual(3, len(payload.keyFindings))
        self.assertEqual(1, payload.totalSourcesProcessed)

    def test_consumer_ignores_messages_without_valid_job_id(self):
        self.assertIsNone(extract_job_id({"start": "1"}))
        self.assertIsNone(extract_job_id({"jobId": ""}))
        self.assertIsNone(extract_job_id({"jobId": "not-a-uuid"}))
        self.assertEqual(
            "00000000-0000-0000-0000-000000000001",
            extract_job_id({"jobId": b"00000000-0000-0000-0000-000000000001"}),
        )

    def test_search_optimizes_long_compare_queries(self):
        query = (
            "Compare autonomous coding agents, code review automation, test generation, "
            "security vulnerability detection, productivity impact, and hallucinated code risks."
        )

        self.assertTrue(_should_optimize_query(query))
        self.assertIn("autonomous", _fallback_search_phrases(query)[0])


if __name__ == "__main__":
    unittest.main()
