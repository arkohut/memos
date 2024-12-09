import re


def convert_relative_paths_to_absolute(readme_path, output_path, base_url):
    # Read the content of the README.md file
    with open(readme_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Define a regex pattern to find relative paths for images and videos
    pattern = r'(!\[.*?\]\(|<img src="|<video src=")([^http].*?)(\)|")'

    # Replace relative paths with absolute paths
    updated_content = re.sub(
        pattern,
        lambda match: f"{match.group(1)}{base_url}{match.group(2)}{match.group(3)}",
        content,
    )

    # Write the updated content to README.pypi.md
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(updated_content)

    print(f"Updated README written to {output_path}")


# Define the paths and base URL
readme_path = "README.md"
output_path = "README.pypi.md"
base_url = "https://github.com/arkohut/pensieve/raw/master/"

# Run the conversion
convert_relative_paths_to_absolute(readme_path, output_path, base_url)
