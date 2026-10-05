import csv
import io
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func
from app.models.entities import AuditLog, Customer, Product, Organization
from app.schemas import CustomerIn, ProductIn


async def import_records(db, organization_id, actor_id, kind, content):
    schema, model = (CustomerIn, Customer) if kind == "customers" else (ProductIn, Product)
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        columns = reader.fieldnames or []
        if not columns or len(columns) != len(set(columns)) or "name" not in columns or any(name not in schema.model_fields for name in columns):
            raise HTTPException(422, "CSV headers must be unique supported fields and include name")
        if kind == "products" and "unit_price" not in columns:
            raise HTTPException(422, "Product CSV must include unit_price")
        records = []
        for row_number, row in enumerate(reader, 2):
            if row_number > 1001:
                raise HTTPException(422, "Import accepts at most 1,000 records")
            if None in row or any(value is None for value in row.values()):
                raise HTTPException(422, f"CSV row {row_number} has a different number of columns")
            try:
                payload = schema.model_validate({key: value.strip() for key, value in row.items() if value.strip() or key in {"name", "unit_price"}})
            except ValidationError as exc:
                errors = "; ".join(f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors(include_input=False))
                raise HTTPException(422, f"CSV row {row_number}: {errors}") from None
            records.append(payload)
    except (UnicodeDecodeError, csv.Error):
        raise HTTPException(422, "Upload a valid UTF-8 CSV file") from None
    if not records:
        raise HTTPException(422, "CSV has no records")
    names = [record.name.casefold() for record in records]
    if len(names) != len(set(names)):
        raise HTTPException(409, "CSV contains duplicate names")
    await db.scalar(select(Organization.id).where(Organization.id == organization_id).with_for_update(key_share=True))
    existing = await db.execute(select(model.name).where(model.organization_id == organization_id))
    if set(names) & {name.casefold() for name in existing.scalars().all()}:
        raise HTTPException(409, "An imported name already exists; no records were imported")
    for payload in records:
        entity = model(organization_id=organization_id, **payload.model_dump())
        db.add(entity); await db.flush()
        db.add(AuditLog(organization_id=organization_id, user_id=actor_id, action=f"{kind}.imported", entity_type=kind.rstrip("s"), entity_id=entity.id, new_values={"name": entity.name}))
    await db.commit()
    return {"imported": len(records)}
