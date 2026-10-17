from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


async def test_cart_checkout_and_stripe_webhook_flow(
    client: AsyncClient,
    admin_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    mock_email_sending: AsyncMock,
):
    """Test cart checkout, Stripe webhook validation, idempotency, and duplicate purchase prevention."""
    cert = (
        await client.post(
            "/api/v1/movies/certifications",
            headers=admin_headers,
            json={"name": "R"},
        )
    ).json()
    movie_res = await client.post(
        "/api/v1/movies",
        headers=admin_headers,
        json={
            "name": "Oppenheimer",
            "year": 2023,
            "time": 180,
            "imdb": 8.9,
            "votes": 900000,
            "description": "Biographical thriller.",
            "price": "19.99",
            "certification_id": cert["id"],
        },
    )
    movie_id = movie_res.json()["id"]

    # Add movie to shopping cart
    cart_res = await client.post(
        "/api/v1/cart/items",
        headers=admin_headers,
        json={"movie_id": movie_id},
    )
    assert cart_res.status_code == 201
    assert cart_res.json()["total_items"] == 1
    assert cart_res.json()["total_price"] == "19.99"

    # Checkout order
    checkout_res = await client.post("/api/v1/orders/checkout", headers=admin_headers)
    assert checkout_res.status_code == 201
    order_data = checkout_res.json()
    order_id = order_data["id"]
    stripe_session_id = order_data["stripe_session_id"]
    user_id = order_data["user_id"]
    assert order_data["status"] == "PENDING"

    # Verify cart is empty after checkout
    empty_cart = await client.get("/api/v1/cart", headers=admin_headers)
    assert empty_cart.json()["total_items"] == 0

    invalid_session_event = {
        "id": "evt_invalid_session",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_wrong_session_id",
                "status": "complete",
                "payment_status": "paid",
                "currency": "usd",
                "amount_total": 1999,
                "metadata": {"order_id": str(order_id), "user_id": str(user_id)},
            }
        },
    }
    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda payload, sig, secret: invalid_session_event,
    )
    bad_session_res = await client.post(
        "/api/v1/orders/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=sig"},
    )
    assert bad_session_res.status_code == 400

    unpaid_event = {
        "id": "evt_unpaid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": stripe_session_id,
                "status": "complete",
                "payment_status": "unpaid",
                "currency": "usd",
                "amount_total": 1999,
                "metadata": {"order_id": str(order_id), "user_id": str(user_id)},
            }
        },
    }
    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda payload, sig, secret: unpaid_event,
    )
    unpaid_res = await client.post(
        "/api/v1/orders/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=sig"},
    )
    assert unpaid_res.status_code == 400

    mock_email_sending.reset_mock()
    valid_event = {
        "id": "evt_valid_payment_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": stripe_session_id,
                "status": "complete",
                "payment_status": "paid",
                "currency": "usd",
                "amount_total": 1999,
                "metadata": {"order_id": str(order_id), "user_id": str(user_id)},
            }
        },
    }
    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda payload, sig, secret: valid_event,
    )
    webhook_res = await client.post(
        "/api/v1/orders/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=sig"},
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "success"
    assert mock_email_sending.call_count == 1

    # Verify order status is now PAID
    order_detail = await client.get(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert order_detail.json()["status"] == "PAID"

    dup_webhook_res = await client.post(
        "/api/v1/orders/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=sig"},
    )
    assert dup_webhook_res.status_code == 200
    assert dup_webhook_res.json()["status"] == "already_processed"
    assert mock_email_sending.call_count == 1

    dup_cart_res = await client.post(
        "/api/v1/cart/items",
        headers=admin_headers,
        json={"movie_id": movie_id},
    )
    assert dup_cart_res.status_code == 400
