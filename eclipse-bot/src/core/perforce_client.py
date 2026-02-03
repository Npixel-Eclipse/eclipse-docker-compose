"""Perforce client wrapper for Eclipse Bot."""

import os
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class P4Config:
    """Perforce configuration from environment variables."""
    user: str = field(default_factory=lambda: os.getenv("P4USER", "ecl_server"))
    client: str = field(default_factory=lambda: os.getenv("P4CLIENT", "Server-Linux-Agent"))
    port: str = field(default_factory=lambda: os.getenv("P4PORT", "ECL-P4D4:1666"))


@dataclass
class P4File:
    """Perforce file info."""
    depot_path: str
    client_path: str
    action: str
    revision: int


class PerforceClient:
    """Perforce client wrapper.
    
    Configuration is loaded from environment variables:
        - P4USER: Perforce username
        - P4CLIENT: Client workspace name
        - P4PORT: Server address
    
    Usage:
        p4 = PerforceClient()
        
        # Sync files
        p4.sync()
        p4.sync("//Eclipse_Studio/Main/ProjectX/Source/...")
        
        # Get file info
        files = p4.files("//Eclipse_Studio/Main/ProjectX/Source/*.cpp")
        
        # Checkout and edit
        p4.edit("//Eclipse_Studio/Main/ProjectX/Source/MyFile.cpp")
        
        # Submit changes
        p4.submit("Fix bug in MyFile.cpp")
    """
    
    def __init__(self, config: Optional[P4Config] = None):
        self.config = config or P4Config()
        logger.info(f"P4 client initialized: {self.config.client}@{self.config.port}")
    
    def _run(self, *args: str, check: bool = True) -> str:
        """Run a p4 command."""
        cmd = [
            "p4",
            "-u", self.config.user,
            "-c", self.config.client,
            "-p", self.config.port,
            *args
        ]
        logger.debug(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        
        if check and result.returncode != 0:
            logger.error(f"P4 error: {result.stderr}")
            raise RuntimeError(f"P4 command failed: {result.stderr}")
        
        return result.stdout
    
    def sync(self, path: str = "//...") -> str:
        """Sync files from depot.
        
        Args:
            path: Depot path to sync (default: all)
            
        Returns:
            Sync output
        """
        output = self._run("sync", path)
        logger.info(f"Synced: {path}")
        return output
    
    def files(self, path: str) -> list[str]:
        """List files matching path pattern.
        
        Args:
            path: Depot path pattern
            
        Returns:
            List of depot file paths
        """
        output = self._run("files", path, check=False)
        files = []
        for line in output.strip().split("\n"):
            if line and "#" in line:
                depot_path = line.split("#")[0]
                files.append(depot_path)
        return files
    
    def edit(self, path: str) -> str:
        """Open file for edit.
        
        Args:
            path: Depot or client file path
            
        Returns:
            Edit output
        """
        output = self._run("edit", path)
        logger.info(f"Opened for edit: {path}")
        return output
    
    def add(self, path: str) -> str:
        """Add new file to depot.
        
        Args:
            path: Client file path
            
        Returns:
            Add output
        """
        output = self._run("add", path)
        logger.info(f"Added: {path}")
        return output
    
    def revert(self, path: str = "//...") -> str:
        """Revert changes.
        
        Args:
            path: Path to revert
            
        Returns:
            Revert output
        """
        output = self._run("revert", path)
        logger.info(f"Reverted: {path}")
        return output
    
    def submit(self, description: str) -> str:
        """Submit pending changes.
        
        Args:
            description: Changelist description
            
        Returns:
            Submit output
        """
        output = self._run("submit", "-d", description)
        logger.info(f"Submitted: {description}")
        return output
    
    def status(self) -> str:
        """Get opened files status.
        
        Returns:
            Status output
        """
        return self._run("opened", check=False)
    
    def info(self) -> str:
        """Get client info.
        
        Returns:
            Info output
        """
        return self._run("info")
    
    def diff(self, path: str = "//...") -> str:
        """Show diff of opened files.
        
        Args:
            path: Path to diff
            
        Returns:
            Diff output
        """
        return self._run("diff", path, check=False)
