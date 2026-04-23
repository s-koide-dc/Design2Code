class MathUtils:
    @staticmethod
    def add(a, b):
        """Adds two numbers."""
        return a + b

    @staticmethod
    def divide(a, b):
        """Divides a by b. Raises ValueError if b is 0."""
        if b == 0:
            raise ValueError("Division by zero")
        return a / b
