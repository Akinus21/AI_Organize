import asyncio
import AI_Organize.cli.organize as organize_cli


def main():
    # Run update check at start (non-blocking if you want, or blocking)
    #from akinus.utils.update import update
    #asyncio.run(update.perform_update())

    # Your existing CLI logic
    asyncio.run(organize_cli.run())
