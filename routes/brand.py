from fastapi import APIRouter
from pydantic import BaseModel
from services.db_service import get_connection

router = APIRouter()

# Request model
class BrandCreate(BaseModel):
    company_name: str


@router.post("/brand/create")
def create_brand(data: BrandCreate):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO brands (company_name) VALUES (%s) RETURNING id;",
            (data.company_name,)
        )
        brand_id = cur.fetchone()["id"]
        conn.commit()

        return {
            "message": "Brand stored successfully",
            "brand_id": brand_id
        }

    finally:
        cur.close()
        conn.close()
