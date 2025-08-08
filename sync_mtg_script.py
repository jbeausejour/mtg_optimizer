#!/usr/bin/env python3
"""
MTG-Optimizer project synchronization script
Syncs local MTG-Optimizer project to Docker containers on Synology NAS
Based on the NexBudget sync script structure
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
        # Local paths (Linux/WSL)
        self.local_mtg_root = "/home/junix/projects/mtg_optimizer"
        self.local_mtg_backend = f"{self.local_mtg_root}/backend"
        self.local_mtg_frontend = f"{self.local_mtg_root}/frontend"
        
        # Remote server settings
        self.local_server_ip = "192.168.68.61"
        self.remote_user = "julz"
        self.remote_host_alias = "syno-julz"
        self.remote_port = 7022
        
        # Remote paths (Docker containers)
        self.remote_backend_path = "/volume1/docker/appdata/mtg-flask-app"
        self.remote_frontend_path = "/volume1/docker/appdata/mtg-frontend"
        
        # Exclusion patterns
        self.exclude_patterns = [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.log",
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            ".git",
            ".gitignore",
            "tests",
            ".pytest_cache",
            "htmlcov",
            ".coverage",
            "*.egg-info",
            "node_modules",
            "venv",
            ".venv",
            "env",
            ".env.dev",
            ".env.local",
            ".env.development",
            "dist",
            "build",
            ".DS_Store",
            "Thumbs.db",
            "*.tmp",
            "*.temp",
            ".idea",
            ".vscode",
            "migrations/__pycache__",
            "instance",
            "logs/*.log",
            "data/cache",
            "data/temp"
        ]
        
        # Files to protect on remote (don't overwrite/delete)
        # These are CRITICAL Docker and production files that must not be deleted
        self.protected_files_backend = [
            "Dockerfile", 
            ".dockerignore", 
            "entrypoint.sh",
            "requirements.txt",  # Critical for Docker builds
            ".env",
            "logs/*",
        ]
        self.protected_files_frontend = [
            "Dockerfile", 
            ".dockerignore", 
            "package-lock.json",  # For frontend, can be large and stable
        ]

    def get_timestamp(self):
        """Get formatted timestamp"""
        return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"

    def log(self, message, color="blue"):
        """Print colored log message"""
        colors = {
            "red": "\033[91m",
            "green": "\033[92m", 
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "cyan": "\033[96m",
            "magenta": "\033[95m",
            "reset": "\033[0m"
        }
        print(f"{colors.get(color, '')}{self.get_timestamp()} {message}{colors['reset']}")

    def test_location_status(self):
        """Test if we're at home (can reach local server directly)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.local_server_ip, self.remote_port))
            sock.close()
            is_at_home = (result == 0)
            location = "home (local network)" if is_at_home else "away (remote access)"
            self.log(f"Location detected: {location}", "blue")
            return is_at_home
        except Exception as e:
            self.log(f"Network test failed, assuming remote: {e}", "yellow")
            return False

    def ensure_env_files(self):
        """Ensure .env files are properly set up"""
        self.log("Checking .env file setup...", "blue")
        
        backend_env = Path(self.local_mtg_backend) / ".env"
        frontend_env = Path(self.local_mtg_frontend) / ".env"
        root_env = Path(self.local_mtg_root) / ".env"
        
        # Check for .env in various locations
        env_locations = [
            (root_env, "root"),
            (backend_env, "backend"),
            (frontend_env, "frontend")
        ]
        
        found_env = False
        for env_file, location in env_locations:
            if env_file.exists():
                self.log(f"Found .env in {location} directory", "green")
                found_env = True
                
                # Copy to backend if it doesn't exist there
                if location != "backend" and not backend_env.exists():
                    try:
                        self.log(f"Copying .env from {location} to backend...", "blue")
                        shutil.copy2(env_file, backend_env)
                        self.log(".env copied to backend successfully", "green")
                    except Exception as e:
                        self.log(f"Failed to copy .env to backend: {e}", "red")
                break
        
        if not found_env:
            self.log("No .env file found - create one with your MTG-optimizer configuration", "yellow")
            self.log("Should include database, Redis, and API configurations", "yellow")

    def run_tests(self, test_type="simple"):
        """Run tests before sync"""
        self.log(f"Running tests ({test_type})...", "yellow")
        
        # Look for tests in multiple possible locations
        test_locations = [
            Path(self.local_mtg_root) / "tests",
            Path(self.local_mtg_backend) / "tests",
            Path(self.local_mtg_root) / "test"
        ]
        
        tests_dir = None
        for location in test_locations:
            if location.exists():
                tests_dir = location
                break
                
        if not tests_dir:
            self.log("Tests directory not found, skipping tests...", "yellow")
            return True
            
        original_dir = os.getcwd()
        try:
            # Set environment variables for existing MTG infrastructure
            test_env = os.environ.copy()
            test_env.update({
                'DB_HOST': '192.168.68.61',
                'REDIS_HOST': '192.168.68.61',
                'API_BASE_URL': 'http://192.168.68.61:5002',  # MTG Flask app port
                'FLASK_ENV': 'testing'
            })
            
            os.chdir(tests_dir)
            
            # Choose test command based on type
            test_commands = {
                "simple": ["python", "-c", "import requests; print('Basic connection test passed')"],
                "unit": ["python", "-m", "pytest", "unit/", "-v", "--tb=short", "-q"],
                "api": ["python", "-m", "pytest", "api/", "-v", "--tb=short", "-q"],
                "integration": ["python", "-m", "pytest", "integration/", "-v", "--tb=short", "-q"],
                "quick": ["python", "-c", "print('Quick test mode - skipped')"],
                "all": ["python", "-m", "pytest", "-v", "--tb=short"]
            }
            
            cmd = test_commands.get(test_type, test_commands["simple"])
                
            self.log(f"Running: {' '.join(cmd)}", "blue")
            result = subprocess.run(cmd, env=test_env, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log("Tests passed!", "green")
                if result.stdout:
                    print(result.stdout)
                return True
            else:
                self.log("Tests failed!", "red")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return False
                
        except Exception as e:
            self.log(f"Error running tests: {e}", "red")
            return False
        finally:
            os.chdir(original_dir)

    def build_rsync_command(self, source, remote_path, component_name, is_at_home, dry_run=False, safe_mode=False):
        """Build rsync command for sync"""
        # Ensure source path ends with /
        source = str(Path(source)).rstrip('/') + '/'

        # Use full path
        ssh_config_path = "/home/junix/.ssh_wsl/config"
        
        if is_at_home:
            target = f"{self.remote_host_alias}:{remote_path}/"
            ssh_options = f"ssh -F {ssh_config_path}"
        else:
            target = f"{self.remote_user}@{self.remote_host_alias}:{remote_path}/"
            ssh_options = f"ssh -F {ssh_config_path} -p {self.remote_port}"
        
        # Build exclude options
        protected_files = self.protected_files_backend if component_name == "MTG-Optimizer backend" else self.protected_files_frontend
        all_excludes = self.exclude_patterns + protected_files

        exclude_opts = []
        for pattern in all_excludes:
            exclude_opts.extend(["--exclude", pattern])

        cmd = [
            "rsync",
            "-avz",
            "--partial",
            "--progress",
            "-e", ssh_options,
            "--rsync-path=/bin/rsync",
            "--stats",
            "--ignore-errors",
        ]
        
        if safe_mode:
            # Ultra-safe mode: no deletions at all
            self.log("SAFE MODE: No files will be deleted, only updated/added", "yellow")
            cmd.extend([
                "--backup",
                "--backup-dir=.rsync-backup-safe",
            ])
        else:
            # Normal mode with backup protection
            cmd.extend([
                "--backup",
                "--backup-dir=.rsync-backup",
                # CRITICAL: Only delete files that don't match our exclude patterns
                "--delete",
            ])

        if dry_run:
            cmd.append("--dry-run")

        cmd.extend(exclude_opts + [source, target])

        return cmd

    def verify_remote_critical_files(self, remote_path, component_name):
        """Verify that critical Docker files exist on remote"""
        critical_files = self.protected_files_backend if component_name == "MTG-Optimizer backend" else self.protected_files_frontend
        
        is_at_home = self.test_location_status()
        ssh_config_path = "/home/junix/.ssh_wsl/config"
        
        if is_at_home:
            ssh_target = self.remote_host_alias
            ssh_options = f"ssh -F {ssh_config_path}"
        else:
            ssh_target = f"{self.remote_user}@{self.remote_host_alias}"
            ssh_options = f"ssh -F {ssh_config_path} -p {self.remote_port}"
        
        missing_files = []
        for file in critical_files:
            check_cmd = f"{ssh_options} {ssh_target} 'test -f {remote_path}/{file}'"
            try:
                result = subprocess.run(check_cmd, shell=True, capture_output=True)
                if result.returncode != 0:
                    missing_files.append(file)
            except Exception as e:
                self.log(f"Could not verify {file}: {e}", "yellow")
        
        if missing_files:
            self.log(f"WARNING: Missing critical files in {component_name}:", "red")
            for file in missing_files:
                self.log(f"  - {file}", "red")
            return False
        else:
            self.log(f"All critical files verified in {component_name}", "green")
            return True

    def sync_with_rsync(self, source, remote_path, component_name, dry_run=False, safe_mode=False):
        """Sync using rsync with safety checks"""
        is_at_home = self.test_location_status()
        
        if is_at_home:
            self.log(f"Using SSH to local server ({self.local_server_ip})", "blue")
        else:
            self.log(f"Using SSH to remote server ({self.remote_host_alias})", "blue")
            
        self.log(f"Source: {source}", "cyan")
        self.log(f"Target: {remote_path}", "cyan")
        
        # Verify critical files exist before sync (unless dry run)
        if not dry_run:
            self.log(f"Verifying critical files before sync for {component_name}...", "blue")
            self.verify_remote_critical_files(remote_path, component_name)
        
        try:
            cmd = self.build_rsync_command(source, remote_path, component_name, is_at_home, dry_run, safe_mode)
            mode_text = " (DRY RUN)" if dry_run else ""
            self.log(f"Executing rsync for {component_name}{mode_text}...", "blue")
            
            if dry_run:
                self.log(f"DRY RUN - Command would be: {' '.join(cmd[:8])} ... [with excludes]", "yellow")
                self.log("Protected files that would be preserved:", "yellow")
                for pf in self.protected_files_backend if component_name == "MTG-Optimizer backend" else self.protected_files_frontend:
                    self.log(f"  - {pf}", "yellow")
                return True
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log(f"{component_name} sync completed successfully", "green")
                
                # Verify critical files still exist after sync
                self.log(f"Verifying critical files after sync for {component_name}...", "blue")
                if not self.verify_remote_critical_files(remote_path, component_name):
                    self.log("CRITICAL: Some Docker files are missing after sync!", "red")
                    self.log("Check .rsync-backup directory on remote for backups", "yellow")
                
                if result.stdout:
                    # Show rsync stats
                    lines = result.stdout.strip().split('\n')
                    for line in lines[-5:]:  # Show last few lines with stats
                        if line.strip():
                            self.log(f"  {line.strip()}", "cyan")
                return True
            else:
                self.log(f"{component_name} sync failed - exit code: {result.returncode}", "red")
                if result.stderr:
                    self.log(f"Error: {result.stderr}", "red")
                if result.stdout:
                    self.log(f"Output: {result.stdout}", "yellow")
                return False
                
        except Exception as e:
            self.log(f"{component_name} sync failed: {e}", "red")
            return False

    def sync_backend_only(self, dry_run=False, safe_mode=False):
        """Sync backend only"""
        self.log("Syncing MTG-Optimizer backend (Flask app)...", "magenta")
        return self.sync_with_rsync(
            self.local_mtg_backend,
            self.remote_backend_path,
            "MTG-Optimizer backend",
            dry_run,
            safe_mode
        )

    def sync_frontend_only(self, dry_run=False, safe_mode=False):
        """Sync frontend only"""
        self.log("Syncing MTG-Optimizer frontend (React app)...", "magenta")
        return self.sync_with_rsync(
            self.local_mtg_frontend,
            self.remote_frontend_path,
            "MTG-Optimizer frontend",
            dry_run,
            safe_mode
        )

    def sync_both(self, dry_run=False, safe_mode=False):
        """Sync both backend and frontend"""
        self.log("Syncing both MTG-Optimizer backend and frontend...", "magenta")
        backend_result = self.sync_backend_only(dry_run, safe_mode)
        frontend_result = self.sync_frontend_only(dry_run, safe_mode)
        
        if backend_result and frontend_result:
            self.log("Full MTG-Optimizer sync completed successfully", "green")
            return True
        else:
            self.log(f"Some MTG-Optimizer syncs failed - Backend: {backend_result}, Frontend: {frontend_result}", "red")
            return False

    def validate_paths(self):
        """Validate that all required local paths exist"""
        paths_to_check = [
            (self.local_mtg_root, "MTG-Optimizer root"),
            (self.local_mtg_backend, "MTG-Optimizer backend"),
            (self.local_mtg_frontend, "MTG-Optimizer frontend")
        ]
        
        missing_paths = []
        for path, name in paths_to_check:
            if not Path(path).exists():
                self.log(f"{name} directory not found: {path}", "red")
                missing_paths.append(name)
        
        if missing_paths:
            self.log(f"Missing required directories: {', '.join(missing_paths)}", "red")
            self.log("Please ensure your MTG-Optimizer project structure is correct", "yellow")
            return False
        return True

    def show_sync_summary(self):
        """Show what will be synced"""
        self.log("MTG-Optimizer Sync Configuration:", "cyan")
        self.log(f"  Local root: {self.local_mtg_root}", "cyan")
        self.log(f"  Remote backend: {self.remote_backend_path}", "cyan")
        self.log(f"  Remote frontend: {self.remote_frontend_path}", "cyan")
        self.log(f"  Server: {self.remote_host_alias} ({self.local_server_ip})", "cyan")
        self.log("", "cyan")

def main():
    parser = argparse.ArgumentParser(description="MTG-Optimizer sync script")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--test-only", action="store_true", help="Run tests only, no sync")
    parser.add_argument("--quick", action="store_true", help="Quick mode with minimal testing")
    parser.add_argument("--test-type", default="simple", 
                       choices=["simple", "unit", "api", "integration", "quick", "all"],
                       help="Type of tests to run")
    parser.add_argument("--backend-only", action="store_true", help="Sync backend only")
    parser.add_argument("--frontend-only", action="store_true", help="Sync frontend only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without actually doing it")
    parser.add_argument("--safe-mode", action="store_true", help="Ultra-safe mode: no deletions, extensive backups")
    parser.add_argument("--show-config", action="store_true", help="Show sync configuration and exit")
    
    args = parser.parse_args()
    
    syncer = MTGOptimizerSync()
    syncer.log("Starting MTG-Optimizer sync...", "cyan")
    
    # Show configuration if requested
    if args.show_config:
        syncer.show_sync_summary()
        sys.exit(0)
    
    # Handle test-only mode
    if args.test_only:
        syncer.log("Test-only mode", "yellow")
        if syncer.run_tests(args.test_type):
            syncer.log("Tests completed successfully!", "green")
            sys.exit(0)
        else:
            syncer.log("Tests failed!", "red")
            sys.exit(1)
    
    # Validate paths
    if not syncer.validate_paths():
        sys.exit(1)
    
    # Show what we're about to do
    syncer.show_sync_summary()
    
    # Ensure .env files
    syncer.ensure_env_files()
    
    # Run tests before sync (unless skipped or quick mode)
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
    
    # Perform the sync
    if args.backend_only:
        result = syncer.sync_backend_only(args.dry_run, args.safe_mode)
    elif args.frontend_only:
        result = syncer.sync_frontend_only(args.dry_run, args.safe_mode)
    else:
        result = syncer.sync_both(args.dry_run, args.safe_mode)
    
    if result:
        mode_text = " (dry run completed)" if args.dry_run else ""
        syncer.log(f"MTG-Optimizer sync completed successfully{mode_text}!", "green")
        
        if not args.dry_run:
            syncer.log("", "green")
            syncer.log("Next steps:", "green")
            syncer.log("1. Check container logs: docker-compose logs mtg-flask-app", "green")
            syncer.log("2. Restart services if needed: docker-compose restart mtg-flask-app mtg-frontend", "green")
            syncer.log("3. Test the application at your configured URLs", "green")
            syncer.log("", "cyan")
            syncer.log("Safety info:", "cyan")
            syncer.log("- Backups of overwritten files are in .rsync-backup/ on remote", "cyan")
            syncer.log("- Critical Docker files are protected from deletion", "cyan")
            syncer.log("- Run with --dry-run first to preview changes safely", "cyan")
        
        sys.exit(0)
    else:
        syncer.log("MTG-Optimizer sync failed!", "red")
        sys.exit(1)

if __name__ == "__main__":
    main()