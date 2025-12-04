from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import engine, get_db
from .models import Base, Player
from .routers import countries, players, playlists


# ----------------------------------------------------
# Create database tables on startup (development only)
# ----------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ArenaSignage API")


# ----------------------------------------------------
# Static file serving
# ----------------------------------------------------
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ----------------------------------------------------
# Template rendering (Jinja2)
# ----------------------------------------------------
templates = Jinja2Templates(directory="app/templates")


# ----------------------------------------------------
# API Routers
# ----------------------------------------------------
# Each router defines its own prefix and tags.
# We include them here without additional prefixes.
app.include_router(countries.router)
app.include_router(players.router)
app.include_router(playlists.router)


# ----------------------------------------------------
# Favicon endpoint
# ----------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.ico")


# ----------------------------------------------------
# Dashboard HTML page
# ----------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Render the dashboard HTML page and inject all players.
    """
    players = db.query(Player).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "players": players},
    )


# ----------------------------------------------------
# Health check endpoint
# ----------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------------------------------
# Root endpoint (hidden)
# ----------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return {
        "status": "running",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "players_api": "/players",
        "playlists_api": "/playlists",
        "countries_api": "/countries",
    }