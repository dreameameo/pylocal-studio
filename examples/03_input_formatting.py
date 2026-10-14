# User input and string formatting
name = input("Enter your name: ")
age = int(input("Enter your age: "))
print(f"Hello, {name.title()}! In 10 years you will be {age + 10}.")
print("Name reversed:", name[::-1], "| upper:", name.upper())
