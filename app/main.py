from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from app.routers import auth, centres, bookings, payments

# For this assignment we create tables directly from the models rather than
# using a migration tool (Alembic) to keep local setup to a single command.
# See README "What I'd improve" for how this would evolve in production.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EVE Healthcare - Diagnostic Bookings API",
    description=(
        "Backend service for diagnostic test bookings and simulated payments. "
        "Provides JWT authentication, diagnostic centre/test catalog management, "
        "a booking system, and a mock payment + idempotent webhook flow."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
