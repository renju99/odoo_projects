import os

def export_folder_to_text(folder_path, output_filename="facilities_management_export.txt", exclude_dirs=None):
    if exclude_dirs is None:
        # Common directories to exclude in Odoo/Python projects
        exclude_dirs = ["__pycache__", ".git", ".idea", "venv", "node_modules"]

    with open(output_filename, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk(folder_path):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, folder_path)

                outfile.write(f"--- File: {relative_path} ---\n")
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
                    outfile.write("\n\n")  # Add a separator for readability
                except Exception as e:
                    outfile.write(f"--- Error reading {relative_path}: {e} ---\n\n")

if __name__ == "__main__":
    current_folder = os.path.dirname(os.path.abspath(__file__)) # Gets the script's directory
    export_folder_to_text(current_folder)
    print(f"Code from '{current_folder}' exported to facilities_management_export.txt")