import requests


# Function to download JSON data from a URL
def download_json_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error downloading JSON from URL: {e}")
        return None


# Function to convert a single step to Markdown
def step_to_markdown(step):
    markdown = f"### {step['name']}\n\n"
    markdown += f"* **Category**: {step['category']}\n"
    markdown += f"* **Version**: {step['version']}\n"
    markdown += f"* **Description**: {step['description']}\n"
    # markdown += f"* **Scope**: {step['scope']}\n"

    if step["input"]:
        markdown += "* **Input**: " + ", ".join(step["input"]) + "\n"

    if step["output"]:
        markdown += "* **Output**: " + ", ".join(step["output"]) + "\n"

    # Render configurables as a Markdown table
    if step["configurables"]:
        markdown += "\n**Configurables:**\n\n"
        markdown += "| Name | Default value | Description |\n"
        markdown += "| ---- | ----- | ----- |\n"
        for configurable in step["configurables"]:
            name = configurable["name"]
            value = configurable["value"]
            label = configurable["label"]
            markdown += f"| {name} | {value} | {label} |\n"

    markdown += "\n---\n\n"

    # markdown += f"* **Docs URL**: [{step['docs_url']}]({step['docs_url']})\n"
    # markdown += f"* **Source**: {step['source']}\n"

    markdown += "\n---\n\n"

    return markdown


steps_registry_url = "http://localhost:8000/api/workflow/registered-steps"
file_name = "docs/steps-library.md"
json_data = download_json_from_url(steps_registry_url)
# Convert all steps to Markdown
markdown_document = ""
# for step in json_data["steps"]:
#     if step["scope"] == "core_global":
#         markdown_document += step_to_markdown(step)

if json_data:
    # Group steps by category
    steps_by_category = {}
    for step in json_data["steps"]:
        if step["scope"] != "core_global":
            continue
        category = step["category"]
        if category not in steps_by_category:
            steps_by_category[category] = []
        steps_by_category[category].append(step)

    # Generate the Markdown document with table of contents and category sections
    markdown_document = "# Repositiry of Steps\n\n"
    markdown_document = "## Table of Contents\n\n"
    for category, category_steps in steps_by_category.items():
        markdown_document += f"* [{category}](#{category.lower().replace(' ', '-')})\n"

    markdown_document += "\n"

    for category, category_steps in steps_by_category.items():
        markdown_document += f"## {category}\n\n"
        for step in category_steps:
            markdown_document += step_to_markdown(step)

    # Save Markdown document to a file
    with open(file_name, "w") as f:
        f.write(markdown_document)

    print("Markdown document generated and saved as 'output.md'")
else:
    print("Unable to download JSON data from the URL.")

# Save Markdown document to a file
# with open("docs/steps-repository.md", "w") as f:
#     f.write(markdown_document)

# print("Markdown document generated and saved as 'output.md'")
