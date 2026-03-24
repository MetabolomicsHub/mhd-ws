"""Build dataset documents for legacy MHD datasets."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mhd_ws.infrastructure.search.indexing.facets import (
    ASSAY_FACET_REF_KEYS,
    FACET_KEYS,
    SEARCH_FACET_KEYS,
    route_characteristic_to_facet,
)
from mhd_ws.infrastructure.search.indexing.graph_utils import (
    build_rel_index,
    choose_study_id,
    cv_value_label_and_accession,
    get_graph_parts,
    node_name,
    rel_sources,
    rel_targets,
)
from mhd_ws.infrastructure.search.indexing.utils import (
    dedup_preserve_order,
    dedup_sorted_strings,
    strip_html,
)

FILE_NODE_TYPES = {
    "metadata-file",
    "raw-data-file",
    "derived-data-file",
    "result-file",
    "supplementary-file",
}

ROLE_ALIASES = {
    "has-contributor": "contributor",
    "has-principal-investigator": "principal-investigator",
    "principal-investigator-of": "principal-investigator",
    "submitted-by": "submitter",
    "submits": "submitter",
}

# Maps known type_accessions to their instrument bucket when type_name is absent/ambiguous
INSTRUMENT_ACCESSION_BUCKET: dict[str, str] = {
    "MSIO:0000171": "ms_instruments",
}
STUDY_ORG_REL_NAMES = {"funds", "funded-by"}
MASS_ANALYZER_KEYWORDS = ("mass analyzer", "mass analyser")
SAMPLE_NODE_TYPES = {"sample"}


def detect_profile(mhd: dict[str, Any]) -> str:
    """Detect the MHD profile from the document profile_uri."""
    profile_uri = mhd.get("profile_uri") or ""
    if "ms-profile" in profile_uri:
        return "ms"
    return "legacy"


def _flatten_str_or_kv_list(items: list | None) -> list[str]:
    """Flatten a list of strings or KeyValue dicts to a list of strings."""
    result: list[str] = []
    for item in items or []:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            v = item.get("value") or item.get("key") or item.get("name")
            if v and isinstance(v, str) and v.strip():
                result.append(v.strip())
    return result


def role_labels(rel_name: str | None) -> list[str]:
    """Return relationship and any normalized role aliases."""
    if not rel_name:
        return []
    labels = [rel_name]
    alias = ROLE_ALIASES.get(rel_name)
    if alias:
        labels.append(alias)
    return labels


def add_person_org(person_entry: dict[str, Any], org: dict[str, Any]) -> None:
    """Add an organization reference (id + name) to a person's organizations list."""
    org_id = org.get("id")
    org_name = node_name(org)
    if not org_id and not org_name:
        return
    person_entry["organizations"].append({"id": org_id, "name": org_name})


