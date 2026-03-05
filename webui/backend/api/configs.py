import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.config import ScenarioConfig
from webui.backend.database import get_db
from webui.backend.models import ConfigRecord

router = APIRouter(prefix="/api/configs", tags=["configs"])


class ConfigCreate(BaseModel):
    name: str
    yaml_content: str


class ConfigResponse(BaseModel):
    id: str
    name: str
    yaml_content: str
    created_at: str
    updated_at: str


@router.get("", response_model=list[ConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    records = db.query(ConfigRecord).order_by(ConfigRecord.updated_at.desc()).all()
    return [_to_response(r) for r in records]


@router.post("", response_model=ConfigResponse, status_code=201)
def create_config(body: ConfigCreate, db: Session = Depends(get_db)):
    record = ConfigRecord(name=body.name, yaml_content=body.yaml_content)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.get("/{config_id}", response_model=ConfigResponse)
def get_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    return _to_response(record)


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(config_id: str, body: ConfigCreate, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    record.name = body.name
    record.yaml_content = body.yaml_content
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(record)
    db.commit()


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = []


@router.post("/{config_id}/validate", response_model=ValidateResponse)
def validate_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        raw = yaml.safe_load(record.yaml_content)
        ScenarioConfig(**raw)
        return ValidateResponse(valid=True)
    except Exception as e:
        return ValidateResponse(valid=False, errors=[str(e)])


def _to_response(record: ConfigRecord) -> ConfigResponse:
    return ConfigResponse(
        id=record.id,
        name=record.name,
        yaml_content=record.yaml_content,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )
