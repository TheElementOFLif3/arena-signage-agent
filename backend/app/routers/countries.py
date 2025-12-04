from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

# Router for all /countries endpoints
router = APIRouter(
    prefix="/countries",
    tags=["countries"],
)


# -------------------------
# Create a new country
# -------------------------
@router.post(
    "/",
    response_model=schemas.CountryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_country(
    country_in: schemas.CountryCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new country.

    The 'code' field is expected to be unique (for example: 'RS', 'US', 'CA').
    """
    # Check if a country with the same code already exists
    existing = (
        db.query(models.Country)
        .filter(models.Country.code == country_in.code)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A country with this code already exists.",
        )

    # Pydantic v2: use model_dump() instead of dict()
    country_data = country_in.model_dump()
    country = models.Country(**country_data)

    db.add(country)
    db.commit()
    db.refresh(country)
    return country


# -------------------------
# List all countries
# -------------------------
@router.get(
    "/",
    response_model=List[schemas.CountryRead],
)
def list_countries(db: Session = Depends(get_db)):
    """
    Return a list of all countries.
    """
    countries = db.query(models.Country).all()
    return countries


# -------------------------
# Get a single country by ID
# -------------------------
@router.get(
    "/{country_id}",
    response_model=schemas.CountryRead,
)
def get_country(
    country_id: int,
    db: Session = Depends(get_db),
):
    """
    Return a single country by its numeric ID.
    """
    country = (
        db.query(models.Country)
        .filter(models.Country.id == country_id)
        .first()
    )
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found.",
        )
    return country


# -------------------------
# Update an existing country
# -------------------------
@router.put(
    "/{country_id}",
    response_model=schemas.CountryRead,
)
def update_country(
    country_id: int,
    country_in: schemas.CountryUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing country (code and/or name).
    Only fields provided in the request body will be updated.
    """
    country = (
        db.query(models.Country)
        .filter(models.Country.id == country_id)
        .first()
    )
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found.",
        )

    # If code is updated, make sure it's not already taken by another country
    if country_in.code is not None:
        existing_with_code = (
            db.query(models.Country)
            .filter(
                models.Country.code == country_in.code,
                models.Country.id != country_id,
            )
            .first()
        )
        if existing_with_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another country with this code already exists.",
            )

    # Only update fields actually provided in the request
    update_data = country_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(country, field, value)

    db.commit()
    db.refresh(country)
    return country


# -------------------------
# Delete a country
# -------------------------
@router.delete(
    "/{country_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_country(
    country_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a country by its ID.

    Note: if there are players referencing this country via 'country_code',
    you may want to enforce a rule or handle it at the application level.
    """
    country = (
        db.query(models.Country)
        .filter(models.Country.id == country_id)
        .first()
    )
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found.",
        )

    db.delete(country)
    db.commit()
    return None