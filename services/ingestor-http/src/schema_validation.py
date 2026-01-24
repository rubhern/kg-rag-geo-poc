import json

from jsonschema import RefResolver
from jsonschema.validators import validator_for
from pathlib import Path


def validate_event(schema_path: Path, event: dict) -> None:
    if not schema_path.exists():
        raise SystemExit(f"Schema file not found: {schema_path}")

    schema = load_json(schema_path)

    # Base URI for resolving local $ref, allOf, etc.
    base_dir = schema_path.parent
    store: dict[str, dict] = {}

    # Load the envelope schema (required by ingest-file.v1.schema.json)
    envelope_path = base_dir / "envelope.v1.schema.json"
    if envelope_path.exists():
        envelope_schema = load_json(envelope_path)

        # Map by $id (https://example.local/...) so remote resolution is satisfied locally
        if "$id" in envelope_schema:
            store[envelope_schema["$id"]] = envelope_schema

        # Also map by file:// URI (useful if refs resolve to file URIs)
        store[envelope_path.resolve().as_uri()] = envelope_schema

    # Map the main schema too (same idea)
    if "$id" in schema:
        store[schema["$id"]] = schema
    store[schema_path.resolve().as_uri()] = schema

    # Base URI for resolving relative refs (envelope.v1.schema.json)
    base_uri = base_dir.resolve().as_uri() + "/"
    resolver = RefResolver(base_uri=base_uri, referrer=schema, store=store)

    Validator = validator_for(schema)
    validator = Validator(schema, resolver=resolver)

    errors = sorted(validator.iter_errors(event), key=lambda e: list(e.path))
    if errors:
        print("❌ Event validation failed:")
        for err in errors:
            where = ".".join([str(p) for p in err.path]) or "<root>"
            print(f" - {where}: {err.message}")
        raise SystemExit(2)

    print("✅ Event validated against JSON Schema")

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))