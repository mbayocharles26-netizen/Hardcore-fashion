from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.response import Response

from .cart_service import merge_session_cart
from .jwt_auth import UsernameOrEmailTokenObtainPairSerializer
from .throttles import LoginRateThrottle


class UsernameOrEmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = UsernameOrEmailTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # A guest cart is keyed to the same Django session cookie sent with
        # this login request. Merge it only after credentials are valid.
        merge_session_cart(serializer.user, request.session.session_key)
        return Response(serializer.validated_data, status=200)

