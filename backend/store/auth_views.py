from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .throttles import LoginRateThrottle, OtpRateThrottle

from .email_service import send_otp_email
from .models import OTPVerification
from .otp import generate_otp, otp_expires_at, otp_hash
from .serializers_auth import (
    RequestForgotPasswordOtpSerializer,
    RequestSignupOtpSerializer,
    VerifyForgotPasswordOtpSerializer,
)


class RequestSignupOtpView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        serializer = RequestSignupOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        username = serializer.validated_data['username'].strip()

        if User.objects.filter(username__iexact=username).exists():
            return Response({'username': 'Username is already taken.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email__iexact=email).exists():
            return Response({'email': 'Email is already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        otp = generate_otp()
        OTPVerification.objects.filter(
            email__iexact=email,
            purpose=OTPVerification.PURPOSE_SIGNUP,
            verified_at__isnull=True,
        ).delete()
        OTPVerification.objects.create(
            email=email,
            purpose=OTPVerification.PURPOSE_SIGNUP,
            otp_hash=otp_hash(otp),
            expires_at=otp_expires_at(),
        )

        try:
            send_otp_email(to_email=email, otp_code=otp, subject='Your signup OTP')
        except Exception as exc:
            OTPVerification.objects.filter(
                email__iexact=email,
                purpose=OTPVerification.PURPOSE_SIGNUP,
                verified_at__isnull=True,
            ).delete()
            return Response(
                {
                    'detail': 'We could not send the OTP email right now. Please try again shortly.',
                    'error': str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'detail': 'OTP sent. Check your email.'},
            status=status.HTTP_200_OK,
        )


class RequestForgotPasswordOtpView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        serializer = RequestForgotPasswordOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            otp = generate_otp()
            OTPVerification.objects.filter(
                email__iexact=email,
                purpose=OTPVerification.PURPOSE_FORGOT_PASSWORD,
                verified_at__isnull=True,
            ).delete()
            OTPVerification.objects.create(
                email=email,
                purpose=OTPVerification.PURPOSE_FORGOT_PASSWORD,
                otp_hash=otp_hash(otp),
                expires_at=otp_expires_at(),
            )

            try:
                send_otp_email(to_email=email, otp_code=otp, subject='Your password reset OTP')
            except Exception as exc:
                OTPVerification.objects.filter(
                    email__iexact=email,
                    purpose=OTPVerification.PURPOSE_FORGOT_PASSWORD,
                    verified_at__isnull=True,
                ).delete()
                return Response(
                    {
                        'detail': 'We could not send the OTP email right now. Please try again shortly.',
                        'error': str(exc),
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )


        return Response(
            {'detail': 'If an account exists for that email, an OTP has been sent.'},
            status=status.HTTP_200_OK,
        )


class VerifyForgotPasswordOtpView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        serializer = VerifyForgotPasswordOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].strip().lower()
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        verification = (
            OTPVerification.objects.filter(
                email__iexact=email,
                purpose=OTPVerification.PURPOSE_FORGOT_PASSWORD,
                verified_at__isnull=True,
            )
            .order_by('-created_at')
            .first()
        )

        if not verification:
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.expires_at <= timezone.now():
            verification.delete()
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.attempts >= 5:
            verification.delete()
            return Response({'otp': 'Too many failed attempts. Request a new OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.otp_hash != otp_hash(otp):
            verification.attempts += 1
            verification.save(update_fields=['attempts'])
            return Response({'otp': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            verification.delete()
            return Response({'email': 'No account was found for this email.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        verification.verified_at = timezone.now()
        verification.save(update_fields=['verified_at'])

        return Response({'detail': 'Password reset successful.'}, status=status.HTTP_200_OK)
