#!/bin/bash
# This script automates the creation of a new module.
# It's a placeholder to illustrate the concept. A real implementation
# would be more robust and might be a Python script instead.

MODULE_NAME=$1
LANGUAGE=$2 # "js" or "py"

if [ -z "$MODULE_NAME" ] || [ -z "$LANGUAGE" ]; then
  echo "Usage: $0 <module_name> <language>"
  echo "  language: 'js' for JavaScript or 'py' for Python"
  exit 1
fi

echo "Creating new module: $MODULE_NAME ($LANGUAGE)"

# 1. Create directory
mkdir -p "src/$MODULE_NAME"

# 2. Create source file based on language
if [ "$LANGUAGE" == "js" ]; then
  touch "src/$MODULE_NAME/index.js"
  touch "tests/test_$MODULE_NAME.js"
elif [ "$LANGUAGE" == "py" ]; then
  touch "src/$MODULE_NAME/index.py"
  touch "tests/test_$MODULE_NAME.py"
else
  echo "Error: Unsupported language '$LANGUAGE'"
  exit 1
fi

# 3. Create design document from template
TEMPLATE_PATH="AIFiles/templates/design_document.md"
NEW_DESIGN_DOC_PATH="src/$MODULE_NAME/${MODULE_NAME}.design.md"
cp "$TEMPLATE_PATH" "$NEW_DESIGN_DOC_PATH"
# Replace placeholder in the new design doc
# (This would be more robust with sed or another tool)
echo "Remember to replace '[Module Name]' in $NEW_DESIGN_DOC_PATH with '$MODULE_NAME'"

# 4. Update ai_project_map.json
# This part is complex and is best handled by a dedicated Python script.
# The script would read the JSON, append the new module info, and write it back.
echo "IMPORTANT: You must now manually update 'ai_project_map.json' with the new module information."
echo "In a real implementation, this script would call another tool to do this automatically."

echo "Module '$MODULE_NAME' created. Please fill in the file contents."

exit 0
