import phonenumbers
from django.core.exceptions import ValidationError


def validate_uk_phone_number(value):
    try:
        parsed_number = phonenumbers.parse(value, "GB")
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValidationError(f"'{value}' is not a valid UK phone number.")
        return parsed_number
    except phonenumbers.NumberParseException as e:
        raise ValidationError(f"'{value}' is not a valid phone number: {str(e)}")


def format_uk_phone_number(value):
    parsed_number = validate_uk_phone_number(value)
    return phonenumbers.format_number(
        parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )
