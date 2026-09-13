#!/usr/bin/env python3
"""Serve the project tree web UI. Usage: python scripts/tree_server.py [port]"""

from __future__ import annotations

import json
import select
import socket
import sys
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))

import workflow_mcp
from project_tree import fragments, model
from project_tree.model import find_node_in_tree, list_projects, load_tree
from project_tree.fragments import compose_tree
from project_tree.verify_runner import run_verification, verification_spec_from_node_data
from spec_discovery.model import save_document

UI_DIR = PACKAGE_ROOT / "tools" / "tree-viewer"


def get_project_fingerprint(proj_dir: Path | str) -> tuple:
    """Calculate fingerprint (tuple of sorted (rel_path, mtime_ns, size)) of monitored files."""
    proj_dir = Path(proj_dir)
    file_records: list[tuple[str, int, int]] = []

    # 1. nodes.yaml, nodes.yaml.proposed
    for fname in ("nodes.yaml", "nodes.yaml.proposed"):
        fpath = proj_dir / fname
        try:
            st = fpath.stat()
            file_records.append((fname, st.st_mtime_ns, st.st_size))
        except OSError:
            pass

    # 2. fragments/*.yaml, fragments/*.yaml.proposed
    frag_dir = proj_dir / "fragments"
    if frag_dir.is_dir():
        try:
            for entry in frag_dir.iterdir():
                if entry.is_file() and (entry.name.endswith(".yaml") or entry.name.endswith(".yaml.proposed")):
                    try:
                        st = entry.stat()
                        file_records.append((f"fragments/{entry.name}", st.st_mtime_ns, st.st_size))
                    except OSError:
                        pass
        except OSError:
            pass

    # 3. claims/*.json
    claims_dir = proj_dir / "claims"
    if claims_dir.is_dir():
        try:
            for entry in claims_dir.iterdir():
                if entry.is_file() and entry.name.endswith(".json"):
                    try:
                        st = entry.stat()
                        file_records.append((f"claims/{entry.name}", st.st_mtime_ns, st.st_size))
                    except OSError:
                        pass
        except OSError:
            pass

    file_records.sort(key=lambda x: x[0])
    return tuple(file_records)


class TreeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format, *args):
        if args and any(str(args[0]).startswith(p) for p in ("GET /api", "POST /api")):
            super().log_message(format, *args)

    def do_GET(self):
        clean_path = self.path.split("?", 1)[0]
        if clean_path == "/api/projects":
            self._json_response(list_projects())
            return
        if clean_path.startswith("/api/tree/"):
            project = unquote(clean_path.removeprefix("/api/tree/").strip("/"))
            try:
                self._json_response(self._load_tree(project))
            except FileNotFoundError:
                self._error_response(404, f"Project not found: {project}")
            return
        if clean_path == "/api/proposals" or clean_path == "/api/proposals/":
            self._error_response(400, "Missing project: /api/proposals/<project>")
            return
        if clean_path.startswith("/api/proposals/"):
            project = unquote(clean_path.removeprefix("/api/proposals/").strip("/"))
            self._handle_get_proposals(project)
            return
        if clean_path == "/api/claims" or clean_path == "/api/claims/":
            self._error_response(400, "Missing project and node_id: /api/claims/<project>/<node_id>")
            return
        if clean_path.startswith("/api/claims/"):
            self._handle_get_claims(clean_path)
            return
        if clean_path == "/api/events" or clean_path == "/api/events/":
            self._error_response(400, "Missing project: /api/events/<project>")
            return
        if clean_path.startswith("/api/events/"):
            project = unquote(clean_path.removeprefix("/api/events/").strip("/"))
            self._handle_events_stream(project)
            return
        if self.path == "/":
            self.path = "/index.html"
        if "?" in self.path:
            self.path = self.path.split("?", 1)[0]
        return super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?", 1)[0].rstrip("/")
        data = self._parse_json_body()
        if data is None:
            return

        if clean_path == "/api/proposals/apply":
            self._handle_proposals_apply(data)
            return
        if clean_path == "/api/proposals/reject":
            self._handle_proposals_reject(data)
            return
        if clean_path == "/api/claims/triage":
            self._handle_claims_triage(data)
            return
        if clean_path == "/api/verify":
            self._handle_verify(data)
            return
        if clean_path == "/api/mutate":
            self._handle_mutate(data)
            return

        self._error_response(404, f"Endpoint not found: {clean_path}")

    def end_headers(self) -> None:
        has_cache_control = any(
            h.lower().startswith(b"cache-control:")
            for h in getattr(self, "_headers_buffer", [])
        )
        if not has_cache_control:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _load_tree(self, name: str) -> dict:
        from project_tree.model import nodes_path, resolve_project_name, list_pending_proposals

        name = resolve_project_name(name)
        path = nodes_path(name)
        if not path.exists():
            raise FileNotFoundError(name)
        with path.open() as f:
            data = yaml.safe_load(f)
        pending_list = list_pending_proposals(name)
        data["pending"] = len(pending_list) > 0
        data["pending_targets"] = [p[0] or "nodes.yaml" for p in pending_list]
        try:
            data = fragments.compose_tree(data, name)
        except (FileNotFoundError, ValueError) as exc:
            data["compose_error"] = str(exc)
        return data

    def _parse_json_body(self) -> dict | None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._error_response(400, "Invalid Content-Length")
            return None

        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        if not raw_body:
            return {}
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._error_response(400, f"Invalid JSON body: {exc}")
            return None

        if not isinstance(data, dict):
            self._error_response(400, "JSON body must be an object")
            return None
        return data

    def _handle_get_proposals(self, project: str) -> None:
        if not project:
            self._error_response(400, "Missing project name")
            return
        try:
            name = model.resolve_project_name(project)
            path = model.nodes_path(name)
            if not path.exists():
                self._error_response(404, f"Project not found: {project}")
                return
            pending_list = model.list_pending_proposals(name)
            proposals = []
            for frag, p_path in pending_list:
                target_label = frag or "nodes.yaml"
                diff_str = model.get_pending_proposal_diff(name, frag)
                proposals.append({
                    "target": target_label,
                    "fragment": frag,
                    "path": str(p_path),
                    "diff": diff_str,
                })
            self._json_response({"project": project, "proposals": proposals})
        except FileNotFoundError:
            self._error_response(404, f"Project not found: {project}")
        except Exception as exc:
            self._error_response(500, f"Error loading proposals: {exc}")

    def _handle_get_claims(self, clean_path: str) -> None:
        parts = clean_path.removeprefix("/api/claims/").strip("/").split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            self._error_response(400, "Invalid path format: expected /api/claims/<project>/<node_id>")
            return
        project = unquote(parts[0])
        node_id = unquote(parts[1])
        if ".." in node_id or "/" in node_id or "\\" in node_id:
            self._error_response(400, "Invalid node_id")
            return
        try:
            claims_file = model.project_dir(project) / "claims" / f"{node_id}.json"
            if claims_file.is_file():
                with claims_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self._json_response(data)
            else:
                self._json_response({"claims": []})
        except Exception as exc:
            self._error_response(500, f"Error loading claims: {exc}")

    def _handle_proposals_apply(self, data: dict) -> None:
        project = data.get("project")
        if not project or not str(project).strip():
            self._error_response(400, "Missing required field 'project'")
            return
        fragment = data.get("fragment")
        fragment_rel = fragment if fragment else None
        try:
            model.apply_pending_proposal(project, fragment_rel=fragment_rel)
            self._json_response({"status": "applied", "project": project, "fragment": fragment_rel})
        except FileNotFoundError as exc:
            self._error_response(404, str(exc))
        except Exception as exc:
            self._error_response(400, str(exc))

    def _handle_proposals_reject(self, data: dict) -> None:
        project = data.get("project")
        if not project or not str(project).strip():
            self._error_response(400, "Missing required field 'project'")
            return
        fragment = data.get("fragment")
        fragment_rel = fragment if fragment else None
        try:
            model.reject_pending_proposal(project, fragment_rel=fragment_rel)
            self._json_response({"status": "rejected", "project": project, "fragment": fragment_rel})
        except FileNotFoundError as exc:
            self._error_response(404, str(exc))
        except Exception as exc:
            self._error_response(400, str(exc))

    def _handle_claims_triage(self, data: dict) -> None:
        project = data.get("project")
        node_id = data.get("node_id")
        claim_id = data.get("claim_id")
        decision = data.get("decision")
        if not project or not node_id or not claim_id or not decision:
            self._error_response(400, "Missing required fields: 'project', 'node_id', 'claim_id', 'decision'")
            return
        if decision not in ("approved", "rejected", "skipped", "pending"):
            self._error_response(400, f"Invalid decision: '{decision}'. Must be one of: approved, rejected, skipped, pending")
            return
        if ".." in node_id or "/" in node_id or "\\" in node_id:
            self._error_response(400, "Invalid node_id")
            return

        claims_file = model.project_dir(project) / "claims" / f"{node_id}.json"
        if not claims_file.is_file():
            self._error_response(404, f"Claims file not found for node: {node_id}")
            return

        try:
            with claims_file.open("r", encoding="utf-8") as f:
                claims_data = json.load(f)
        except Exception as exc:
            self._error_response(500, f"Failed to read claims file: {exc}")
            return

        claims = claims_data.get("claims")
        if not isinstance(claims, list):
            self._error_response(400, "Malformed claims file: 'claims' is not a list")
            return

        target_claim = None
        for c in claims:
            if isinstance(c, dict) and c.get("id") == claim_id:
                target_claim = c
                break

        if target_claim is None:
            self._error_response(404, f"Claim '{claim_id}' not found in node '{node_id}'")
            return

        target_claim["decision"] = decision
        target_claim["triaged_at"] = datetime.now(timezone.utc).isoformat()

        try:
            save_document(claims_file, claims_data)
        except Exception as exc:
            self._error_response(500, f"Failed to save claims file: {exc}")
            return

        self._json_response(claims_data)

    def _handle_verify(self, data: dict) -> None:
        project = data.get("project")
        node_id = data.get("node_id")
        if not project or not node_id:
            self._error_response(400, "Missing required fields: 'project', 'node_id'")
            return
        try:
            raw_tree = load_tree(project)
            composed = compose_tree(raw_tree, project)
            node = find_node_in_tree(composed, node_id)
            if node is None:
                raise ValueError(f"Node '{node_id}' not found in project '{project}'")

            node_data = node.get("data") or {}
            spec = verification_spec_from_node_data(node_data)
            repo_root = getattr(model, "REPO_ROOT", None) or model.host_root()
            timeout = float(data.get("timeout", 30.0))
            result = run_verification(spec, Path(repo_root), timeout=timeout)
            res = {
                "status": result["status"],
                "project": project,
                "node_id": node_id,
                "command": result["command"],
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "duration_seconds": result["duration_seconds"],
            }
            self._json_response(res)
        except FileNotFoundError as exc:
            self._error_response(404, str(exc))
        except ValueError as exc:
            status = 404 if "not found" in str(exc).lower() else 400
            self._error_response(status, str(exc))
        except Exception as exc:
            self._error_response(500, f"Verification execution error: {exc}")

    def _handle_mutate(self, data: dict) -> None:
        project = data.get("project")
        target_node_id = data.get("target_node_id")
        operation = data.get("operation")
        payload = data.get("payload")
        fragment = data.get("fragment")

        if not project or not target_node_id or not operation:
            self._error_response(400, "Missing required fields: 'project', 'target_node_id', 'operation'")
            return
        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            self._error_response(400, "Field 'payload' must be a dictionary")
            return

        try:
            res = workflow_mcp.workflow_propose_tree_mutation(
                project=project,
                target_node_id=target_node_id,
                operation=operation,
                payload=payload,
                fragment=fragment,
            )
            self._json_response(res)
        except FileNotFoundError as exc:
            self._error_response(404, str(exc))
        except ValueError as exc:
            status = 404 if "not found" in str(exc).lower() else 400
            self._error_response(status, str(exc))
        except Exception as exc:
            self._error_response(500, f"Mutation error: {exc}")

    def _is_server_shutting_down(self) -> bool:
        if not hasattr(self, "server") or self.server is None:
            return False
        return bool(
            getattr(self.server, "_shutdown_requested", False)
            or getattr(self.server, "_BaseServer__shutdown_request", False)
            or getattr(self.server, "shutdown_flag", False)
        )

    def _send_sse_event(self, event: str, data: dict) -> None:
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")
        self.wfile.write(payload)
        self.wfile.flush()

    def _handle_events_stream(self, project: str) -> None:
        if not project:
            self._error_response(400, "Missing project name")
            return
        try:
            name = model.resolve_project_name(project)
            proj_dir = model.project_dir(name)
            nodes_file = model.nodes_path(name)
            if not nodes_file.exists():
                self._error_response(404, f"Project not found: {project}")
                return
        except FileNotFoundError:
            self._error_response(404, f"Project not found: {project}")
            return
        except Exception as exc:
            self._error_response(500, f"Error resolving project: {exc}")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            self._send_sse_event("connected", {"project": project})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout, OSError):
            self.close_connection = True
            return

        last_fingerprint = get_project_fingerprint(proj_dir)
        poll_interval = getattr(self.server, "sse_poll_interval", 0.25)
        ping_interval = getattr(self.server, "sse_ping_interval", 15.0)
        last_event_time = time.time()

        while True:
            if self._is_server_shutting_down():
                break

            try:
                r, _, _ = select.select([self.connection], [], [], poll_interval)
                if r:
                    peek = self.connection.recv(1, socket.MSG_PEEK)
                    if not peek:
                        break
            except (OSError, socket.error):
                break
            except (AttributeError, ValueError):
                time.sleep(poll_interval)

            if self._is_server_shutting_down():
                break

            current_fingerprint = get_project_fingerprint(proj_dir)
            now = time.time()
            if current_fingerprint != last_fingerprint:
                last_fingerprint = current_fingerprint
                last_event_time = now
                try:
                    self._send_sse_event("tree_changed", {"project": project})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout, OSError):
                    break
            elif now - last_event_time >= ping_interval:
                last_event_time = now
                try:
                    self._send_sse_event("ping", {})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout, OSError):
                    break

        self.close_connection = True

    def _json_response(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, status: int, message: str) -> None:
        self._json_response({"error": message}, status=status)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), TreeHandler)
    projects = list_projects()
    q = f"?project={projects[0]}" if projects else ""
    url = f"http://127.0.0.1:{port}/{q}"
    print(f"Tree viewer at {url}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
