"""
Summarizes a Java/SpringBoot codebase
"""

import os
import argparse
import sys
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

# CONFIGURATION
PROJECT_ROOT = "."  # Change this if running outside the root
OUTPUT_FILE = "codebase_summary.txt"

# File patterns to look for
PATTERNS = {
    "GRAPHQL_SCHEMA": {
        "ext": [".graphqls", ".graphql"],
        "keywords": [] # Keep all content for schemas
    },
    "JPA_ENTITIES": {
        "ext": [".java"],
        "keywords": ["@Entity", "@Table", "@Embeddable"]
    },
    "AMQP_LISTENERS": {
        "ext": [".java"],
        "keywords": ["@RabbitListener", "@KafkaListener", "AmqpConfig"]
    },
    "REPOSITORIES": {
        "ext": [".java"],
        "keywords": ["extends JpaRepository", "@Repository"]
    },
    "CONTROLLERS": {
        "ext": [".java"],
        "keywords": ["@Controller", "@RestController", " implements GraphQLQueryResolver", " implements GraphQLMutationResolver"]
    }
}

def is_relevant_file(content, valid_keywords):
    if not valid_keywords: return True # If no keywords defined, it's relevant (e.g. schemas)
    return any(keyword in content for keyword in valid_keywords)

# --- TREE-SITTER BASED CLEANER ---
JAVA_LANGUAGE = Language(tsjava.language())
parser = Parser(JAVA_LANGUAGE)

def clean_java_content(content):
    """
    Strips imports, comments, and method bodies from Java code using tree-sitter.
    """
    tree = parser.parse(bytes(content, "utf8"))
    root_node = tree.root_node
    
    content_bytes = bytes(content, "utf8")
    
    # These are the node types we want to fully remove
    nodes_to_remove = {"import_declaration", "package_declaration", "line_comment", "block_comment"}
    
    # We will collect the parts of the code we want to keep
    kept_parts = []
    last_end = 0

    def traverse(node):
        nonlocal last_end
        
        # 1. Remove entire nodes
        if node.type in nodes_to_remove:
            # Add content before this node
            kept_parts.append(content_bytes[last_end:node.start_byte])
            # Skip this node by updating the last_end position
            last_end = node.end_byte
            return # Don't traverse children of removed nodes

        # 2. Specifically remove method bodies (blocks)
        if node.type == 'method_declaration':
            # Find the body of the method, which is a 'block'
            body_node = next((child for child in node.children if child.type == 'block'), None)
            
            if body_node:
                # Keep everything up to the start of the method body
                kept_parts.append(content_bytes[last_end:body_node.start_byte])
                # Append a semicolon for a clean signature
                kept_parts.append(b';')
                # Skip the body
                last_end = body_node.end_byte
                
                # We've handled this node and its relevant children, so we can stop traversing this branch
                return

        # 3. For any other node, continue traversing its children
        for child in node.children:
            traverse(child)

    traverse(root_node)
    
    # Add any remaining content after the last handled node
    kept_parts.append(content_bytes[last_end:])

    # Join the kept parts and decode back to a string
    cleaned_content = b"".join(kept_parts).decode('utf-8')
    
    # Final cleanup for excessive newlines
    return "\n".join(line for line in cleaned_content.split('\n') if line.strip())


def write_output(out_stream, data):
    out_stream.write("PROJECT CODEBASE SUMMARY\n")
    out_stream.write("========================\n\n")

    order = ["GRAPHQL_SCHEMA", "JPA_ENTITIES", "AMQP_LISTENERS", "REPOSITORIES", "CONTROLLERS"]

    for category in order:
        files_found = data.get(category, [])
        out_stream.write(f"=== SECTION: {category} ({len(files_found)} files) ===\n")
        if not files_found:
            out_stream.write("(No files found for this section)\n")
        for entry in files_found:
            out_stream.write(entry)
        out_stream.write("\n\n")

def scan_project(project_root, output_file):
    summary_data = {key: [] for key in PATTERNS.keys()}

    print(f"Scanning {project_root}...")

    for root, dirs, files in os.walk(project_root):
        # Exclude common build and dependency directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'target', 'build', 'node_modules', '.venv']]
        
        for file in files:
            file_path = os.path.join(root, file)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, IOError):
                continue # Skip binary or unreadable files

            # Categorize the file
            for category, criteria in PATTERNS.items():
                if any(file.endswith(ext) for ext in criteria["ext"]):
                    if is_relevant_file(content, criteria["keywords"]):

                        # Clean content based on type
                        if file.endswith(".java"):
                            final_content = clean_java_content(content)
                        else:
                            final_content = content

                        entry = f"\n--- START FILE: {file} ({category}) ---\n{final_content}\n--- END FILE ---\n"
                        summary_data[category].append(entry)
                        # Break loop so we don't duplicate
                        break

    # Output the summary
    if output_file == "-":
        write_output(sys.stdout, summary_data)
        print(f"Success! Context generated to stdout.")
    else:
        with open(output_file, 'w', encoding='utf-8') as out:
            write_output(out, summary_data)
        print(f"Success! Context generated at: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Summarizes a Java/SpringBoot codebase.")
    arg_parser.add_argument("--project_root", type=str, default=".",
                        help="Path to the project root directory (default: .)")
    arg_parser.add_argument("--output_file", type=str, default="-",
                        help="Name of the output summary file (default: -, which means stdout)")
    args = arg_parser.parse_args()
    scan_project(args.project_root, args.output_file)
