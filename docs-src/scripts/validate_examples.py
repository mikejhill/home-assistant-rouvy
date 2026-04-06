#!/usr/bin/env python3
"""Validate the command catalog and schemas.

Reads docs-src/commands.yaml and docs-src/schemas.yaml (single-file catalogs)
and validates:
  1. Command YAML has required fields
  2. Schemas are valid JSON Schema (draft 2020-12)
  3. Inline example outputs validate against their declared schemas

Usage:
    python docs-src/scripts/validate_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_FILE = REPO_ROOT / "docs-src" / "commands.yaml"
SCHEMAS_FILE = REPO_ROOT / "docs-src" / "schemas.yaml"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _to_json_schema(schema_def: dict) -> dict:
    """Wrap a schema definition with the JSON Schema meta-schema URI."""
    result = dict(schema_def)
    result.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    return result


def validate_schemas(schemas: dict[str, dict]) -> int:
    """Validate all schema definitions are well-formed JSON Schema."""
    errors = 0
    for name, schema_def in sorted(schemas.items()):
        try:
            full_schema = _to_json_schema(schema_def)
            jsonschema.Draft202012Validator.check_schema(full_schema)
            print(f"  ✓ Schema valid: {name}")
        except jsonschema.SchemaError as exc:
            print(f"  ✗ Schema invalid: {name}: {exc.message}", file=sys.stderr)
            errors += 1
    return errors


def validate_commands(commands: list[dict]) -> int:
    """Validate all commands have required fields."""
    required_keys = {"id", "command", "summary", "category"}
    errors = 0
    for cmd in commands:
        cmd_id = cmd.get("id", "<unknown>")
        missing = required_keys - set(cmd.keys())
        if missing:
            print(f"  ✗ Missing keys in {cmd_id}: {missing}", file=sys.stderr)
            errors += 1
        else:
            print(f"  ✓ Command valid: {cmd_id}")
    return errors


def validate_examples(commands: list[dict], schemas: dict[str, dict]) -> int:
    """Validate inline example outputs against their declared schemas."""
    errors = 0
    for cmd in commands:
        cmd_id = cmd.get("id", "<unknown>")
        schema_name = cmd.get("output", {}).get("schema")
        if not schema_name or schema_name not in schemas:
            continue

        full_schema = _to_json_schema(schemas[schema_name])
        validator = jsonschema.Draft202012Validator(full_schema)

        for i, example in enumerate(cmd.get("examples", [])):
            output_data = example.get("output")
            if output_data is None:
                continue

            label = f"{cmd_id}[{i}]"
            try:
                validator.validate(output_data)
                print(f"  ✓ Example valid: {label} against {schema_name}")
            except jsonschema.ValidationError as exc:
                print(
                    f"  ✗ Example invalid: {label}: {exc.message}",
                    file=sys.stderr,
                )
                errors += 1

    return errors


def main() -> None:
    """Run all validations."""
    for path in (COMMANDS_FILE, SCHEMAS_FILE):
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)

    catalog = _load_yaml(COMMANDS_FILE)
    schemas_doc = _load_yaml(SCHEMAS_FILE)
    commands: list[dict] = catalog.get("commands", [])
    schemas: dict[str, dict] = schemas_doc.get("schemas", {})

    total_errors = 0

    print("Validating command catalog...")
    total_errors += validate_commands(commands)

    print("\nValidating schemas...")
    total_errors += validate_schemas(schemas)

    print("\nValidating examples against schemas...")
    total_errors += validate_examples(commands, schemas)

    if total_errors:
        print(f"\n✗ {total_errors} validation error(s) found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✓ All validations passed.")


if __name__ == "__main__":
    main()
