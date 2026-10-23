import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-user-jwt-secret")
