# app/routes/admin_auth.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
templates = Jinja2Templates(directory="admin_portal")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@mailsized.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# ────────────────────────────────
# Render Login Page
# ────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Serve the admin login form."""
    return templates.TemplateResponse("login.html", {"request": request})


# ────────────────────────────────
# Handle Login Submission
# ────────────────────────────────
@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Validate credentials and create session."""
    if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return JSONResponse({"ok": True, "redirect": "/admin"})
    return JSONResponse({"ok": False, "message": "Invalid credentials"})


# ────────────────────────────────
# Logout Route
# ────────────────────────────────
@router.get("/logout")
def logout(request: Request):
    """Destroy session and redirect to login."""
    request.session.clear()
    return RedirectResponse("/login")
