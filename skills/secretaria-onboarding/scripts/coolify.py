#!/usr/bin/env python3
# Coolify onboarding helper (Tier A) for Secretária V4. Wraps the FRAGILE, deterministic mechanics of
# driving a Coolify instance during onboarding so the agent CALLS them instead of hand-assembling shell:
#   token           mint a root API token over SSH (artisan tinker; seeds currentTeam) -> 0600 file
#   enable-api      flip is_api_enabled=true (psql over SSH); the API is OFF by default (403 otherwise)
#   list-apps       SELECT id,name,fqdn FROM service_applications (psql over SSH) -> JSON
#   set-fqdn        UPDATE service_applications.fqdn by id (psql over SSH); the env SERVICE_FQDN_* does NOT
#                   drive Traefik, so this DB write is the real fix for the 503/cert-000 gotcha
#   api-get         authenticated GET  against /api/v1 (token read from --token-file, never argv/env)
#   api-post        authenticated POST against /api/v1 (--json-file / --json-stdin)
#   create-service  POST /api/v1/services with the compose base64-encoded (raw -> 422 "should be base64")
#
# WHY a script: the Coolify token is a Laravel Sanctum "<id>|<token>"; the "|" breaks an unquoted shell,
# and a weak model once looped on it and leaked the secret. Here the "|" only ever lives in a file and an
# HTTP header value, never in a shell command. SSH payloads (PHP/SQL) ship base64-piped so quoting and
# "$" expansion can't corrupt them. Python 3 stdlib only (no pip); mirrors scripts/portainer-brownfield.py.
#
# Network/SSH calls run through the Bash tool with dangerouslyDisableSandbox:true (see 00-prereqs).
import argparse
import base64
import json
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CONTAINER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
FQDN_RE = re.compile(r"^https?://[A-Za-z0-9.\-:/]+$")
SANCTUM_RE = re.compile(r"^\d+\|[A-Za-z0-9]{20,}$")

# The whole point: the decoded payload (with its quotes / "$" / "|") never reaches the remote shell.
PHP_TOKEN = (
    r'''$u = App\Models\User::first(); $t = $u ? $u->teams()->first() : null; '''
    r'''if ($u) { session(["currentTeam" => $t]); '''
    r'''echo "TOKEN_START".$u->createToken("__NAME__", ["*"])->plainTextToken."TOKEN_END"; } '''
    r'''else { echo "ERR_NO_USER"; }'''
)
SQL_ENABLE_API = "UPDATE instance_settings SET is_api_enabled = true;"
SQL_LIST_APPS = (
    "SELECT COALESCE("
    "json_agg(json_build_object('id', id, 'name', name, 'fqdn', fqdn) ORDER BY id), '[]')"
    " FROM service_applications;"
)


def out(obj, code=0):
    print(json.dumps(obj))
    sys.exit(code)


def fail(msg, **extra):
    out({"ok": False, "error": msg, **extra}, code=1)


def ssh_argv(dest, ssh_opts):
    extra = shlex.split(ssh_opts) if ssh_opts else []
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", *extra, dest]


def b64_pipe(payload, target):
    # base64 is shell-safe ([A-Za-z0-9+/=]); single-quote it so even a leading "-" can't trip echo.
    blob = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return f"echo '{blob}' | base64 -d | {target}"


