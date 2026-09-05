"""Run browser verification against a disposable local full stack."""

import fcntl
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

import psycopg
from psycopg import sql

E2E = Path(__file__).resolve().parent
ROOT = E2E.parent
BACKEND = ROOT / "crackGreVocab"
FRONTEND = ROOT / "gre-vocab-front-end"


def reserve_port(port: int) -> None:
    """Fail before setup if a requested test port belongs to another process."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))


def stop_process(process: subprocess.Popen) -> None:
    """Stop the owned process group, including children started by build tools."""
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    output: TextIO | None = None,
    check: bool = True,
) -> int:
    """Run a build or test command and stop its children on interruption."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        returncode = process.wait()
        if check and returncode:
            raise subprocess.CalledProcessError(returncode, command)
        return returncode
    finally:
        stop_process(process)


def wait_ready(url: str, process: subprocess.Popen, log: Path) -> None:
    """Wait for a successful health response while checking for early exit."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before readiness; see {log}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except URLError, TimeoutError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready at {url}; see {log}")


def run_stack(database_name: str, connection: str) -> int:
    """Build and exercise the app using only the database created by this run."""
    api_port = int(os.environ.get("E2E_API_PORT", "8100"))
    web_port = int(os.environ.get("E2E_WEB_PORT", "3100"))
    if api_port == web_port:
        raise ValueError("E2E_API_PORT and E2E_WEB_PORT must differ.")
    reserve_port(api_port)
    reserve_port(web_port)
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"
    artifacts = E2E / "artifacts" / database_name
    mail = artifacts / "mail"
    mail.mkdir(parents=True)
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(BACKEND), str(ROOT))),
        "PYTHONUNBUFFERED": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "DJANGO_SETTINGS_MODULE": "e2e.settings",
        "DATABASE_URL": urlunsplit(
            urlsplit(connection)._replace(path=f"/{database_name}")
        ),
        "SECRET_KEY": "e2e-only-disposable-secret-not-for-hosting",
        "DEBUG": "true",
        "ALLOWED_HOSTS": "127.0.0.1",
        "CORS_ALLOWED_ORIGINS": web_url,
        "CSRF_TRUSTED_ORIGINS": web_url,
        "SECURE_SSL_REDIRECT": "false",
        "TRUST_X_FORWARDED_PROTO": "false",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": "false",
        "GOOGLE_OAUTH_CLIENT_ID": "",
        "GOOGLE_OAUTH_CLIENT_SECRET": "",
        "GOOGLE_OAUTH_FRONTEND_ORIGIN": web_url,
        "PASSWORD_RESET_FRONTEND_URL": f"{web_url}/reset-password/confirm",
        "EMAIL_BACKEND": "django.core.mail.backends.filebased.EmailBackend",
        "DEFAULT_FROM_EMAIL": "no-reply@example.test",
        "E2E_MAIL_DIR": str(mail),
        "E2E_BASE_URL": web_url,
        "E2E_API_URL": api_url,
        "NEXT_PUBLIC_API_BASE_URL": api_url,
        "NEXT_DIST_DIR": ".next-e2e",
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    print(f"E2E database: {database_name}\nLogs: {artifacts}", flush=True)

    with ExitStack() as resources:
        setup_log = artifacts / "setup.log"
        setup_output = resources.enter_context(setup_log.open("w"))
        for arguments in (
            ("migrate", "--noinput"),
            (
                "import_vocabulary_corpus",
                "data/vocabulary/versions/m1-v2/manifest.json",
            ),
        ):
            print(f"Django: {arguments[0]}", flush=True)
            run_command(
                [sys.executable, "manage.py", *arguments],
                cwd=BACKEND,
                env=env,
                output=setup_output,
            )
        print("Building the frontend for E2E…", flush=True)
        run_command(
            ["npm", "run", "build", "--", "--webpack"],
            cwd=FRONTEND,
            env=env,
            output=setup_output,
        )
        for name, command, cwd, health_url in (
            (
                "backend",
                [
                    sys.executable,
                    "manage.py",
                    "runserver",
                    f"127.0.0.1:{api_port}",
                    "--noreload",
                ],
                BACKEND,
                f"{api_url}/api/readiness/",
            ),
            (
                "frontend",
                [
                    "node",
                    "node_modules/next/dist/bin/next",
                    "start",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(web_port),
                ],
                FRONTEND,
                f"{web_url}/sign-in",
            ),
        ):
            log = artifacts / f"{name}.log"
            output = resources.enter_context(log.open("w"))
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            resources.callback(stop_process, process)
            wait_ready(health_url, process, log)
        return run_command(
            ["node", "node_modules/@playwright/test/cli.js", "test", *sys.argv[1:]],
            cwd=E2E,
            env=env,
            check=False,
        )


def main() -> int:
    """Create a unique test database and remove it even after failed tests."""
    connection = os.environ.get("E2E_DATABASE_URL", "postgresql://127.0.0.1/postgres")
    address = urlsplit(connection)
    if (
        address.scheme not in {"postgresql", "postgres"}
        or address.hostname not in {"localhost", "127.0.0.1"}
        or address.query
    ):
        raise ValueError("E2E_DATABASE_URL must address a local PostgreSQL server.")
    # Serialize runs because Next.js and Playwright use shared output directories.
    with (E2E / ".run.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                "Another E2E run is already using this checkout."
            ) from None
        database_name = f"gre_e2e_{uuid.uuid4().hex}"
        with psycopg.connect(connection, autocommit=True, connect_timeout=5) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )
            try:
                return run_stack(database_name, connection)
            finally:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )
                print(f"Removed E2E database: {database_name}", flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    raise SystemExit(main())
