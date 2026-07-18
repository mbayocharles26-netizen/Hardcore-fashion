import re

from django.contrib.auth.models import User
from rest_framework import serializers

_USERNAME_RE = re.compile(r'^[\w.@+\-]+$')  # same chars Django allows, explicit


class _StrongPasswordMixin:
    def validate_strong_password(self, password: str):
        errors = []

        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not any(c.isupper() for c in password):
            errors.append('Password must include at least one uppercase letter.')
        if not any(c.islower() for c in password):
            errors.append('Password must include at least one lowercase letter.')
        if not any(c.isdigit() for c in password):
            errors.append('Password must include at least one number.')
        if not any(not c.isalnum() for c in password):
            errors.append('Password must include at least one special symbol (e.g. !@#$%^&*).')

        if errors:
            raise serializers.ValidationError(errors)
        return password


class RequestSignupOtpSerializer(_StrongPasswordMixin, serializers.Serializer):
    ROLE_CHOICES = ['customer', 'vendor']

    username = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField(max_length=254)

    def validate_username(self, value):
        if not _USERNAME_RE.match(value):
            raise serializers.ValidationError('Username contains invalid characters.')
        return value
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default='customer')
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        return self.validate_strong_password(value)

    def validate(self, attrs):
        # Double entry check (backend-enforced)
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs



class VerifySignupOtpSerializer(_StrongPasswordMixin, serializers.Serializer):
    ROLE_CHOICES = ['customer', 'vendor']

    username = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField(max_length=254)

    def validate_username(self, value):
        if not _USERNAME_RE.match(value):
            raise serializers.ValidationError('Username contains invalid characters.')
        return value
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default='customer')
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_password(self, value):
        return self.validate_strong_password(value)

    def validate(self, attrs):
        # Double entry check (backend-enforced)
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs




class RequestForgotPasswordOtpSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class VerifyForgotPasswordOtpSerializer(_StrongPasswordMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    new_password = serializers.CharField(write_only=True)
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_new_password(self, value):
        return self.validate_strong_password(value)


