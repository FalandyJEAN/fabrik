SECRET_KEY=${secret_key}
DATABASE_URL=${db_url}
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080
# Background tasks (ARQ + Redis). Si Redis est down, l'API marche quand meme
# (les routes qui veulent enqueue renvoient 503 Service Unavailable).
REDIS_URL=redis://localhost:6379
