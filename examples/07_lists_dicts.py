# Lists, tuples, dictionaries and sets
fruits = ["apple", "banana", "cherry"]
fruits.append("date")
point = (3, 4)
ages = {"Ann": 30, "Bob": 25}
ages["Cy"] = 41
unique = set([1, 2, 2, 3, 3])
print(fruits, point, unique)
for name, age in sorted(ages.items()):
    print(name, age)
