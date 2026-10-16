from httpx import AsyncClient


async def test_cart_checkout_and_payment_flow(
    client: AsyncClient, admin_headers: dict
):
    """Test adding a movie to cart, checking out, confirming payment, and duplicate purchase prevention."""
    cert = (await client.post("/api/v1/movies/certifications", headers=admin_headers, json={"name": "R"})).json()
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

    cart_res = await client.post(
        "/api/v1/cart/items",
        headers=admin_headers,
        json={"movie_id": movie_id},
    )
    assert cart_res.status_code == 201
    assert cart_res.json()["total_items"] == 1
    assert cart_res.json()["total_price"] == "19.99"

    checkout_res = await client.post("/api/v1/orders/checkout", headers=admin_headers)
    assert checkout_res.status_code == 201
    order_data = checkout_res.json()
    order_id = order_data["id"]
    assert order_data["status"] == "PENDING"

    empty_cart = await client.get("/api/v1/cart", headers=admin_headers)
    assert empty_cart.json()["total_items"] == 0

    pay_res = await client.post(
        f"/api/v1/orders/{order_id}/confirm-payment", headers=admin_headers
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "PAID"

    dup_cart_res = await client.post(
        "/api/v1/cart/items",
        headers=admin_headers,
        json={"movie_id": movie_id},
    )
    assert dup_cart_res.status_code == 400
