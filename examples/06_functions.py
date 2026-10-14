# Functions and return values
def add(a, b):
    return a + b

def stats(*nums):
    return min(nums), max(nums), sum(nums) / len(nums)

print(add(10, 20))
print(stats(3, 9, 6))
