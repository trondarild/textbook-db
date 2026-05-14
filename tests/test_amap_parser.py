import pytest
from src.amap_parser import (
    parse_claims, priority_claims, parse_gap_report, parse_citations_block
)

_CLAIMS = """\
↓ ? stub_claim (!) "Not yet formulated — needs evidence" [Author 2016]
↓ ~ drafted_claim (T) "Drafted but not yet cited" [Smith 2005]
↓ * cited_claim (E) "Cited and ready" [Jones 2001; Doe 2003]
↓ ✓ complete_claim (R) "Fully verified claim" [Brown 1999]
↓ naked_claim (!) "Bare claim with no status marker"
"""

_GAP_REPORT = (
    "## Gap report\n\n"
    "```\n"
    "STRUCTURAL GAPS\n"
    "───────────────\n"
    "G1  3.5 transition: some_label needs a citation\n"
    "G2  3.7 another gap\n"
    "\n"
    "NAKED ASSERTIONS (!) \"— require argument or citation\n"
    "───────────────\n"
    "  naked_label     (3.5)  — cite arousal-scale literature\n"
    "\n"
    "STUBS — not ready for prose\n"
    "───────────────\n"
    "  stub_label (3.6) — develop or soften\n"
    "```\n"
)

_CITATIONS_BLOCK = """\
Some preamble text.

CITATIONS
  claim_one  (R): Nagel1974, Chalmers1995
  claim_two  (E): CrickKoch1998
  claim_three (T): Friston2010

Next section here.
"""


class TestParseClaims:
    def test_parses_all_claims(self):
        assert len(parse_claims(_CLAIMS)) == 5

    def test_label_extracted(self):
        claims = parse_claims(_CLAIMS)
        assert claims[0]['label'] == 'stub_claim'

    def test_status_question_mark(self):
        claims = parse_claims(_CLAIMS)
        assert claims[0]['status'] == '?'

    def test_status_tilde(self):
        claims = parse_claims(_CLAIMS)
        assert claims[1]['status'] == '~'

    def test_status_star(self):
        claims = parse_claims(_CLAIMS)
        assert claims[2]['status'] == '*'

    def test_status_checkmark(self):
        claims = parse_claims(_CLAIMS)
        assert claims[3]['status'] == '✓'

    def test_status_absent(self):
        claims = parse_claims(_CLAIMS)
        assert claims[4]['status'] == ''

    def test_type_extracted(self):
        claims = parse_claims(_CLAIMS)
        assert claims[0]['type'] == '!'
        assert claims[1]['type'] == 'T'
        assert claims[2]['type'] == 'E'
        assert claims[3]['type'] == 'R'

    def test_citations_split_on_semicolon(self):
        claims = parse_claims(_CLAIMS)
        assert 'Jones 2001' in claims[2]['citations']
        assert 'Doe 2003' in claims[2]['citations']

    def test_single_citation(self):
        claims = parse_claims(_CLAIMS)
        assert claims[0]['citations'] == ['Author 2016']

    def test_no_citation_block(self):
        line = '↓ * no_cite (T) "No citations here"'
        assert parse_claims(line)[0]['citations'] == []

    def test_legacy_star_question_status(self):
        line = '↓ *? old_format (T) "Legacy notation"'
        claims = parse_claims(line)
        assert len(claims) == 1
        assert claims[0]['status'] == '*?'


class TestPriorityClaims:
    def test_stubs_are_primary(self):
        claims = parse_claims(_CLAIMS)
        priority = priority_claims(claims)
        assert priority[0]['label'] == 'stub_claim'

    def test_drafted_included(self):
        claims = parse_claims(_CLAIMS)
        priority = priority_claims(claims)
        assert any(c['label'] == 'drafted_claim' for c in priority)

    def test_cited_excluded(self):
        claims = parse_claims(_CLAIMS)
        priority = priority_claims(claims)
        assert not any(c['label'] == 'cited_claim' for c in priority)

    def test_complete_excluded(self):
        claims = parse_claims(_CLAIMS)
        priority = priority_claims(claims)
        assert not any(c['label'] == 'complete_claim' for c in priority)

    def test_stubs_before_drafted(self):
        claims = parse_claims(_CLAIMS)
        priority = priority_claims(claims)
        statuses = [c['status'] for c in priority]
        if '?' in statuses and '~' in statuses:
            assert statuses.index('?') < statuses.index('~')


class TestParseCitationsBlock:
    def test_parses_labels(self):
        cites = parse_citations_block(_CITATIONS_BLOCK)
        assert 'claim_one' in cites
        assert 'claim_two' in cites

    def test_parses_refs(self):
        cites = parse_citations_block(_CITATIONS_BLOCK)
        assert 'Nagel1974' in cites['claim_one']
        assert 'Chalmers1995' in cites['claim_one']

    def test_single_ref(self):
        cites = parse_citations_block(_CITATIONS_BLOCK)
        assert cites['claim_two'] == ['CrickKoch1998']

    def test_no_citations_block(self):
        assert parse_citations_block("No citations block here.") == {}


class TestParseGapReport:
    def test_structural_gaps_found(self):
        gaps = parse_gap_report(_GAP_REPORT)
        assert any('G1' in g for g in gaps['structural'])
        assert any('G2' in g for g in gaps['structural'])

    def test_naked_assertion_label(self):
        gaps = parse_gap_report(_GAP_REPORT)
        assert any(g['label'] == 'naked_label' for g in gaps['naked_assertions'])

    def test_stub_label(self):
        gaps = parse_gap_report(_GAP_REPORT)
        assert any(g['label'] == 'stub_label' for g in gaps['stubs'])

    def test_no_gap_report_returns_empty(self):
        gaps = parse_gap_report("No gap report section here.")
        assert gaps == {'structural': [], 'naked_assertions': [], 'stubs': []}
