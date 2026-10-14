# Interactive command-line program (to-do list)
todos = []
while True:
    cmd = input("add <text> | list | quit > ").strip()
    if cmd.startswith("add "):
        todos.append(cmd[4:])
    elif cmd == "list":
        for i, t in enumerate(todos, 1):
            print(f"{i}. {t}")
    elif cmd == "quit":
        print("Bye!")
        break
    else:
        print("Unknown command")
