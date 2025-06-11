from app import app  # This imports your FastAPI app from app.py

# Vercel looks for a file-level variable named "app"
# This is what Vercel's @vercel/python uses as the ASGI handler