def run_ssh(dest, ssh_opts, remote_cmd, timeout):
    try:
        return subprocess.run(
            [*ssh_argv(dest, ssh_opts), remote_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        fail("ssh not found on PATH")
    except subprocess.TimeoutExpired:
        fail(f"ssh timed out after {timeout}s", dest=dest)


def require_container(name):
    if not CONTAINER_RE.match(name):
        fail(f"invalid container name {name!r} (expected [A-Za-z0-9_.-]+)")


def psql_target(args):
    require_container(args.container)
    return (
        f"docker exec -i {args.container} "
        f"psql -U {args.db_user} -d {args.db_name} -v ON_ERROR_STOP=1"
    )


def read_token(token_file):
    try:
        tok = Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        fail(f"cannot read --token-file: {exc}")
    if not tok:
        fail("--token-file is empty")
    return tok


def http(method, base_url, path, token, body=None, timeout=60):
    url = base_url.rstrip("/") + "/api/v1/" + path.lstrip("/")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        fail(f"request failed: {exc.reason}", url=url)


def parse_json(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def cmd_token(args):
    require_container(args.container)
    if not re.match(r"^[A-Za-z0-9_-]+$", args.token_name):
        fail("--token-name must match [A-Za-z0-9_-]+")
    php = PHP_TOKEN.replace("__NAME__", args.token_name)
    target = f"docker exec -i {args.container} php artisan tinker"
    proc = run_ssh(args.ssh, args.ssh_opts, b64_pipe(php, target), args.timeout)
    combined = (proc.stdout or "") + (proc.stderr or "")
    if "ERR_NO_USER" in combined:
        fail("Coolify has no user yet — create the first admin before minting a token")
    match = re.search(r"TOKEN_START(.+?)TOKEN_END", combined, re.S)
    if not match:
        fail(
            "could not find a token in tinker output (admin created? did artisan run?)",
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[-400:],
            stderr=(proc.stderr or "")[-400:],
        )
    token = match.group(1).strip()
    if not SANCTUM_RE.match(token):
        fail("extracted value does not look like a Sanctum token")
    dest = Path(args.out)
    dest.write_text(token + "\n", encoding="utf-8")
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    out(
        {
            "ok": True,
            "token_file": str(dest),
            "token_id": token.split("|", 1)[0],
            "ability": "*",
            "note": "raw token written to file (chmod 600), not printed",
        }
    )


def cmd_enable_api(args):
    proc = run_ssh(args.ssh, args.ssh_opts, b64_pipe(SQL_ENABLE_API, psql_target(args)), args.timeout)
    if proc.returncode != 0:
        fail("psql failed", exit_code=proc.returncode, stderr=(proc.stderr or "")[-400:])
    out({"ok": True, "result": (proc.stdout or "").strip(), "idempotent": True})


def cmd_list_apps(args):
    target = psql_target(args) + " -tA"
    proc = run_ssh(args.ssh, args.ssh_opts, b64_pipe(SQL_LIST_APPS, target), args.timeout)
    if proc.returncode != 0:
        fail("psql failed", exit_code=proc.returncode, stderr=(proc.stderr or "")[-400:])
    raw = (proc.stdout or "").strip()
    try:
        rows = json.loads(raw)
    except ValueError:
        fail("could not parse psql JSON output", raw=raw[-400:])
    out({"ok": True, "count": len(rows), "apps": rows})


def poll_url(url, attempts, interval):
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                return {"reachable": True, "status": resp.status, "attempt": i + 1}
        except urllib.error.HTTPError as exc:
            return {"reachable": True, "status": exc.code, "attempt": i + 1}
        except Exception as exc:  # noqa: BLE001 — polling: any failure is "not ready yet"
            last = str(exc)
        if i < attempts - 1:
            time.sleep(interval)
    return {"reachable": False, "last_error": last, "attempts": attempts}


def cmd_set_fqdn(args):
    if not str(args.app_id).isdigit():
        fail("--app-id must be the numeric service_applications.id (see list-apps)")
    if not FQDN_RE.match(args.fqdn):
        fail("--fqdn must be http(s)://host[:port][/path] with no quotes")
    sql = f"UPDATE service_applications SET fqdn='{args.fqdn}' WHERE id={int(args.app_id)};"
    proc = run_ssh(args.ssh, args.ssh_opts, b64_pipe(sql, psql_target(args)), args.timeout)
    if proc.returncode != 0:
        fail("psql UPDATE failed", exit_code=proc.returncode, stderr=(proc.stderr or "")[-400:])
    result = (proc.stdout or "").strip()
    if result == "UPDATE 0":
        fail(f"no service_applications row with id={args.app_id} (see list-apps)", result=result)
    verify = poll_url(args.verify_url, args.verify_attempts, args.verify_interval) if args.verify_url else None
    out(
        {
            "ok": True,
            "result": result,
            "app_id": int(args.app_id),
            "fqdn": args.fqdn,
            "verify": verify,
            "note": "restart the Coolify SERVICE via its API (not coolify-proxy) for the route to apply",
        }
    )


def cmd_api_get(args):
    token = read_token(args.token_file)
    status, raw = http("GET", args.base_url, args.path, token, timeout=args.timeout)
    ok = 200 <= status < 300
    out({"ok": ok, "status": status, "data": parse_json(raw)}, code=0 if ok else 1)


def _post_body(args):
    if args.json_stdin and args.json_file:
        fail("pass only one of --json-file / --json-stdin")
    if args.json_stdin:
        body = parse_json(sys.stdin.read())
        if isinstance(body, str):
            fail("--json-stdin: not valid JSON")
        return body
    if args.json_file:
        try:
            return json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fail(f"--json-file: {exc}")
    return None


def cmd_api_post(args):
    token = read_token(args.token_file)
    status, raw = http("POST", args.base_url, args.path, token, body=_post_body(args), timeout=args.timeout)
    ok = 200 <= status < 300
    out({"ok": ok, "status": status, "data": parse_json(raw)}, code=0 if ok else 1)


def cmd_create_service(args):
    token = read_token(args.token_file)
    try:
        compose = Path(args.compose_file).read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read --compose-file: {exc}")
    body = {
        "name": args.name,
        "project_uuid": args.project_uuid,
        "server_uuid": args.server_uuid,
        "docker_compose_raw": base64.b64encode(compose.encode("utf-8")).decode("ascii"),
        "instant_deploy": bool(args.instant_deploy),
    }
    if args.environment_uuid:
        body["environment_uuid"] = args.environment_uuid
    else:
        body["environment_name"] = args.environment_name
    status, raw = http("POST", args.base_url, "/services", token, body=body, timeout=args.timeout)
    ok = 200 <= status < 300
    data = parse_json(raw)
    result = {"ok": ok, "status": status, "data": data}
    if ok and isinstance(data, dict):
        result["uuid"] = data.get("uuid") or (data.get("data") or {}).get("uuid")
    out(result, code=0 if ok else 1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="coolify.py",
        description="Coolify onboarding helper (Tier A). Keeps the Sanctum token out of every shell.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ssh = argparse.ArgumentParser(add_help=False)
    ssh.add_argument("--ssh", required=True, metavar="USER@HOST", help="SSH destination, e.g. root@1.2.3.4")
    ssh.add_argument("--ssh-opts", default="", help="extra ssh options, e.g. '-i ~/.ssh/key -p 2222'")
    ssh.add_argument("--timeout", type=int, default=120, help="per-command timeout in seconds")

    db = argparse.ArgumentParser(add_help=False)
    db.add_argument("--container", default="coolify-db", help="Coolify DB container (default: coolify-db)")
    db.add_argument("--db-user", default="coolify")
    db.add_argument("--db-name", default="coolify")

    api = argparse.ArgumentParser(add_help=False)
    api.add_argument("--base-url", required=True, metavar="URL", help="e.g. http://1.2.3.4:8000")
    api.add_argument("--token-file", required=True, help="file holding the Bearer token (from 'token')")
    api.add_argument("--timeout", type=int, default=60)

    p_token = sub.add_parser("token", parents=[ssh], help="mint a root API token over SSH -> 0600 file")
    p_token.add_argument("--out", required=True, help="file to write the token to (chmod 600)")
    p_token.add_argument("--container", default="coolify", help="Coolify app container (default: coolify)")
    p_token.add_argument("--token-name", default="fazer-ai-onboarding")
    p_token.set_defaults(fn=cmd_token)

    p_enable = sub.add_parser("enable-api", parents=[ssh, db], help="set is_api_enabled=true (psql over SSH)")
    p_enable.set_defaults(fn=cmd_enable_api)

    p_list = sub.add_parser("list-apps", parents=[ssh, db], help="list service_applications (id,name,fqdn)")
    p_list.set_defaults(fn=cmd_list_apps)

    p_fqdn = sub.add_parser("set-fqdn", parents=[ssh, db], help="set service_applications.fqdn by id")
    p_fqdn.add_argument("--app-id", required=True, help="numeric service_applications.id (see list-apps)")
    p_fqdn.add_argument("--fqdn", required=True, metavar="URL")
    p_fqdn.add_argument("--verify-url", help="optional URL to poll after the update")
    p_fqdn.add_argument("--verify-attempts", type=int, default=5)
    p_fqdn.add_argument("--verify-interval", type=int, default=5)
    p_fqdn.set_defaults(fn=cmd_set_fqdn)

    p_get = sub.add_parser("api-get", parents=[api], help="authenticated GET against /api/v1")
    p_get.add_argument("--path", required=True, metavar="/servers")
    p_get.set_defaults(fn=cmd_api_get)

    p_post = sub.add_parser("api-post", parents=[api], help="authenticated POST against /api/v1")
    p_post.add_argument("--path", required=True)
    p_post.add_argument("--json-file")
    p_post.add_argument("--json-stdin", action="store_true")
    p_post.set_defaults(fn=cmd_api_post)

    p_create = sub.add_parser("create-service", parents=[api], help="POST /services with compose base64-encoded")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--project-uuid", required=True)
    p_create.add_argument("--server-uuid", required=True)
    p_create.add_argument("--environment-name", default="production")
    p_create.add_argument("--environment-uuid")
    p_create.add_argument("--compose-file", required=True)
    p_create.add_argument("--instant-deploy", action="store_true")
    p_create.set_defaults(fn=cmd_create_service)

    return parser


def main():
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