def dedup_org_refs(orgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """De-duplicate organization refs by (id, name)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for org in orgs:
        key = ((org.get("id") or "").strip(), (org.get("name") or "").strip())
        if key == ("", ""):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(org)
    return out


def normalize_extension(ext: str | None) -> str | None:
    """Normalize an extension to lowercase with a leading dot."""
    if not ext or not isinstance(ext, str):
        return None
    ext = ext.strip()
    if not ext:
        return None
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext.lower()


def extension_from_text(text: str | None) -> str | None:
    """Extract a file extension from a path or URL."""
    if not text or not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    if "://" in raw:
        raw = urlparse(raw).path
    name = Path(raw).name
    if "." not in name:
        return None
    suffixes = Path(name).suffixes
    if not suffixes:
        return None
    ext = suffixes[-1]
    if ext.lower() in {".gz", ".zip", ".bz2", ".xz"} and len(suffixes) >= 2:
        ext = "".join(suffixes[-2:])
    return normalize_extension(ext)


def detect_file_extension(node: dict[str, Any]) -> str | None:
    """Find the best available file extension for a file node."""
    ext = normalize_extension(node.get("extension"))
    if ext:
        return ext
    ext = extension_from_text(node.get("name"))
    if ext:
        return ext
    for url in node.get("url_list") or []:
        ext = extension_from_text(url)
        if ext:
            return ext
    return None


def _collect_strings(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        v = value.strip()
        if v:
            out.append(v)
        return
    if isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
        return
    if isinstance(value, list):
        for v in value:
            _collect_strings(v, out)


# Relationship names from study node → descriptor (used as the `relationship` field value)
_STUDY_DESCRIPTOR_RELS = ("has-submitter-keyword", "has-repository-keyword")

# (node_type, ref_field) → relationship label stored in the descriptor entry
_NODE_REF_DESCRIPTOR_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("assay", "assay_type_ref", "assay.assay_type"),
    ("assay", "omics_type_ref", "assay.omics_type"),
    ("assay", "measurement_type_ref", "assay.measurement_type"),
    ("assay", "technology_type_ref", "assay.technology_type"),
    ("metadata-file", "format_ref", "metadata-file.format"),
    ("raw-data-file", "format_ref", "raw-data-file.format"),
    ("result-file", "format_ref", "result-file.format"),
)


def _collect_descriptors(
    doc: dict[str, Any],
    node_by_id: dict[str, Any],
    relidx: Any,
    study_id: str,
    assay_nodes: list[dict[str, Any]],
) -> None:
    """Populate doc['descriptors'] from all known relationship/ref sources."""
    seen: set[tuple[str, str]] = set()  # (descriptor_id, relationship)

    def _add(descriptor_node: dict[str, Any], relationship: str) -> None:
        did = descriptor_node.get("id", "")
        key = (did, relationship)
        if key in seen:
            return
        seen.add(key)
        name = descriptor_node.get("name")
        if not name:
            return
        doc["descriptors"].append({
            "name": name,
            "source": descriptor_node.get("source"),
            "accession": descriptor_node.get("accession"),
            "relationship": relationship,
        })

    # Study-level keyword relationships
    for rel_name in _STUDY_DESCRIPTOR_RELS:
        for target_id in rel_targets(relidx, study_id, rel_name):
            node = node_by_id.get(target_id)
            if node and node.get("type") == "descriptor":
                _add(node, f"study.{rel_name}")

    # Embedded ref fields on assay and file nodes
    nodes_by_type: dict[str, list[dict[str, Any]]] = {}
    for node in node_by_id.values():
        ntype = node.get("type", "")
        nodes_by_type.setdefault(ntype, []).append(node)

    for node_type, ref_field, rel_label in _NODE_REF_DESCRIPTOR_SOURCES:
        if node_type == "assay":
            source_nodes = assay_nodes
        else:
            source_nodes = nodes_by_type.get(node_type, [])
        for node in source_nodes:
            ref_id = node.get(ref_field)
            if not ref_id:
                continue
            desc = node_by_id.get(ref_id)
            if desc and desc.get("type") == "descriptor":
                _add(desc, rel_label)


def build_legacy_dataset_doc(  # noqa: C901, PLR0912, PLR0915
    mhd: dict[str, Any], indexed_iso: str
) -> dict[str, Any]:
    """Build a legacy dataset document suitable for ES indexing."""
    node_by_id, relationships = get_graph_parts(mhd)
    relidx = build_rel_index(relationships)

    study_id = choose_study_id(mhd, node_by_id)
    study = node_by_id[study_id]

    repo_name = mhd.get("repository_name")
    repo_id = mhd.get("repository_identifier")
    repo_rev = mhd.get("repository_revision", 1)
    profile = detect_profile(mhd)

    doc: dict[str, Any] = {
        "id": f"{profile}::{repo_id}",
        "profile": profile,
        "repository": {
            "name": repo_name,
            "identifier": repo_id,
            "revision": repo_rev,
        },
        "study": {
            "title": study.get("title"),
            "description": study.get("description"),
            "license": study.get("license"),
            "dataset_urls": study.get("dataset_url_list", []),
        },
        "dates": {
            "submission": study.get("submission_date"),
            "public_release": study.get("public_release_date"),
            "indexed": indexed_iso,
        },
        "data_provider": {},
        "facets": {k: [] for k in FACET_KEYS},
        "assays": {"count": 0},
        "samples": {"count": 0},
        "counts": {
            "assays": 0,
            "samples": 0,
            "sample_runs": 0,
            "subjects": 0,
            "specimens": 0,
        },
        "files": {
            "metadata": {"count": 0},
            "raw": {"count": 0},
            "derived": {"count": 0},
            "result": {"count": 0},
            "supplementary": {"count": 0},
            "extensions": [],
        },
        "people": [],
        "organizations": [],
        "parameters": [],
        "parameter_groups": [],
        "characteristic_groups": [],
        "descriptors": [],
        "ms_instruments": [],
        "chromatography_instruments": [],
        "other_instruments": [],
        "mass_analyzers": [],
        "factors": [],
        "project": {},
        "protocols": [],
        "publications": [],
        "specimens": [],
        "search_text": "",
        "debug": {
            "node_type_counts": {},
            "relationship_counts": {},
        },
    }

    # MS-specific top-level fields
    revision_datetime = mhd.get("repository_revision_datetime")
    if revision_datetime:
        doc["repository"]["revision_datetime"] = revision_datetime

    change_log = mhd.get("change_log")
    if change_log:
        doc["change_log"] = change_log

    # MS-specific study fields
    mhd_identifier = study.get("mhd_identifier") or mhd.get("mhd_identifier")
    if mhd_identifier:
        doc["study"]["mhd_identifier"] = mhd_identifier

    grant_identifiers = _flatten_str_or_kv_list(study.get("grant_identifier_list"))
    if grant_identifiers:
        doc["study"]["grant_identifiers"] = grant_identifiers

    related_datasets = _flatten_str_or_kv_list(study.get("related_dataset_list"))
    if related_datasets:
        doc["study"]["related_datasets"] = related_datasets

    # Debug counts
    doc["debug"]["node_type_counts"] = dict(
        Counter([n.get("type") for n in node_by_id.values()])
    )
    doc["debug"]["relationship_counts"] = dict(
        Counter(
            [
                r.get("relationship_name")
                for r in relationships
                if r.get("type") == "relationship"
            ]
        )
    )

    # Data provider (study.created_by_ref or data-provider --provides--> study)
    provider_id = study.get("created_by_ref")
    if not provider_id:
        provider_ids = rel_sources(relidx, study_id, "provides")
        if provider_ids:
            provider_id = provider_ids[0]
    provider_node = node_by_id.get(provider_id) if provider_id else None
    if provider_node:
        provider_value = provider_node.get("value") or provider_node.get("name")
        provider_entry = {
            "value": provider_value,
            "accession": provider_node.get("accession"),
            "source": provider_node.get("source"),
        }
        if any(provider_entry.values()):
            doc["data_provider"] = provider_entry

    # People: any study <-> person relationship; preserve relationship roles
    people_by_id: dict[str, dict[str, Any]] = {}
    for rel in relationships:
        if rel.get("type") != "relationship":
            continue
        rel_name = rel.get("relationship_name")
        src = rel.get("source_ref")
        tgt = rel.get("target_ref")
        if not src or not tgt or not rel_name:
            continue
        if src == study_id and node_by_id.get(tgt, {}).get("type") == "person":
            pid = tgt
        elif tgt == study_id and node_by_id.get(src, {}).get("type") == "person":
            pid = src
        else:
            continue

        person = node_by_id.get(pid, {})
        person_entry: dict[str, Any] = {
            "full_name": person.get("full_name") or person.get("name"),
            "emails": person.get("email_list") or person.get("emails") or [],
            "organizations": [],
            "roles": [],
        }
        if person.get("orcid"):
            person_entry["orcid"] = person["orcid"]
        entry = people_by_id.setdefault(pid, person_entry)
        entry["roles"].extend(role_labels(rel_name))

    def add_org_entry(
        org: dict[str, Any], role: str, direction: str, seen: set
    ) -> None:
        org_name = node_name(org)
        if not org_name:
            return
        entry = {
            "id": org.get("id"),
            "name": org_name,
            "address": org.get("address"),
            "role": role,
            "direction": direction,
        }
        if org.get("department"):
            entry["department"] = org["department"]
        if org.get("unit"):
            entry["unit"] = org["unit"]
        key = (
            (entry.get("id") or "").strip(),
            (entry.get("name") or "").strip(),
            (entry.get("address") or "").strip(),
            (entry.get("role") or "").strip(),
            (entry.get("direction") or "").strip(),
        )
        if key in seen:
            return
        seen.add(key)
        doc["organizations"].append(entry)

    seen_orgs: set[tuple[str, ...]] = set()

    # People -> organizations (affiliations, etc.), promote to dataset orgs
    for rel in relationships:
        if rel.get("type") != "relationship":
            continue
        src = rel.get("source_ref")
        tgt = rel.get("target_ref")
        if not src or not tgt:
            continue
        if (
            src in people_by_id
            and node_by_id.get(tgt, {}).get("type") == "organization"
        ):
            org = node_by_id.get(tgt, {})
            add_person_org(people_by_id[src], org)
            add_org_entry(org, "affiliation", "via-person", seen_orgs)
        elif (
            tgt in people_by_id
            and node_by_id.get(src, {}).get("type") == "organization"
        ):
            org = node_by_id.get(src, {})
            add_person_org(people_by_id[tgt], org)
            add_org_entry(org, "affiliation", "via-person", seen_orgs)

    for entry in people_by_id.values():
        entry["organizations"] = dedup_org_refs(entry["organizations"])
        entry["roles"] = dedup_preserve_order(entry["roles"])
    doc["people"] = list(people_by_id.values())

    # Organizations: capture study <-> organization relationships (funding only)
    for rel in relationships:
        if rel.get("type") != "relationship":
            continue
        rel_name = rel.get("relationship_name")
        if rel_name not in STUDY_ORG_REL_NAMES:
            continue
        src = rel.get("source_ref")
        tgt = rel.get("target_ref")
        if not src or not tgt or not rel_name:
            continue
        if src == study_id and node_by_id.get(tgt, {}).get("type") == "organization":
            org = node_by_id.get(tgt, {})
            direction = "outbound"
        elif tgt == study_id and node_by_id.get(src, {}).get("type") == "organization":
            org = node_by_id.get(src, {})
            direction = "inbound"
        else:
            continue
        add_org_entry(org, rel_name, direction, seen_orgs)

    # Project: project --has-study--> study ; project --managed-by--> organization
    for proj_id in rel_sources(relidx, study_id, "has-study"):
        proj = node_by_id.get(proj_id, {})
        managed_by = []
        for org_id in rel_targets(relidx, proj_id, "managed-by"):
            org = node_by_id.get(org_id, {})
            oname = org.get("name")
            if oname:
                managed_by.append(oname)
        doc["project"] = {
            "title": proj.get("title") or proj.get("name"),
            "managed_by": dedup_preserve_order(managed_by),
        }

    # Protocols: study --has-protocol--> protocol
    protocol_ids = set(rel_targets(relidx, study_id, "has-protocol"))
    protocol_ids.update(study.get("protocol_refs") or [])
    seen_protocols: set[tuple[str, ...]] = set()
    for pid in protocol_ids:
        p = node_by_id.get(pid, {})
        if p.get("type") != "protocol":
            continue
        protocol_type = None
        protocol_type_accession = None
        type_ref = p.get("protocol_type_ref")
        if type_ref and type_ref in node_by_id:
            type_node = node_by_id[type_ref]
            protocol_type = node_name(type_node)
            protocol_type_accession = type_node.get("accession")

        entry = {
            "name": p.get("name"),
            "description": p.get("description"),
            "protocol_type": protocol_type,
            "protocol_type_accession": protocol_type_accession,
        }
        key = (
            (entry.get("name") or "").strip(),
            (entry.get("protocol_type") or "").strip(),
            (entry.get("protocol_type_accession") or "").strip(),
        )
        if key in seen_protocols:
            continue
        seen_protocols.add(key)
        doc["protocols"].append(entry)
        if protocol_type:
            doc["facets"]["protocol_types"].append(protocol_type)

    # Publications: study --has-publication--> publication
    publication_ids = set(rel_targets(relidx, study_id, "has-publication"))
    seen_publications: set[tuple[str, ...]] = set()
    for pub_id in publication_ids:
        pub = node_by_id.get(pub_id, {})
        if pub.get("type") != "publication":
            continue
        entry = {"title": pub.get("title"), "doi": pub.get("doi")}
        if pub.get("pubmed_id"):
            entry["pubmed_id"] = pub["pubmed_id"]
        key = ((entry.get("title") or "").strip(), (entry.get("doi") or "").strip())
        if key in seen_publications:
            continue
        seen_publications.add(key)
        doc["publications"].append(entry)

    # Assay facets: assay refs point to descriptor nodes
    assay_nodes = [n for n in node_by_id.values() if n.get("type") == "assay"]
    doc["assays"]["count"] = len(assay_nodes)
    doc["samples"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") in SAMPLE_NODE_TYPES
    )
    doc["counts"]["assays"] = doc["assays"]["count"]
    doc["counts"]["samples"] = doc["samples"]["count"]
    doc["counts"]["sample_runs"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "sample-run"
    )
    doc["counts"]["subjects"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "subject"
    )
    doc["counts"]["specimens"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "specimen"
    )
    for a in assay_nodes:
        for facet_key, ref_key in ASSAY_FACET_REF_KEYS:
            ref = a.get(ref_key)
            if ref and ref in node_by_id:
                nm = node_name(node_by_id[ref])
                if nm:
                    doc["facets"][facet_key].append(nm)

    # Characteristic definitions
    char_def_ids = rel_targets(relidx, study_id, "has-characteristic-definition")
    if not char_def_ids:
        char_def_ids = [
            nid
            for nid, n in node_by_id.items()
            if n.get("type") == "characteristic-definition"
        ]

    for cd_id in char_def_ids:
        cd = node_by_id.get(cd_id, {})
        nm = cd.get("name")
        if nm:
            doc["facets"]["characteristic_types"].append(nm)

    # Characteristic values
    char_entries: list[dict[str, str]] = []
    for cv_node in [
        n
        for n in node_by_id.values()
        if (n.get("type") or "").endswith("characteristic-value")
    ]:
        cv_id = cv_node.get("id")
        if not cv_id:
            continue

        def_ids = rel_targets(relidx, cv_id, "instance-of")
        if not def_ids:
            def_ids = rel_sources(relidx, cv_id, "has-instance")

        label, accession = cv_value_label_and_accession(cv_node)

        type_names: list[str] = []
        for def_id in def_ids:
            cd = node_by_id.get(def_id, {})
            char_type_ref = cd.get("characteristic_type_ref")
            char_type_node = node_by_id.get(char_type_ref) if char_type_ref else None
            char_type_name = (
                char_type_node.get("name") if char_type_node else None
            ) or cd.get("name")
            if char_type_name:
                type_names.append(char_type_name)

        if not type_names:
            type_ids = rel_targets(relidx, cv_id, "has-type")
            for type_id in type_ids:
                type_node = node_by_id.get(type_id, {})
                type_name = type_node.get("name")
                if type_name:
                    type_names.append(type_name)

        for char_type_name in type_names:
            type_name_lc = char_type_name.strip().lower()
            if label and type_name_lc:
                char_entries.append({"type_name": type_name_lc, "value": label})

            bucket = route_characteristic_to_facet(char_type_name)
            if not bucket:
                continue

            if bucket == "organisms":
                if label:
                    doc["facets"]["organisms"].append(label)
                if accession:
                    doc["facets"]["organism_accessions"].append(accession)
            elif bucket == "diseases":
                if label:
                    doc["facets"]["diseases"].append(label)
                if accession:
                    doc["facets"]["disease_accessions"].append(accession)
            elif bucket == "tissues":
                if label:
                    doc["facets"]["tissues"].append(label)
            elif bucket == "sample_types":
                if label:
                    doc["facets"]["sample_types"].append(label)

    # characteristic_kv and characteristic_values flat facets (all pairs)
    char_kv_seen: set[str] = set()
    char_val_seen: set[str] = set()
    for entry in char_entries:
        type_name = entry["type_name"]
        value = entry["value"]
        kv = f"{type_name}::{value}"
        if kv not in char_kv_seen:
            char_kv_seen.add(kv)
            doc["facets"]["characteristic_kv"].append(kv)
        if value not in char_val_seen:
            char_val_seen.add(value)
            doc["facets"]["characteristic_values"].append(value)

    # characteristic_groups: nested {type_name, values[], kv[]} for correlated search and facet
    char_groups: dict[str, list[str]] = {}
    for entry in char_entries:
        type_name = entry["type_name"]
        value = entry["value"]
        if type_name not in char_groups:
            char_groups[type_name] = []
        if value not in char_groups[type_name]:
            char_groups[type_name].append(value)
    doc["characteristic_groups"] = [
        {
            "type_name": t,
            "values": vs,
            "kv": [f"{t}::{v}" for v in vs],
        }
        for t, vs in char_groups.items()
    ]

    # Factor values
    factor_def_ids = rel_targets(relidx, study_id, "has-factor-definition")
    if not factor_def_ids:
        factor_def_ids = [
            nid
            for nid, n in node_by_id.items()
            if n.get("type") == "factor-definition"
        ]
    factor_def_id_set = set(factor_def_ids)
    factor_entries: list[dict[str, Any]] = []
    seen_factors: set[tuple[str, ...]] = set()

    for fv_node in [
        n
        for n in node_by_id.values()
        if (n.get("type") or "").endswith("factor-value")
    ]:
        fv_id = fv_node.get("id")
        if not fv_id:
            continue

        def_ids = rel_targets(relidx, fv_id, "instance-of")
        if not def_ids:
            def_ids = rel_sources(relidx, fv_id, "has-instance")
        if factor_def_id_set:
            def_ids = [def_id for def_id in def_ids if def_id in factor_def_id_set]
            if not def_ids:
                continue

        type_names = []
        type_nodes_by_id: dict[str, dict[str, Any]] = {}
        for def_id in def_ids:
            fd = node_by_id.get(def_id, {})
            type_ref = fd.get("factor_type_ref")
            type_node = node_by_id.get(type_ref) if type_ref else None
            type_name = (type_node.get("name") if type_node else None) or fd.get(
                "name"
            )
            if type_name:
                type_names.append(type_name)
            if type_node and type_ref:
                type_nodes_by_id[type_ref] = type_node

        if not type_names:
            type_ids = rel_targets(relidx, fv_id, "has-type")
            if not type_ids:
                type_ids = rel_sources(relidx, fv_id, "type-of")
            for type_id in type_ids:
                type_node = node_by_id.get(type_id, {})
                type_name = type_node.get("name")
                if type_name:
                    type_names.append(type_name)
                if type_node and type_id:
                    type_nodes_by_id[type_id] = type_node

        label, accession = cv_value_label_and_accession(fv_node)
        for type_name in type_names:
            bucket = route_characteristic_to_facet(type_name)
            if not bucket:
                continue

            if bucket == "organisms":
                if label:
                    doc["facets"]["organisms"].append(label)
                if accession:
                    doc["facets"]["organism_accessions"].append(accession)
            elif bucket == "diseases":
                if label:
                    doc["facets"]["diseases"].append(label)
                if accession:
                    doc["facets"]["disease_accessions"].append(accession)
            elif bucket == "tissues":
                if label:
                    doc["facets"]["tissues"].append(label)
            elif bucket == "sample_types":
                if label:
                    doc["facets"]["sample_types"].append(label)

        # Build general factor entries
        value_source = fv_node.get("source")
        type_infos: list[tuple[str | None, str | None, str | None]] = []
        for type_node in type_nodes_by_id.values():
            type_infos.append(
                (node_name(type_node), type_node.get("accession"), type_node.get("source"))
            )
        if not type_infos:
            type_infos.append((None, None, None))

        if def_ids:
            def_nodes = [node_by_id.get(def_id, {}) for def_id in def_ids]
        else:
            def_nodes = [None]

        for def_node in def_nodes:
            def_name = def_node.get("name") if def_node else None
            for type_name, type_accession, type_source in type_infos:
                final_type_name = type_name or def_name
                entry = {
                    "definition_name": def_name,
                    "type_name": final_type_name,
                    "type_accession": type_accession,
                    "type_source": type_source,
                    "value": label,
                    "value_accession": accession,
                    "value_source": value_source,
                }
                if not any(entry.values()):
                    continue
                key = (
                    (entry.get("definition_name") or "").strip(),
                    (entry.get("type_name") or "").strip(),
                    (entry.get("type_accession") or "").strip(),
                    (entry.get("type_source") or "").strip(),
                    (entry.get("value") or "").strip(),
                    (entry.get("value_accession") or "").strip(),
                    (entry.get("value_source") or "").strip(),
                )
                if key in seen_factors:
                    continue
                seen_factors.add(key)
                factor_entries.append(entry)

    doc["factors"] = factor_entries

    # Parameters: parameter-value nodes + their parameter types/definitions
    param_entries: list[dict[str, Any]] = []
    seen_params: set[tuple[str, ...]] = set()
    for pv_node in [
        n
        for n in node_by_id.values()
        if (n.get("type") or "").endswith("parameter-value")
    ]:
        pv_id = pv_node.get("id")
        if not pv_id:
            continue

        value_label, value_accession = cv_value_label_and_accession(pv_node)
        value_source = pv_node.get("source")

        type_nodes: list[dict[str, Any]] = []
        type_ids = rel_targets(relidx, pv_id, "has-type")
        if not type_ids:
            type_ids = rel_sources(relidx, pv_id, "type-of")
        for type_id in type_ids:
            type_node = node_by_id.get(type_id)
            if type_node:
                type_nodes.append(type_node)

        def_ids = rel_targets(relidx, pv_id, "instance-of")
        if not def_ids:
            def_ids = rel_sources(relidx, pv_id, "has-instance")

        for def_id in def_ids:
            def_node = node_by_id.get(def_id, {})
            type_ref = def_node.get("parameter_type_ref")
            if type_ref and type_ref in node_by_id:
                type_nodes.append(node_by_id[type_ref])

        type_infos: list[tuple[str | None, str | None, str | None]] = []
        for type_node in type_nodes:
            type_name = node_name(type_node)
            type_infos.append(
                (type_name, type_node.get("accession"), type_node.get("source"))
            )

        if not type_infos and def_ids:
            for def_id in def_ids:
                def_node = node_by_id.get(def_id, {})
                type_name = def_node.get("name")
                if type_name:
                    type_infos.append((type_name, None, None))

        if not type_infos:
            type_infos.append((None, None, None))

        for type_name, type_accession, type_source in type_infos:
            entry = {
                "type_name": type_name,
                "type_accession": type_accession,
                "type_source": type_source,
                "value": value_label,
                "value_accession": value_accession,
                "value_source": value_source,
            }
            if not any(entry.values()):
                continue
            key = (
                (entry.get("type_name") or "").strip(),
                (entry.get("type_accession") or "").strip(),
                (entry.get("type_source") or "").strip(),
                (entry.get("value") or "").strip(),
                (entry.get("value_accession") or "").strip(),
                (entry.get("value_source") or "").strip(),
            )
            if key in seen_params:
                continue
            seen_params.add(key)
            param_entries.append(entry)

            if type_name:
                doc["facets"]["parameter_types"].append(type_name)
            if value_label:
                doc["facets"]["parameter_values"].append(value_label)

            type_name_lc = (type_name or "").lower()
            is_instrument = "instrument" in type_name_lc or (
                type_accession or ""
            ) in INSTRUMENT_ACCESSION_BUCKET
            if is_instrument and value_label:
                inst_entry = {
                    "name": value_label,
                    "type_name": type_name,
                    "type_accession": type_accession,
                    "type_source": type_source,
                }
                if type_name_lc == "mass spectrometry instrument":
                    bucket = "ms_instruments"
                elif type_name_lc == "chromatography instrument":
                    bucket = "chromatography_instruments"
                else:
                    bucket = INSTRUMENT_ACCESSION_BUCKET.get(
                        type_accession or "", "other_instruments"
                    )
                if inst_entry not in doc[bucket]:
                    doc[bucket].append(inst_entry)

            is_mass_analyzer = any(k in type_name_lc for k in MASS_ANALYZER_KEYWORDS)
            if is_mass_analyzer and value_label:
                analyzer_entry = {
                    "name": value_label,
                    "type_name": type_name,
                    "type_accession": type_accession,
                    "type_source": type_source,
                }
                if analyzer_entry not in doc["mass_analyzers"]:
                    doc["mass_analyzers"].append(analyzer_entry)

    doc["parameters"] = param_entries

    # parameter_kv: flat "type_name::value" pairs for faceting/filtering
    kv_seen: set[str] = set()
    for entry in param_entries:
        type_name = entry.get("type_name")
        value = entry.get("value")
        if type_name and value:
            kv = f"{type_name}::{value}"
            if kv not in kv_seen:
                kv_seen.add(kv)
                doc["facets"]["parameter_kv"].append(kv)

    # parameter_groups: nested {type_name, values[]} for per-type drill-down
    groups: dict[str, list[str]] = {}
    for entry in param_entries:
        type_name = entry.get("type_name")
        value = entry.get("value")
        if type_name and value:
            if type_name not in groups:
                groups[type_name] = []
            if value not in groups[type_name]:
                groups[type_name].append(value)
    doc["parameter_groups"] = [
        {"type_name": t, "values": vs} for t, vs in groups.items()
    ]

    # Descriptors: collect all descriptor nodes reachable via known relationships/refs
    _collect_descriptors(doc, node_by_id, relidx, study_id, assay_nodes)

    # File counts
    doc["files"]["metadata"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "metadata-file"
    )
    doc["files"]["raw"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "raw-data-file"
    )
    doc["files"]["derived"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "derived-data-file"
    )
    doc["files"]["result"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "result-file"
    )
    doc["files"]["supplementary"]["count"] = sum(
        1 for n in node_by_id.values() if n.get("type") == "supplementary-file"
    )

    # Specimens (ms profile)
    specimen_nodes = [n for n in node_by_id.values() if n.get("type") == "specimen"]
    if specimen_nodes:
        doc["specimens"] = [
            {
                "name": s.get("name"),
                "repository_identifier": s.get("repository_identifier"),
            }
            for s in specimen_nodes
        ]
    extension_counts: Counter[str] = Counter()
    for node in node_by_id.values():
        if node.get("type") not in FILE_NODE_TYPES:
            continue
        ext = detect_file_extension(node)
        if ext:
            extension_counts[ext] += 1
    if extension_counts:
        doc["files"]["extensions"] = [
            {"extension": ext, "count": extension_counts[ext]}
            for ext in sorted(extension_counts.keys())
        ]

    # search_text
    search_bits: list[str] = []
    search_bits.extend(
        [strip_html(doc["study"]["title"]), strip_html(doc["study"]["description"])]
    )
    if doc.get("project", {}).get("title"):
        search_bits.append(strip_html(doc["project"]["title"]))

    nested_text_sources = [
        doc.get("people", []),
        doc.get("organizations", []),
        doc.get("parameters", []),
        doc.get("descriptors", []),
        doc.get("ms_instruments", []),
        doc.get("chromatography_instruments", []),
        doc.get("other_instruments", []),
        doc.get("mass_analyzers", []),
        doc.get("factors", []),
        doc.get("protocols", []),
        doc.get("publications", []),
        doc.get("files", {}).get("extensions", []),
    ]
    for source in nested_text_sources:
        _collect_strings(source, search_bits)

    for k in SEARCH_FACET_KEYS:
        search_bits.extend(doc["facets"].get(k, []))

    doc["search_text"] = " ".join(dedup_preserve_order(search_bits)).strip()

    # final de-dup + sort facets
    for k, v in doc["facets"].items():
        doc["facets"][k] = dedup_sorted_strings(v)

    return doc
