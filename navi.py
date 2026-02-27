import os
import sys
import threading
import pyfiglet
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import clear
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich.panel import Panel

console = Console()

# ---------------------------------------------------------------------------
# 1. CORE INDEXING & CACHING LOGIC
# ---------------------------------------------------------------------------
class DriveIndex:
    def __init__(self, root_drive="D:\\"):
        self.root_drive = root_drive
        self.folders = []
        self.files = []
        self.is_ready = False

    def build_index(self):
        """Scans the drive and caches paths in memory for instant searching."""
        if not os.path.exists(self.root_drive):
            console.print(f"[bold red]Error: Drive {self.root_drive} not found.[/bold red]")
            self.is_ready = True
            return

        for root, dirs, files in os.walk(self.root_drive):
            # Cache folders (storing full paths)
            for d in dirs:
                self.folders.append(os.path.join(root, d))
            # Cache files
            for f in files:
                self.files.append(os.path.join(root, f))

        self.is_ready = True

# ---------------------------------------------------------------------------
# 2. AUTO-COMPLETER FOR PROMPT_TOOLKIT
# ---------------------------------------------------------------------------
class FolderCompleter(Completer):
    def __init__(self, index_cache):
        self.index_cache = index_cache

    def get_completions(self, document, complete_event):
        word_before_cursor = document.text_before_cursor.lower()
        if not word_before_cursor or not self.index_cache.is_ready:
            return

        # Filter cached folders based on user input (Partial matching)
        # Limit to 15 results to keep the UI snappy
        matches = [f for f in self.index_cache.folders if word_before_cursor in os.path.basename(f).lower()]

        for match in matches[:15]:
            # Yield completion. start_position replaces the currently typed text with the full path
            yield Completion(match, start_position=-len(word_before_cursor), display=os.path.basename(match), display_meta=match)

# ---------------------------------------------------------------------------
# 3. UI & COMMAND HANDLING
# ---------------------------------------------------------------------------
def display_banner():
    """Renders a colorful, patterned ASCII banner."""
    ascii_art = pyfiglet.figlet_format("Hi SOMS", font="slant")

    # Create a gradient/pattern effect using Rich
    styled_text = Text()
    colors = ["cyan", "magenta", "blue", "green", "yellow"]
    for i, char in enumerate(ascii_art):
        styled_text.append(char, style=f"bold {colors[i % len(colors)]}")

    panel = Panel(styled_text, title="[bold white]Professional File Navigator[/bold white]", border_style="bright_blue")
    console.print(panel)

def search_files(index_cache, query):
    """Searches files and displays them in a structured Rich Table."""
    query = query.lower()
    matches = [f for f in index_cache.files if query in os.path.basename(f).lower()][:20]

    if not matches:
        console.print(f"[yellow]No files found matching '{query}'.[/yellow]")
        return

    table = Table(title=f"File Search Results for '{query}' (Showing top 20)", style="cyan")
    table.add_column("File Name", style="bold green", no_wrap=True)
    table.add_column("Full Path", style="dim white")
    table.add_column("Extension", justify="right", style="magenta")

    for match in matches:
        name = os.path.basename(match)
        ext = os.path.splitext(name)[1] or "File"
        table.add_row(name, match, ext)

    console.print(table)
    console.print("[dim]Use the 'open <full_path>' command to launch any of these files.[/dim]")

def main():
    clear()
    display_banner()

    target_drive = "D:\\"
    index_cache = DriveIndex(target_drive)

    # Run indexing in a background thread while showing a loading spinner
    console.print(f"[dim]Initializing smart index for {target_drive}...[/dim]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Caching file system for instant search...", total=None)

        index_thread = threading.Thread(target=index_cache.build_index)
        index_thread.start()
        index_thread.join() # Wait for index to finish before allowing input

    console.print("[bold green]Ready![/bold green] Type a folder name to auto-complete, 'search <name>' for files, or 'help'.\n")

    # Set up prompt_toolkit session
    session = PromptSession(
        history=InMemoryHistory(),
        completer=FolderCompleter(index_cache),
        complete_while_typing=True
    )

    previous_dir = None

    while True:
        try:
            # The interactive prompt
            user_input = session.prompt("SOMS-Nav> ").strip()

            if not user_input:
                continue

            cmd_parts = user_input.split(" ", 1)
            command = cmd_parts[0].lower()

            # Commands
            if command in ['exit', 'quit']:
                console.print("[bold yellow]Shutting down navigator. Goodbye, SOMS![/bold yellow]")
                break
            elif command == 'clear':
                clear()
                display_banner()
            elif command == 'help':
                console.print("[bold cyan]Commands:[/bold cyan]")
                console.print("  [green]<folder_path>[/green] : Type any folder name to see auto-suggestions, press Enter to open.")
                console.print("  [green]search <name>[/green]   : Search for specific files across the drive.")
                console.print("  [green]open <path>[/green]     : Open a specific file directly.")
                console.print("  [green]back[/green]            : Open the previously accessed directory.")
                console.print("  [green]clear[/green]           : Clear the terminal screen.")
                console.print("  [green]exit[/green]            : Close the application.\n")
            elif command == 'search' and len(cmd_parts) > 1:
                search_files(index_cache, cmd_parts[1])
            elif command == 'back':
                if previous_dir and os.path.exists(previous_dir):
                    console.print(f"Opening previous directory: [green]{previous_dir}[/green]")
                    os.startfile(previous_dir)
                else:
                    console.print("[yellow]No valid previous directory to go back to.[/yellow]")
            elif command == 'open' and len(cmd_parts) > 1:
                path = cmd_parts[1]
                if os.path.exists(path):
                    os.startfile(path)
                else:
                    console.print("[red]File not found.[/red]")
            else:
                # Default behavior: Treat input as a folder path to open
                if os.path.exists(user_input):
                    console.print(f"[bold green]Opening:[/bold green] {user_input}")
                    os.startfile(user_input)
                    previous_dir = user_input
                else:
                    console.print("[bold red]Invalid command or path not found.[/bold red] Type 'help' for options.")

        except KeyboardInterrupt:
            # Handles Ctrl+C
            console.print("\n[bold yellow]Process interrupted. Type 'exit' to quit.[/bold yellow]")
        except EOFError:
            # Handles Ctrl+D
            break
        except Exception as e:
            console.print(f"[bold red]An error occurred: {e}[/bold red]")

if __name__ == "__main__":
    main()
