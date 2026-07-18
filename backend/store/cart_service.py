from django.db import transaction

from .models import Cart, CartItem


def get_cart(request):
    """Return the current user's durable cart or the browser's guest cart."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def merge_session_cart(user, session_key):
    """Move a browser's guest cart into *user*'s durable cart exactly once."""
    with transaction.atomic():
        user_cart, _ = Cart.objects.get_or_create(user=user)
        if not session_key:
            return user_cart

        session_cart = (
            Cart.objects.select_for_update()
            .filter(user__isnull=True, session_key=session_key)
            .first()
        )
        if session_cart is None:
            return user_cart

        for guest_item in session_cart.items.select_related('product').all():
            user_item, created = CartItem.objects.get_or_create(
                cart=user_cart,
                product=guest_item.product,
                defaults={'quantity': guest_item.quantity},
            )
            if not created:
                user_item.quantity += guest_item.quantity
                user_item.save(update_fields=['quantity'])

        # Deleting the guest cart also removes its cart items, preventing this
        # browser session from being merged into the account a second time.
        session_cart.delete()
        return user_cart
