from django import forms
from django.core.validators import RegexValidator


PHONE_VALIDATOR = RegexValidator(
    regex=r"^[0-9+()\-\s]{7,20}$",
    message="Enter a valid phone number.",
)


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "John Doe"}),
    )
    customer_email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "john@example.com"}),
    )
    customer_phone = forms.CharField(
        max_length=30,
        required=False,
        validators=[PHONE_VALIDATOR],
        widget=forms.TextInput(attrs={"placeholder": "e.g. +1 555 123 4567"}),
    )
    customer_address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "123 Street Name"}),
    )

