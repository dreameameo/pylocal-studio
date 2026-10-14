# Simple calculator
a = float(input("First number: "))
op = input("Operator (+ - * /): ")
b = float(input("Second number: "))
try:
    result = {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[op]
    print(f"{a} {op} {b} = {result}")
except ZeroDivisionError:
    print("Cannot divide by zero")
except KeyError:
    print("Unknown operator:", op)
