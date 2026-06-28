# Research & Technical Decisions: Notion Ingestion & Page Validation Fixes

## 1. Notion API Crawler Patterns

### Challenge
Notion represents documents as a tree of blocks. Reading a Notion page's full text requires recursively retrieving the child blocks of the page. If we only query `notion.pages.retrieve()`, we only get the page metadata (title, icon, properties), but not the page content.

### API Investigation
To get the actual contents:
1. Discover pages using `notion.search()` or query databases using `notion.databases.query()`.
2. Retrieve the top-level block children using `notion.blocks.children.list(block_id=page_id)`.
3. For blocks that have children (e.g. lists, callouts, child pages, columns), recursively fetch their child blocks using `notion.blocks.children.list(block_id=child_block_id)`.

### Selected Approach (Recursive Block Crawler)
We will implement a recursive Python crawler in `phase-2/backend/app/ingestion/notion.py`:
- **Discover phase**: Call `notion.search()` with a filter for `page` and `database` types. Save metadata for each found object into the `notion_objects` SQLite table.
- **Extract phase**: For each page, recursively call `notion.blocks.children.list()` up to a max depth of 5 (to prevent infinite loops or excessive API usage).
- **Compile/Format**: Translate each block type to Markdown equivalents:
  - `paragraph` -> raw text
  - `heading_1` -> `# Heading 1`
  - `heading_2` -> `## Heading 2`
  - `heading_3` -> `### Heading 3`
  - `bulleted_list_item` -> `- Item`
  - `numbered_list_item` -> `1. Item`
  - `code` -> ` ```lang\ncode\n``` `
  - `table` -> Markdown table syntax (requiring fetching row child blocks)
  - `callout` -> `> [!NOTE] text`
  - `child_page` -> recursively fetch it if shared, otherwise insert link to it.

---

## 2. Heading-Based Section Chunking

### Challenge
The current ingestion system splits raw content into small sentence clusters, losing document flow and structure. This produces shallow, disconnected knowledge pages.

### Selected Approach
Instead of sentence clustering, the Notion parser will split the compiled raw Markdown document by Markdown headings (`#`, `##`, `###`).
- Each section starts with a heading and continues until the next heading of equal or higher level.
- Sections that are too small (e.g. less than 100 characters) are merged with their parent/sibling section to maintain context.
- Sources are mapped down to block level (e.g. `notion://page/{page_id}#block-{block_id}`).

---

## 3. Strict Pre-Save Validation Gate

### Challenge
FastAPI and the synthesis loop currently save pages and commit them to Git even if the LLM output leaks prompts (e.g. `Input JSON:`, `Expected Output:`, `</output_format>`) or fails to generate YAML frontmatter.

### Selected Approach
Create `verify_page_shape(content: str) -> bool` in `validation.py`:
1. Check that the content starts with `---`.
2. Find the second `---` and attempt to parse the content between them as YAML.
3. Validate that the parsed dict contains:
   - `id` (string)
   - `title` (string)
   - `sources` (list of strings)
   - `propositions` (list of strings or dicts)
   - `synthesis_validation` (dict containing completeness, propositions_count, etc.)
4. Search the remainder of the markdown text for blacklisted substrings:
   - `Expected Output` (case-insensitive)
   - `Input JSON` (case-insensitive)
   - `</output_format>`
   - `Based on the provided source data` (and other common LLM helper preambles)
5. Reject writing to the file system or committing to Git if any check fails.
6. The `pipeline.py` compiler will intercept validation failures, catch the exception, update the `IngestionJob` database record to `failed`, and log a detailed warning via `structlog`.
