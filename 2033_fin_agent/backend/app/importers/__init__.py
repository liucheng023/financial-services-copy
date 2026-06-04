"""Importers translate upstream plugin content into Supabase rows.

Importers are read-only relative to the upstream filesystem. They MUST NOT
modify, create, or delete files under ``$UPSTREAM_PLUGINS_PATH``.
"""
