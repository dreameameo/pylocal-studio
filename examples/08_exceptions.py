# Exception handling
for text in ["42", "abc", "0"]:
    try:
        value = 100 / int(text)
    except ValueError as error:
        print("Not a number:", error)
    except ZeroDivisionError as error:
        print("Error:", error)
    else:
        print("Result:", value)
    finally:
        print("done with", repr(text))
