import subprocess
import shlex
import sys

CMD = "govee2mqtt/target/debug/govee serve --govee-email hebardiansbehardians@gmail.com --govee-password 777Markofthebeast!"


def main() -> None:
    try:
        result = subprocess.run(shlex.split(CMD), capture_output=True, text=True)
    except FileNotFoundError as exc:
        print(f"Failed to run command: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
