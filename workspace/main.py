# Basic file operations (files live in the workspace/ folder)
with open("notes.txt", "w", encoding="utf-8") as f:
    f.write("line one\nline two\n")
with open("notes.txt", encoding="utf-8") as f:
    for number, line in enumerate(f, 1):
        print(number, line.rstrip())
