import asyncio
from pathlib import Path
import AI_Organize.cli.organize as organize_cli


def main():
    # Run update check at start (non-blocking if you want, or blocking)
    #from akinus.utils.update import update
    #asyncio.run(update.perform_update())

    # Your existing CLI logic
    curr_dir = Path.cwd().resolve()
    asyncio.run(
        organize_cli.run(
            project_root=curr_dir,
            max_depth=0, 
        )
    )