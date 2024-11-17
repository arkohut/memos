import subprocess
import threading
import sys
import signal
from colorama import init, Fore
import time

# Initialize colorama for Windows compatibility
init()

# Define colors for each process
COLORS = [Fore.GREEN, Fore.BLUE, Fore.YELLOW]


def run_process(command, color):
    """Run a single process with colored output."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"{color}{command[0]}: {line.rstrip()}{Fore.RESET}")

        return process.poll()

    except Exception as e:
        print(f"{Fore.RED}Error in {command[0]}: {str(e)}{Fore.RESET}")
        return 1


def main():
    # Define your three commands here
    commands = [
        ["python", "memos_app.py", "record"],
        ["python", "memos_app.py", "serve"],
        ["python", "memos_app.py", "watch"],
    ]

    # Create threads for each process
    threads = []
    processes = []

    def signal_handler(signum, frame):
        print(f"\n{Fore.RED}Interrupting all processes...{Fore.RESET}")
        for process in processes:
            process.terminate()
        sys.exit(0)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run processes in separate threads
    for i, command in enumerate(commands):
        time.sleep(3)
        color = COLORS[i % len(COLORS)]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        processes.append(process)
        thread = threading.Thread(target=run_process, args=(command, color))
        thread.start()
        threads.append(thread)
        print(f"Started {command[0]} with PID {process.pid}")

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check for any failed processes
    failed_processes = [process for process in processes if process != 0]
    if failed_processes:
        print(f"\n{Fore.RED}Some processes failed: {failed_processes}{Fore.RESET}")
    else:
        print(f"\n{Fore.GREEN}All processes completed successfully!{Fore.RESET}")


if __name__ == "__main__":
    main()
