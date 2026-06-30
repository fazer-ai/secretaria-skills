#!/usr/bin/env python3
# Harbor (private registry) login on the VPS for the Secretária V4 onboarding. Runs `docker login
# --password-stdin` over SSH so the robot secret never lands in argv / ps / shell history, and the robot
# username (which contains a "$", e.g. robot$project — a shell-expansion footgun, same family as the
# Coolify token's "|") is decoded in-shell from base64 and passed quoted. The credential comes from the
# hub MCP (create_registry_credential / generate_install_script); write the secret to a 0600 file and
# pass --secret-file. Python 3 stdlib only. SSH runs via Bash with dangerouslyDisableSandbox:true.
import argparse
import base64
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def out(obj, code=0):
    print(json.dumps(obj))
    sys.exit(code)


def fail(msg, **extra):
    out({"ok": False, "error": msg, **extra}, code=1)


def split_ssh_opts(opts, _nt=None):
    # POSIX shlex eats backslashes, mangling a Windows key path ("-i C:\Users\me\.ssh\key" ->
    # "C:Usersme.sshkey"). On Windows, tokenize without escape processing and strip our own quotes so the
    # backslashes survive. _nt is injectable for tests.
    nt = (os.name == "nt") if _nt is None else _nt
    if not opts:
        return []
    if nt:
        toks = shlex.split(opts, posix=False)
        return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in toks]
    return shlex.split(opts)


def cmd_login(args):
    try:
        secret = Path(args.secret_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        fail(f"cannot read --secret-file: {exc}")
    if not secret:
        fail("--secret-file is empty")
    user_b64 = base64.b64encode(args.username.encode("utf-8")).decode("ascii")
    secret_b64 = base64.b64encode(secret.encode("utf-8")).decode("ascii")
    # Decode the username in-shell (protects the "$") and feed the secret via --password-stdin.
    remote = (
        f"U=$(echo '{user_b64}' | base64 -d); "
        f"echo '{secret_b64}' | base64 -d | docker login -u \"$U\" --password-stdin {args.registry}"
    )
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", *split_ssh_opts(args.ssh_opts), args.ssh, remote]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=args.timeout)
    except FileNotFoundError:
        fail("ssh not found on PATH")
    except subprocess.TimeoutExpired:
        fail(f"ssh timed out after {args.timeout}s")
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or "Login Succeeded" not in combined:
        fail("docker login failed", exit_code=proc.returncode, stderr=(proc.stderr or "")[-400:])
    out({"ok": True, "registry": args.registry, "result": "Login Succeeded"})


def build_parser():
    parser = argparse.ArgumentParser(
        prog="harbor-login.py",
        description="docker login to a private registry on the VPS; secret via stdin, robot '$' protected.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    login = sub.add_parser("login", help="docker login over SSH (secret via --password-stdin)")
    login.add_argument("--ssh", required=True, metavar="USER@HOST")
    login.add_argument("--username", required=True, help="robot account, e.g. 'robot$project+name'")
    login.add_argument("--secret-file", required=True, help="file holding the robot secret (chmod 600)")
    login.add_argument("--registry", default="harbor.fazer.ai")
    login.add_argument("--ssh-opts", default="", help="extra ssh options, e.g. '-i ~/.ssh/key -p 2222'")
    login.add_argument("--timeout", type=int, default=60)
    login.set_defaults(fn=cmd_login)
    return parser


def main():
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
