#!/bin/zsh

# Specify the directory you want to process
# 
# Check if directory path is passed as an argument
if [[ -z "$1" ]]; then
  echo "Usage: $0 <directory_path>"
  exit 1
fi

# Set the directory path from the argument
dir_path="$1"
files=$(ls $1)

# Use a while loop to iterate over files in the directory
for file in $files; do
  # Check if it is a file
  if [[ -f $file ]]; then
    echo "Contents of $file:"
    cat "$file" # Print the content of the file
    echo "\n---------------------------\n" # Separator for readability
  fi
done

