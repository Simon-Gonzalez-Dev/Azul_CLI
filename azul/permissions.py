"""Permission system for file operations."""

import click
from typing import Optional, List, Tuple
from dataclasses import dataclass

from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


@dataclass
class DiffHunk:
    """Represents a single hunk in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]
    content: str


class PermissionManager:
    """Manages permissions for file operations."""
    
    def __init__(self):
        """Initialize permission manager."""
        self.config = get_config_manager()
        self.formatter = get_formatter()
    
    def request_permission(
        self,
        action: str,
        description: str,
        show_diff: Optional[str] = None
    ) -> bool:
        """
        Request permission for an action.
        
        Args:
            action: Action description (e.g., "edit file")
            description: Detailed description of what will happen
            show_diff: Optional diff preview to show
            
        Returns:
            True if permission granted, False otherwise
        """
        if show_diff:
            self.formatter.print_info("\nProposed Changes:")
            self.formatter.print_diff(show_diff)
        
        self.formatter.print_info(description)
        
        # Check if auto-approve is enabled
        auto_approve = self.config.get("permission_defaults", {}).get("auto_approve", False)
        if auto_approve:
            self.formatter.print_info("Auto-approve is enabled. Proceeding...")
            return True
        
        return click.confirm(f"Do you want to {action}?", default=False)
    
    def request_edit_permission(
        self,
        file_path: str,
        diff_preview: str
    ) -> bool:
        """
        Request permission to edit a file.
        
        Args:
            file_path: Path to file being edited
            diff_preview: Color-coded diff preview
            
        Returns:
            True if permission granted, False otherwise
        """
        return self.request_permission(
            action="apply these changes",
            description=f"This will modify: {file_path}",
            show_diff=diff_preview
        )
    
    def request_file_creation_permission(
        self,
        file_path: str,
        preview: Optional[str] = None,
        language: str = "text"
    ) -> bool:
        """
        Request permission to create a file.
        
        Args:
            file_path: Path to file being created
            preview: Optional preview of file content
            language: Programming language for syntax highlighting
            
        Returns:
            True if permission granted, False otherwise
        """
        if preview:
            self.formatter.print_info(f"\nNew file: {file_path}")
            self.formatter.print_code_block(preview, language)
        
        return self.request_permission(
            action="create this file",
            description=f"This will create: {file_path}"
        )
    
    def request_cherry_pick_permission(
        self,
        hunks: List[DiffHunk]
    ) -> List[bool]:
        """
        Request permission for individual hunks (cherry-picking).
        
        Args:
            hunks: List of diff hunks
            
        Returns:
            List of booleans indicating which hunks to apply
        """
        if not self.config.get("enable_cherry_picking", False):
            # If cherry-picking not enabled, return all True or False based on single permission
            all_content = "\n".join(hunk.content for hunk in hunks)
            granted = self.request_edit_permission("file", all_content)
            return [granted] * len(hunks)
        
        results = []
        click.echo("\n" + "="*70)
        click.echo("Cherry-pick Changes (apply individual sections)")
        click.echo("="*70)
        
        for i, hunk in enumerate(hunks, 1):
            click.echo(f"\n--- Hunk {i}/{len(hunks)} ---")
            click.echo(hunk.content)
            apply = click.confirm(f"Apply hunk {i}?", default=True)
            results.append(apply)
        
        click.echo("="*70 + "\n")
        return results


# Global permission manager instance
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get the global permission manager instance."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager

