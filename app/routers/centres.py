from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(tags=["Diagnostic Centres & Tests"])


# ---------- Centres ----------

@router.post(
    "/centres/",
    response_model=schemas.DiagnosticCentreOut,
    status_code=status.HTTP_201_CREATED,
)
def create_centre(
    payload: schemas.DiagnosticCentreCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Creates a diagnostic centre.

    Assumption: any authenticated user may register a centre (there is no
    separate "admin"/"centre owner" role in this assignment's scope). In a
    production system this would be restricted to a staff/admin role.
    """
    centre = models.DiagnosticCentre(name=payload.name, location=payload.location)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("/centres/", response_model=schemas.PaginatedCentres)
def list_centres(
    location: str | None = Query(default=None, description="Filter by location (partial match)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.DiagnosticCentre).options(joinedload(models.DiagnosticCentre.tests))
    if location:
        query = query.filter(models.DiagnosticCentre.location.ilike(f"%{location}%"))

    total = query.count()
    items = query.order_by(models.DiagnosticCentre.name).offset(offset).limit(limit).all()
    return schemas.PaginatedCentres(total=total, limit=limit, offset=offset, items=items)


@router.get("/centres/{centre_id}", response_model=schemas.DiagnosticCentreOut)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = (
        db.query(models.DiagnosticCentre)
        .options(joinedload(models.DiagnosticCentre.tests))
        .filter(models.DiagnosticCentre.id == centre_id)
        .first()
    )
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")
    return centre


# ---------- Tests ----------

@router.post(
    "/centres/{centre_id}/tests/",
    response_model=schemas.DiagnosticTestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_test(
    centre_id: str,
    payload: schemas.DiagnosticTestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    centre = db.query(models.DiagnosticCentre).filter(models.DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")

    test = models.DiagnosticTest(centre_id=centre_id, name=payload.name, price=payload.price)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get("/centres/{centre_id}/tests/", response_model=schemas.PaginatedTests)
def list_tests_for_centre(
    centre_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    centre = db.query(models.DiagnosticCentre).filter(models.DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")

    query = db.query(models.DiagnosticTest).filter(models.DiagnosticTest.centre_id == centre_id)
    total = query.count()
    items = query.order_by(models.DiagnosticTest.name).offset(offset).limit(limit).all()
    return schemas.PaginatedTests(total=total, limit=limit, offset=offset, items=items)


@router.get("/tests/{test_id}", response_model=schemas.DiagnosticTestOut)
def get_test(test_id: str, db: Session = Depends(get_db)):
    test = db.query(models.DiagnosticTest).filter(models.DiagnosticTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic test not found")
    return test
