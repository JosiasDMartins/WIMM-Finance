# finances/templatetags/math_filters.py

from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def sub(value, arg):
    """
    Subtracts the argument from the value.
    Ensures that values are converted to Decimal for precise math.
    """
    try:
        # Ensure both are converted to Decimal before subtraction
        return Decimal(value) - Decimal(arg)
    except (ValueError, TypeError, InvalidOperation):
        # Return 0 if conversion fails
        return 0

@register.filter
def divide(value, arg):
    """
    Divides the value by the argument. 
    Handles division by zero by returning 0.
    Ensures that values are converted to Decimal for precise math.
    """
    try:
        # Check for None, 0, or '0' values for the divisor
        if arg in (None, 0, '0', Decimal(0)):
            return 0
        
        # Convert to Decimal for accurate financial calculations
        return Decimal(value) / Decimal(arg)
    except (ValueError, TypeError, InvalidOperation):
        # Catches conversion errors etc.
        return 0

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument.
    Ensures that values are converted to Decimal for precise math.
    """
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError, InvalidOperation):
        return 0