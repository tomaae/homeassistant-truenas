import argparse
import json
import os


def find_manifest_file():
    """
    Search for manifest.json in the project directory.
    """
    for root, _, files in os.walk(os.getcwd()):
        if "manifest.json" in files:
            return os.path.join(root, "manifest.json")
    raise FileNotFoundError("manifest.json file not found in the project directory.")


def update_manifest_version(version):
    """
    Update the version in the manifest.json file.
    """
    try:
        manifest_path = find_manifest_file()
        print(f"Found manifest.json at: {manifest_path}")

        # Read the current manifest file
        with open(manifest_path, "r") as file:
            manifest_data = json.load(file)

        # Update the version
        manifest_data["version"] = version

        # Write the updated manifest back to the file
        with open(manifest_path, "w") as file:
            json.dump(manifest_data, file, indent=4)

        print(f"Successfully updated version to {version} in manifest.json.")
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"An error occurred: {e}")


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Update the version in the manifest.json file."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="The new version to set in the manifest.json file.",
    )
    args = parser.parse_args()

    # Update the manifest version
    update_manifest_version(args.version)


if __name__ == "__main__":
    main()
