#!/usr/bin/env python

import unittest
from tree_sitter import Language, Parser
from tree_sitter_markdown import language as markdown_language

# Assuming the script is run from the project root, this import should work.
from playground.markdown_query import build_heading_tree, find_sections, parse_query, Heading

SAMPLE_MARKDOWN = b"""# Section 1

Some text in section 1.

## Section 1.1

Content of 1.1.

## Section 1.2

Content of 1.2.

### Section 1.2.1

Content of 1.2.1.

# Section 2

Content of section 2.

## Section 2.1

Content of 2.1

## Section 2.2

Content of 2.2
"""


class TestParseQuery(unittest.TestCase):
    """Tests for the query parsing function."""

    def test_parse_query_simple(self):
        self.assertEqual(parse_query("1"), [[[1]]])
        self.assertEqual(parse_query("3.2.1"), [[[3], [2], [1]]])

    def test_parse_query_multiple(self):
        self.assertEqual(parse_query("1,2,3"), [[[1]], [[2]], [[3]]])
        self.assertEqual(parse_query("1.2,3.4"), [[[1], [2]], [[3], [4]]])

    def test_parse_query_range(self):
        self.assertEqual(parse_query("1..3"), [[list(range(1, 4))]])
        self.assertEqual(parse_query("1.2..4"), [[[1], list(range(2, 5))]])

    def test_parse_query_mixed(self):
        self.assertEqual(parse_query("1.2..3,4.1,5"), [[[1], [2, 3]], [[4], [1]], [[5]]])

    def test_parse_query_invalid_range(self):
        with self.assertRaisesRegex(ValueError, "End of range cannot be smaller than start."):
            parse_query("5..2")


class TestMarkdownNavigation(unittest.TestCase):
    """Tests for building the heading tree and finding sections."""

    @classmethod
    def setUpClass(cls):
        """Parse the sample markdown and build the heading tree once for all tests."""
        cls.source_code = SAMPLE_MARKDOWN
        md_parser = Parser()
        md_parser.set_language(Language(markdown_language()))
        tree = md_parser.parse(cls.source_code)
        cls.heading_tree = build_heading_tree(tree.root_node, cls.source_code)

    def test_build_heading_tree(self):
        """Verify the structure and content of the generated heading tree."""
        self.assertEqual(len(self.heading_tree), 2)

        # Section 1
        sec1 = self.heading_tree[0]
        self.assertEqual(sec1.level, 1)
        self.assertEqual(sec1.text, "Section 1")
        self.assertEqual(len(sec1.children), 2)

        # Section 1.1
        sec1_1 = sec1.children[0]
        self.assertEqual(sec1_1.level, 2)
        self.assertEqual(sec1_1.text, "Section 1.1")
        self.assertEqual(len(sec1_1.children), 0)

        # Section 1.2
        sec1_2 = sec1.children[1]
        self.assertEqual(sec1_2.level, 2)
        self.assertEqual(sec1_2.text, "Section 1.2")
        self.assertEqual(len(sec1_2.children), 1)

        # Section 1.2.1
        sec1_2_1 = sec1_2.children[0]
        self.assertEqual(sec1_2_1.level, 3)
        self.assertEqual(sec1_2_1.text, "Section 1.2.1")
        self.assertEqual(len(sec1_2_1.children), 0)

        # Section 2
        sec2 = self.heading_tree[1]
        self.assertEqual(sec2.level, 1)
        self.assertEqual(sec2.text, "Section 2")
        self.assertEqual(len(sec2.children), 2)

        # Verify section boundaries
        self.assertEqual(sec1.end_byte, sec2.start_byte)
        self.assertEqual(sec1_1.end_byte, sec1_2.start_byte)
        self.assertEqual(sec2.children[1].end_byte, len(self.source_code))

    def test_find_sections_single_path(self):
        """Test selecting a single, deeply nested section."""
        selectors = parse_query("1.2.1")
        sections = find_sections(self.heading_tree, selectors)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].text, "Section 1.2.1")

    def test_find_sections_multiple_paths(self):
        """Test selecting multiple, non-contiguous sections."""
        selectors = parse_query("1.1,2.2")
        sections = find_sections(self.heading_tree, selectors)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].text, "Section 1.1")
        self.assertEqual(sections[1].text, "Section 2.2")

    def test_find_sections_range(self):
        """Test selecting a range of sections."""
        selectors = parse_query("1.1..2")
        sections = find_sections(self.heading_tree, selectors)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].text, "Section 1.1")
        self.assertEqual(sections[1].text, "Section 1.2")

    def test_find_sections_complex_selection(self):
        """Test a mixed query with single paths and ranges."""
        selectors = parse_query("1.1..2,2.2")
        sections = find_sections(self.heading_tree, selectors)
        self.assertEqual(len(sections), 3)
        texts = {s.text for s in sections}
        self.assertEqual(texts, {"Section 1.1", "Section 1.2", "Section 2.2"})

    def test_find_sections_index_error(self):
        """Test that an out-of-bounds index raises an IndexError."""
        with self.assertRaisesRegex(IndexError, "Index 3 out of bounds"):
            find_sections(self.heading_tree, parse_query("3"))
        with self.assertRaisesRegex(IndexError, "Index 3 out of bounds"):
            find_sections(self.heading_tree, parse_query("1.3"))
        with self.assertRaisesRegex(IndexError, "Index 2 out of bounds"):
            find_sections(self.heading_tree, parse_query("1.2.2"))

    def test_merge_sections(self):
        """Test the merging logic for overlapping sections from main()."""
        def merge(sections):
            if not sections:
                return []
            sections.sort(key=lambda s: s.start_byte)
            merged = [sections[0]]
            for next_section in sections[1:]:
                if next_section.start_byte < merged[-1].end_byte:
                    merged[-1].end_byte = max(merged[-1].end_byte, next_section.end_byte)
                else:
                    merged.append(next_section)
            return merged

        # No overlap
        h1 = Heading(1, "h1", 0, 10, [])
        h2 = Heading(1, "h2", 10, 20, [])
        self.assertEqual(len(merge([h1, h2])), 2)

        # Overlap
        h1 = Heading(1, "h1", 0, 15, [])
        h2 = Heading(1, "h2", 10, 20, [])
        merged = merge([h1, h2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].start_byte, 0)
        self.assertEqual(merged[0].end_byte, 20)

        # Containment (order reversed to test sorting)
        h1 = Heading(1, "h1", 0, 30, [])
        h2 = Heading(1, "h2", 10, 20, [])
        merged = merge([h2, h1])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].start_byte, 0)
        self.assertEqual(merged[0].end_byte, 30)

        # Multiple merges
        h1 = Heading(1, "h1", 0, 10, [])
        h2 = Heading(1, "h2", 5, 15, [])    # overlaps h1
        h3 = Heading(1, "h3", 20, 30, [])   # separate
        h4 = Heading(1, "h4", 25, 35, [])   # overlaps h3
        merged = merge([h4, h1, h3, h2])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].start_byte, 0)
        self.assertEqual(merged[0].end_byte, 15)
        self.assertEqual(merged[1].start_byte, 20)
        self.assertEqual(merged[1].end_byte, 35)


if __name__ == '__main__':
    unittest.main()
