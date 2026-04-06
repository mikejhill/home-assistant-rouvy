#!/usr/bin/env python3
"""Generate CLI reference Markdown pages from the YAML command catalog.

Reads docs-src/commands.yaml and docs-src/schemas.yaml (single-file catalogs)
and generates Markdown pages in docs/reference/commands/ for MkDocs.

Usage:
    python docs-src/scripts/generate_docs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_FILE = REPO_ROOT / "docs-src" / "commands.yaml"
SCHEMAS_FILE = REPO_ROOT / "docs-src" / "schemas.yaml"
OUTPUT_DIR = REPO_ROOT / "docs" / "reference" / "commands"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_arguments_table(arguments: list[dict]) -> str:
    """Render an arguments table in Markdown."""
    if not arguments:
        return "_No arguments._"

    lines = [
        "| Argument | Type | Required | Description |",
        "| -------- | ---- | -------- | ----------- |",
    ]
    for arg in arguments:
        name = f"`{arg['name']}`"
        arg_type = arg.get("type", "string")
        required = "Yes" if arg.get("required") else "No"
        help_text = arg.get("help", "") or arg.get("description", "")
        if "choices" in arg:
            help_text += f" Choices: `{'`, `'.join(arg['choices'])}`"
        lines.append(f"| {name} | {arg_type} | {required} | {help_text} |")

    return "\n".join(lines)


def _render_schema_summary(schema: dict | None) -> str:
    """Render a summary of a JSON Schema's properties."""
    if not schema:
        return ""

    props = schema.get("properties", {})
    if not props:
        items = schema.get("items", {})
        if items:
            props = items.get("properties", {})
            if not props:
                return ""

    required_fields = set(schema.get("required", []))
    items_required = set(schema.get("items", {}).get("required", []))
    all_required = required_fields | items_required

    lines = [
        "| Field | Type | Required |",
        "| ----- | ---- | -------- |",
    ]
    for name, prop in props.items():
        type_str = _schema_type_str(prop)
        req = "Yes" if name in all_required else "No"
        lines.append(f"| `{name}` | {type_str} | {req} |")

    return "\n".join(lines)


def _schema_type_str(prop: dict) -> str:
    """Convert a JSON Schema property to a human-readable type string."""
    if "oneOf" in prop:
        types = [opt.get("type", "unknown") for opt in prop["oneOf"]]
        return " or ".join(types)
    if "$ref" in prop:
        ref = prop["$ref"]
        return ref.rsplit("/", 1)[-1] if "/" in ref else ref
    prop_type = prop.get("type", "unknown")
    if prop_type == "array":
        items = prop.get("items", {})
        item_type = items.get("type", "object")
        return f"array of {item_type}"
    return prop_type


def _render_inline_example(output_data: dict | list | None) -> str:
    """Render inline example data as a fenced JSON code block."""
    if output_data is None:
        return ""
    formatted = json.dumps(output_data, indent=2)
    return f"```json\n{formatted}\n```"


def generate_command_page(cmd: dict, schemas: dict[str, dict]) -> str:
    """Generate a Markdown page for a single CLI command."""
    cmd_id = cmd["id"]
    lines = [
        f"# {cmd_id}",
        "",
        cmd["summary"],
        "",
        "## Usage",
        "",
        f"```bash\n{cmd['command']}",
    ]

    for arg in cmd.get("arguments", []):
        name = arg["name"]
        if name.startswith("--"):
            if arg.get("required"):
                lines[-1] += f" {name} <value>"
            else:
                lines[-1] += f" [{name} <value>]"
        elif arg.get("required", True):
            lines[-1] += f" <{name}>"
        else:
            lines[-1] += f" [<{name}>]"

    lines.append("```")
    lines.append("")

    # Arguments
    arguments = cmd.get("arguments", [])
    if arguments:
        lines.append("## Arguments")
        lines.append("")
        lines.append(_render_arguments_table(arguments))
        lines.append("")

    # Examples
    examples = cmd.get("examples", [])
    if examples:
        lines.append("## Examples")
        lines.append("")
        for ex in examples:
            lines.append(f"### {ex['description']}")
            lines.append("")
            lines.append(f"```bash\n{ex['invocation']}\n```")
            lines.append("")
            output_data = ex.get("output")
            if output_data is not None:
                lines.append("#### Output")
                lines.append("")
                lines.append(_render_inline_example(output_data))
                lines.append("")

    # Output schema
    schema_name = cmd.get("output", {}).get("schema")
    if schema_name and schema_name in schemas:
        schema = schemas[schema_name]
        summary = _render_schema_summary(schema)
        if summary:
            lines.append("## Output Schema")
            lines.append("")
            title = schema.get("title", cmd_id)
            lines.append(f"### {title}")
            lines.append("")
            lines.append(summary)
            lines.append("")

    # Notes
    notes = cmd.get("notes", [])
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    # Stability
    stability = cmd.get("stability", "stable")
    lines.append("---")
    lines.append("")
    lines.append(f"*Stability: {stability}*")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Generate all command reference pages."""
    if not COMMANDS_FILE.exists():
        print(f"Error: {COMMANDS_FILE} not found", file=sys.stderr)
        sys.exit(1)
    if not SCHEMAS_FILE.exists():
        print(f"Error: {SCHEMAS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    catalog = _load_yaml(COMMANDS_FILE)
    schemas_doc = _load_yaml(SCHEMAS_FILE)
    schemas: dict[str, dict] = schemas_doc.get("schemas", {})
    commands: list[dict] = catalog.get("commands", [])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    for cmd in commands:
        page_content = generate_command_page(cmd, schemas)
        output_path = OUTPUT_DIR / f"{cmd['id']}.md"
        output_path.write_text(page_content, encoding="utf-8")
        generated += 1
        print(f"  Generated: {output_path.relative_to(REPO_ROOT)}")

    print(f"\nGenerated {generated} command reference pages.")


if __name__ == "__main__":
    main()
