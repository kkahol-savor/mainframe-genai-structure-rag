# COBOL Examples Repository

This repository contains a COBOL parser (repo_cobol_tree_parser.py) that extracts COBOL structure and call graph information from source files.

## Prerequisites

- Python 3.8+
- Install required Python package:
  ```
  pip install -r requirements.txt
  ```
- Note: tree-sitter-cobol is no longer available on PyPI or GitHub. You must provide a local copy of the COBOL grammar (e.g., a local "tree-sitter-cobol" folder) for the build step to work.

## Usage

1. Ensure a local copy of the COBOL grammar exists in a folder named "tree-sitter-cobol" (or update the build path accordingly in repo_cobol_tree_parser.py).
2. Run the parser:
   ```
   python repo_cobol_tree_parser.py
   ```
   The script will:
   - Check for the compiled COBOL language bundle (.so). If missing, it attempts to build it using the local COBOL grammar.
   - Parse all `.cbl` files in the `cobol_examples/` directory.
   - Generate JSON structure files in the `cobol_structures` folder.
   - Produce a repo-level call graph (filecall_graph.json).

## Troubleshooting

- If the build step fails, confirm that you have a valid local copy of the COBOL grammar.
- Ensure that the grammar’s structure is compatible with the tree-sitter build process.



