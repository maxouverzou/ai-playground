#!/usr/bin/env python

import argparse
import sys
import re
from tree_sitter import Language, Parser
from tree_sitter_markdown import language as markdown_language

class Heading:
    def __init__(self, level, text, start_byte, end_byte, children=None):
        self.level = level
        self.text = text
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.children = children if children is not None else []

    def __repr__(self):
        return f"Heading(level={self.level}, text='{self.text}', children={len(self.children)})"

def find_all_headings(node):
    headings = []
    if node.type == 'atx_heading':
        headings.append(node)
    
    if node.type != 'atx_heading':
        for child in node.children:
            headings.extend(find_all_headings(child))
    return headings

def build_heading_tree(root_node, source_code):
    flat_headings = find_all_headings(root_node)
    
    headings = []
    for i, heading_node in enumerate(flat_headings):
        level = heading_node.children[0].text.count(b'#')
        content_node = heading_node.child_by_field_name('content')
        text = content_node.text.decode('utf8').strip() if content_node else ""
        
        start_byte = heading_node.start_byte
        end_byte = -1

        # Find the end of the section
        for j in range(i + 1, len(flat_headings)):
            next_heading_node = flat_headings[j]
            next_level = next_heading_node.children[0].text.count(b'#')
            if next_level <= level:
                end_byte = next_heading_node.start_byte
                break
        
        if end_byte == -1:
            end_byte = root_node.end_byte

        headings.append(Heading(level, text, start_byte, end_byte))

    # Nest headings
    if not headings:
        return []

    root = Heading(0, "root", 0, 0)
    stack = [root]

    for heading in headings:
        while stack and stack[-1].level >= heading.level:
            stack.pop()
        stack[-1].children.append(heading)
        stack.append(heading)

    return root.children

def parse_query(query_str):
    selectors = []
    parts = query_str.split(',')
    for part in parts:
        # Hack to handle ".." in ranges
        part = part.replace('..', '#RANGE#')
        indices = part.strip().split('.')
        selector_path = []
        for index in indices:
            index = index.replace('#RANGE#', '..')
            if '..' in index:
                start, end = map(int, index.split('..'))
                if end < start:
                    raise ValueError("End of range cannot be smaller than start.")
                selector_path.append(list(range(start, end + 1)))
            else:
                val = int(index)
                selector_path.append([val])
        selectors.append(selector_path)
    return selectors

def find_sections(tree, selectors):
    sections = []
    for selector in selectors:
        nodes_at_current_depth = tree 
        
        for i, path_part in enumerate(selector):
            is_last_part = (i == len(selector) - 1)
            
            selected_nodes_this_level = []
            for index in path_part:
                if index > len(nodes_at_current_depth):
                    raise IndexError(f"Index {index} out of bounds for query part {'.'.join(map(str, [p[0] for p in selector[:i+1]]))}")
                selected_nodes_this_level.append(nodes_at_current_depth[index - 1])

            if is_last_part:
                nodes_at_current_depth = selected_nodes_this_level
            else:
                nodes_for_next_depth = []
                for node in selected_nodes_this_level:
                    nodes_for_next_depth.extend(node.children)
                nodes_at_current_depth = nodes_for_next_depth
            
        sections.extend(nodes_at_current_depth)
    return sections


def main():
    """
    Main function to parse arguments and extract markdown sections.
    """
    parser = argparse.ArgumentParser(
        description="Extract sections from a markdown file based on a query."
    )
    parser.add_argument(
        "file_path",
        help="Path to the markdown file."
    )
    parser.add_argument(
        "query",
        help="Query to select sections (e.g., '1.3.2,1.3.4..5,2')."
    )

    args = parser.parse_args()

    try:
        with open(args.file_path, 'rb') as f:
            source_code = f.read()

        md_parser = Parser()
        md_parser.language = Language(markdown_language())
        tree = md_parser.parse(source_code)
        
        heading_tree = build_heading_tree(tree.root_node, source_code)
        selectors = parse_query(args.query)
        sections = find_sections(heading_tree, selectors)

        # Sort by start_byte and merge overlapping sections
        sections.sort(key=lambda s: s.start_byte)
        
        if not sections:
            return

        merged_sections = []
        current_section = sections[0]

        for next_section in sections[1:]:
            if next_section.start_byte < current_section.end_byte:
                # Merge
                current_section.end_byte = max(current_section.end_byte, next_section.end_byte)
            else:
                merged_sections.append(current_section)
                current_section = next_section
        merged_sections.append(current_section)

        for section in merged_sections:
            print(source_code[section.start_byte:section.end_byte].decode('utf8'), end='')

    except FileNotFoundError:
        print(f"Error: File not found at {args.file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
