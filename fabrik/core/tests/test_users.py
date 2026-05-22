EMAIL = "testuser@example.com"
PASSWORD = "password123"


async def test_register(client):
    response = await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == EMAIL
    assert "password" not in data


async def test_register_duplicate_email(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    response = await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 409


async def test_login_success(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    response = await client.post("/users/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    response = await client.post("/users/login", json={"email": EMAIL, "password": "mauvais"})
    assert response.status_code == 401


async def test_get_me_without_token(client):
    response = await client.get("/users/me")
    assert response.status_code == 401


async def test_get_me_with_token(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    login = await client.post("/users/login", json={"email": EMAIL, "password": PASSWORD})
    token = login.json()["access_token"]
    response = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


async def test_refresh_token(client):
    await client.post("/users/", json={"email": EMAIL, "password": PASSWORD})
    login = await client.post("/users/login", json={"email": EMAIL, "password": PASSWORD})
    refresh_token = login.json()["refresh_token"]
    response = await client.post("/users/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
