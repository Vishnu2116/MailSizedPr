# run_db_setup.py
from app.db import Base, engine
from app.models import models

print("🔧 Creating tables...")
Base.metadata.create_all(bind=engine)
print("✅ Done.")
