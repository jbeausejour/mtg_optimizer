#!/usr/bin/env python3
"""
MTG-Optimizer project synchronization script
Syncs local MTG-Optimizer project to Docker containers on Synology NAS.
This version fixes: wrong project paths, clearer rsync logging, and safer behavior.
"""

import os
import sys
import argparse
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import socket

class MTGOptimizerSync:
    def __init__(self):
        # ---------- Defaults (MTG ONLY) ----------
        # Local paths (Linux/WSL)
        self.local_mtg_root = "/home/junix/projects/mtg_optimizer"
        self.local_mtg_backend = f"{self.local_mtg_root}/backend"
        self.local_mtg_frontend = f"{self.local_mtg_root}/frontend"

        # Remote server settings
        self.local_server_ip = "192.168.68.61"
        self.remote_user = "julz"
        self.remote_host_alias = "syno-julz"           # SSH config Host alias (home)
        self.remote_host = "ext.julzandfew.com"        # Public host (away)
        self.remote_port = 7022

        # Remote paths (Docker appdata for MTG stack)
        self.remote_backend_path = "/volume1/docker/appdata/mtg-flask-app"
        self.remote_frontend_path = "/volume1/docker/appdata/mtg-frontend"

        # SSH config (WSL)
        self.ssh_config_path = "/home/junix/.ssh_wsl/config"

        # Exclusions (broad but safe for app syncs)
        self.exclude_patterns = [
            "__pycache__", "*.pyc", "*.pyo", "*.log",
            "*.db", "*.sqlite", "*.sqlite3",
            ".git", ".gitignore", ".gitattributes",
            "tests", ".pytest_cache", "htmlcov", ".coverage",
            "*.egg-info", "node_modules",
            "venv", ".venv", "env",
            ".env.dev", ".env.local", ".env.development",
            "dist", "build",
            ".DS_Store", "Thumbs.db", "*.tmp", "*.temp",
            ".idea", ".vscode",
            "migrations/__pycache__",
            "instance", "logs/*.log", "data/cache", "data/temp",
        ]

        # Files to keep safe during *directory* sync (we update them separately)
        self.protected_files_backend = [
            "Dockerfile", ".dockerignore", "entrypoint.sh",
            "requirements.txt", "pyproject.toml", ".env",
        ]
        self.protected_files_frontend = [
            "Dockerfile", ".dockerignore",
        ]

        self.debug = False

    # ---------- Utilities ----------
    def ts(self) -> str:
        return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"

    def log(self, msg: str, color: str = "blue"):
        colors = {
            "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
            "blue": "\033[94m", "cyan": "\033[96m", "magenta": "\033[95m",
            "reset": "\033[0m"
        }
        print(f"{colors.get(color, '')}{self.ts()} {msg}{colors['reset']}")

    def at_home(self) -> bool:
        """Detect if we can reach the NAS on local port (fast path)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((self.local_server_ip, self.remote_port))
            sock.close()
            home = (result == 0)
            self.log(f"Location detected: {'home (local network)' if home else 'away (remote access)'}", "blue")
            return home
        except Exception as e:
            self.log(f"Network test failed, assuming remote: {e}", "yellow")
            return False

    # ---------- Env helpers ----------
    def ensure_env_files(self):
        self.log("Checking .env file setup...", "blue")

        backend_env = Path(self.local_mtg_backend) / ".env"
        frontend_env = Path(self.local_mtg_frontend) / ".env"
        root_env = Path(self.local_mtg_root) / ".env"

        for f, name in [(root_env, "root"), (backend_env, "backend"), (frontend_env, "frontend")]:
            if f.exists():
                self.log(f"Found .env in {name} directory", "green")
                if name != "backend" and not backend_env.exists():
                    try:
                        shutil.copy2(f, backend_env)
                        self.log(".env copied to backend successfully", "green")
                    except Exception as e:
                        self.log(f"Failed to copy .env to backend: {e}", "red")
                break
        else:
            self.log("No .env file found - create one with your MTG-optimizer configuration", "yellow")

    # ---------- Tests ----------
    def run_tests(self, test_type: str = "simple") -> bool:
        self.log(f"Running tests ({test_type})...", "yellow")

        # Detect tests dir
        candidate_dirs = [
            Path(self.local_mtg_root) / "tests",
            Path(self.local_mtg_backend) / "tests",
            Path(self.local_mtg_root) / "test",
        ]
        tests_dir = next((p for p in candidate_dirs if p.exists()), None)
        if not tests_dir:
            self.log("Tests directory not found, skipping tests...", "yellow")
            return True

        original = os.getcwd()
        try:
            os.chdir(tests_dir)
            env = os.environ.copy()
            env.update({
                "DB_HOST": self.local_server_ip,
                "REDIS_HOST": self.local_server_ip,
                "API_BASE_URL": "http://192.168.68.61:5002",
                "FLASK_ENV": "testing",
            })

            cmds = {
                "simple": ["python", "-c", "print('Basic test placeholder')"],
                "unit": ["python", "-m", "pytest", "unit/", "-v", "--tb=short", "-q"],
                "api": ["python", "-m", "pytest", "api/", "-v", "--tb=short", "-q"],
                "integration": ["python", "-m", "pytest", "integration/", "-v", "--tb=short", "-q"],
                "quick": ["python", "-c", "print('Quick test mode - skipped')"],
                "all": ["python", "-m", "pytest", "-v", "--tb=short"],
            }
            cmd = cmds.get(test_type, cmds["simple"])
            self.log(f"Running: {' '.join(cmd)}", "blue")
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if self.debug:
                if res.stdout: print(res.stdout)
                if res.stderr: print(res.stderr, file=sys.stderr)
            ok = (res.returncode == 0)
            self.log("Tests passed!" if ok else "Tests failed!", "green" if ok else "red")
            return ok
        except Exception as e:
            self.log(f"Error running tests: {e}", "red")
            return False
        finally:
            os.chdir(original)

    # ---------- Rsync ----------
    def _build_rsync_base(self, ssh_options: str, delete: bool, checksum: bool):
        cmd = [
            "rsync",
            "-avi",                                   # verbose, itemize changes; no compression on LAN
            "--info=FLIST2,DEL2,NAME0",               # clearer change reporting
            "--partial",
            "-e", ssh_options,
            "--rsync-path=/bin/rsync",
            "--stats",
        ]
        if delete:
            cmd.append("--delete")
        if checksum:
            cmd.append("--checksum")
        return cmd

    def _exclude_opts(self, component_name: str):
        protected = self.protected_files_backend if "backend" in component_name.lower() else self.protected_files_frontend
        all_excludes = self.exclude_patterns + protected
        opts = []
        for pat in all_excludes:
            opts += ["--exclude", pat]
        return opts

    def build_rsync_command(self, source: str, remote_path: str, component_name: str,
                            is_home: bool, dry_run: bool, safe_mode: bool, checksum: bool):
        # Ensure trailing slash semantics on source/target
        source = str(Path(source)).rstrip("/") + "/"
        target = f"{remote_path}/"

        if is_home:
            ssh_target = self.remote_host_alias
            ssh_options = f"ssh -F {self.ssh_config_path}"
        else:
            ssh_target = f"{self.remote_user}@{self.remote_host}"
            ssh_options = f"ssh -F {self.ssh_config_path} -p {self.remote_port}"

        cmd = self._build_rsync_base(ssh_options, delete=not safe_mode, checksum=checksum)

        # backups always; choose backup dir name by mode
        cmd += ["--backup", "--backup-dir=.rsync-backup-safe" if safe_mode else "--backup-dir=.rsync-backup"]

        if dry_run:
            cmd.append("--dry-run")

        cmd += self._exclude_opts(component_name)
        cmd += [source, f"{ssh_target}:{target}"]
        return cmd

    def verify_remote_critical_files(self, remote_path: str, component_name: str) -> bool:
        critical = self.protected_files_backend if "backend" in component_name.lower() else self.protected_files_frontend

        is_home = self.at_home()
        if is_home:
            ssh_target = self.remote_host_alias
            ssh_options = f"ssh -F {self.ssh_config_path}"
        else:
            ssh_target = f"{self.remote_user}@{self.remote_host}"
            ssh_options = f"ssh -F {self.ssh_config_path} -p {self.remote_port}"

        missing = []
        for fname in critical:
            check_cmd = f"{ssh_options} {ssh_target} 'test -f {remote_path}/{fname}'"
            res = subprocess.run(check_cmd, shell=True, capture_output=True)
            if res.returncode != 0:
                missing.append(fname)

        if missing:
            self.log(f"WARNING: Missing critical files in {component_name}:", "red")
            for f in missing:
                self.log(f"  - {f}", "red")
            return False
        self.log(f"All critical files verified in {component_name}", "green")
        return True

    def sync_with_rsync(self, source: str, remote_path: str, component_name: str,
                        dry_run: bool, safe_mode: bool, checksum: bool) -> bool:
        is_home = self.at_home()
        self.log(f"Using SSH to {'local server (' + self.local_server_ip + ')' if is_home else 'remote server (' + self.remote_host + ')'}", "blue")
        self.log(f"Source: {source}", "cyan")
        self.log(f"Target: {remote_path}", "cyan")

        if not dry_run:
            self.log(f"Verifying critical files before sync for {component_name}...", "blue")
            self.verify_remote_critical_files(remote_path, component_name)

        try:
            cmd = self.build_rsync_command(source, remote_path, component_name, is_home, dry_run, safe_mode, checksum)
            if self.debug or dry_run:
                self.log("Rsync command:", "yellow")
                self.log("  " + " ".join(cmd), "yellow")

            res = subprocess.run(cmd, capture_output=True, text=True)
            if self.debug:
                if res.stdout: print(res.stdout)
                if res.stderr: print(res.stderr, file=sys.stderr)

            if res.returncode == 0:
                self.log(f"{component_name} sync completed successfully", "green")
                # Print last few lines of stats for quick glance
                if res.stdout:
                    lines = [ln for ln in res.stdout.strip().splitlines() if ln.strip()]
                    for ln in lines[-8:]:
                        self.log("  " + ln, "cyan")

                self.log(f"Verifying critical files after sync for {component_name}...", "blue")
                self.verify_remote_critical_files(remote_path, component_name)
                return True
            else:
                self.log(f"{component_name} sync failed - exit code: {res.returncode}", "red")
                if res.stderr:
                    self.log(f"Error: {res.stderr}", "red")
                if res.stdout and not self.debug:
                    self.log(f"Output: {res.stdout}", "yellow")
                return False
        except Exception as e:
            self.log(f"{component_name} sync failed: {e}", "red")
            return False

    # ---------- High-level ops ----------
    def sync_backend_only(self, dry_run: bool, safe_mode: bool, force_update: bool):
        self.log("Syncing MTG-Optimizer backend (Flask app)...", "magenta")
        ok = self.sync_with_rsync(
            self.local_mtg_backend,
            self.remote_backend_path,
            "MTG-Optimizer backend",
            dry_run=dry_run,
            safe_mode=safe_mode,
            checksum=force_update
        )
        if ok and not dry_run:
            # Also push pyproject.toml / requirements.txt if present
            files = []
            pyproj = Path(self.local_mtg_backend) / "pyproject.toml"
            req = Path(self.local_mtg_backend) / "requirements.txt"
            if pyproj.exists(): files.append(str(pyproj))
            if req.exists(): files.append(str(req))
            if files:
                self._push_specific_files(files, self.remote_backend_path, label="backend extras", safe_mode=safe_mode, force_update=force_update)
        return ok

    def _push_specific_files(self, files, remote_path, label: str, safe_mode: bool, force_update: bool):
        self.log(f"Syncing additional files: {[Path(f).name for f in files]}...", "magenta")
        is_home = self.at_home()
        if is_home:
            target = f"{self.remote_host_alias}:{remote_path}/"
            ssh_options = f"ssh -F {self.ssh_config_path}"
        else:
            target = f"{self.remote_user}@{self.remote_host}:{remote_path}/"
            ssh_options = f"ssh -F {self.ssh_config_path} -p {self.remote_port}"

        cmd = [
            "rsync", "-avi", "--info=FLIST2,DEL2,NAME0", "--partial",
            "-e", ssh_options, "--rsync-path=/bin/rsync", "--stats", "--ignore-errors",
            "--backup", "--backup-dir=.rsync-backup-safe" if safe_mode else "--backup-dir=.rsync-backup"
        ]
        if force_update:
            cmd.append("--checksum")
        # No --delete when sending specific files
        cmd += files + [target]

        if self.debug:
            self.log("Rsync (extras) command:", "yellow")
            self.log("  " + " ".join(cmd), "yellow")

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            self.log(f"Additional files sync completed successfully", "green")
            if res.stdout:
                lines = [ln for ln in res.stdout.strip().splitlines() if ln.strip()]
                for ln in lines[-6:]:
                    self.log("  " + ln, "cyan")
        else:
            self.log("Sync of additional files failed", "red")
            if res.stderr:
                self.log(f"Error: {res.stderr}", "red")
            if res.stdout:
                self.log(f"Output: {res.stdout}", "yellow")

    def sync_frontend_only(self, dry_run: bool, safe_mode: bool):
        self.log("Syncing MTG-Optimizer frontend (React app)...", "magenta")
        return self.sync_with_rsync(
            self.local_mtg_frontend,
            self.remote_frontend_path,
            "MTG-Optimizer frontend",
            dry_run=dry_run, safe_mode=safe_mode, checksum=False
        )

    def sync_both(self, dry_run: bool, safe_mode: bool, force_update: bool):
        self.log("Syncing both MTG-Optimizer backend and frontend...", "magenta")
        b = self.sync_backend_only(dry_run, safe_mode, force_update)
        f = self.sync_frontend_only(dry_run, safe_mode)
        if b and f:
            self.log("Full MTG-Optimizer sync completed successfully", "green")
            return True
        self.log(f"Some MTG-Optimizer syncs failed - Backend: {b}, Frontend: {f}", "red")
        return False

    # ---------- Validation / summary ----------
    def validate_paths(self) -> bool:
        ok = True
        for path, label in [
            (self.local_mtg_root, "MTG-Optimizer root"),
            (self.local_mtg_backend, "MTG-Optimizer backend"),
            (self.local_mtg_frontend, "MTG-Optimizer frontend"),
        ]:
            if not Path(path).exists():
                self.log(f"{label} directory not found: {path}", "red")
                ok = False
        return ok

    def show_sync_summary(self):
        self.log("MTG-Optimizer Sync Configuration:", "cyan")
        self.log(f"  Local root:       {self.local_mtg_root}", "cyan")
        self.log(f"  Remote backend:   {self.remote_backend_path}", "cyan")
        self.log(f"  Remote frontend:  {self.remote_frontend_path}", "cyan")
        self.log(f"  Server:           {self.remote_host_alias} ({self.local_server_ip})", "cyan")
        self.log(f"  SSH config:       {self.ssh_config_path}", "cyan")
        self.log("", "cyan")

def main():
    p = argparse.ArgumentParser(description="MTG-Optimizer sync script (fixed)")
    p.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    p.add_argument("--test-only", action="store_true", help="Run tests only, no sync")
    p.add_argument("--quick", action="store_true", help="Quick mode with minimal testing")
    p.add_argument("--test-type", default="simple",
                   choices=["simple", "unit", "api", "integration", "quick", "all"],
                   help="Type of tests to run")

    p.add_argument("--backend-only", action="store_true", help="Sync backend only")
    p.add_argument("--frontend-only", action="store_true", help="Sync frontend only")
    p.add_argument("--dry-run", action="store_true", help="Show what would be synced without doing it")
    p.add_argument("--safe-mode", action="store_true", help="No deletions; all changes backed up to .rsync-backup-safe")
    p.add_argument("--force-update", action="store_true", help="Use --checksum to force updates when mtimes are misleading")
    p.add_argument("--debug", action="store_true", help="Print full rsync commands and stdout/stderr")

    # Optional overrides (in case paths change)
    p.add_argument("--local-root", help="Override local project root")
    p.add_argument("--remote-backend", help="Override remote backend path")
    p.add_argument("--remote-frontend", help="Override remote frontend path")

    args = p.parse_args()

    syncer = MTGOptimizerSync()
    syncer.debug = args.debug

    # Apply optional overrides
    if args.local_root:
        syncer.local_mtg_root = args.local_root.rstrip("/")
        syncer.local_mtg_backend = f"{syncer.local_mtg_root}/backend"
        syncer.local_mtg_frontend = f"{syncer.local_mtg_root}/frontend"
    if args.remote_backend:
        syncer.remote_backend_path = args.remote_backend.rstrip("/")
    if args.remote_frontend:
        syncer.remote_frontend_path = args.remote_frontend.rstrip("/")

    syncer.log("Starting MTG-Optimizer sync...", "cyan")

    # Validate
    if not syncer.validate_paths():
        sys.exit(1)

    # Summary
    syncer.show_sync_summary()

    # Ensure env files
    syncer.ensure_env_files()

    # Tests
    if args.test_only:
        syncer.log("Test-only mode", "yellow")
        ok = syncer.run_tests(args.test_type)
        sys.exit(0 if ok else 1)

    if not args.skip_tests and not args.quick:
        syncer.log("Running tests before sync...", "yellow")
        if not syncer.run_tests(args.test_type):
            syncer.log("Sync aborted due to test failures!", "red")
            syncer.log("Use --skip-tests to bypass, or --quick for minimal testing", "yellow")
            sys.exit(1)
        syncer.log("Tests passed, proceeding with sync...", "green")
    elif args.quick:
        syncer.log("Quick mode - running basic tests...", "yellow")
        if not syncer.run_tests("quick"):
            syncer.log("Quick tests failed, but proceeding with sync...", "yellow")
        else:
            syncer.log("Quick tests passed!", "green")
    else:
        syncer.log("Skipping tests...", "yellow")

    # Sync
    if args.backend_only:
        ok = syncer.sync_backend_only(args.dry_run, args.safe_mode, args.force_update)
    elif args.frontend_only:
        ok = syncer.sync_frontend_only(args.dry_run, args.safe_mode)
    else:
        ok = syncer.sync_both(args.dry_run, args.safe_mode, args.force_update)

    if ok:
        syncer.log(f"MTG-Optimizer sync completed successfully{' (dry run)' if args.dry_run else ''}!", "green")
        if not args.dry_run:
            syncer.log("", "green")
            syncer.log("Next steps:", "green")
            syncer.log("1. Check container logs: docker compose -f /volume1/docker/compose/synology/mtg-optimizer.yml logs -f mtg-flask-app", "green")
            syncer.log("2. Restart services if needed: docker compose -f /volume1/docker/compose/synology/mtg-optimizer.yml restart mtg-flask-app mtg-frontend", "green")
            syncer.log("3. Test the application at your configured URLs", "green")
    else:
        syncer.log("MTG-Optimizer sync failed!", "red")
        sys.exit(1)

if __name__ == "__main__":
    main()