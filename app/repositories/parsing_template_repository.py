from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.entities.parsing_template import ParsingTemplate


class ParsingTemplateRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, template: ParsingTemplate) -> ParsingTemplate:
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_by_id(self, template_id: str, load_user: bool = False) -> Optional[ParsingTemplate]:
        query = self.db.query(ParsingTemplate)
        if load_user:
            query = query.options(joinedload(ParsingTemplate.user))
        return query.filter(ParsingTemplate.id == template_id).first()

    def get_by_user_and_name(self, user_id: str, template_name: str) -> Optional[ParsingTemplate]:
        return self.db.query(ParsingTemplate).filter(
            ParsingTemplate.user_id == user_id,
            ParsingTemplate.template_name == template_name
        ).first()

    def get_accessible_templates(self, user_id: str, load_user: bool = False) -> List[ParsingTemplate]:
        query = self.db.query(ParsingTemplate)
        if load_user:
            query = query.options(joinedload(ParsingTemplate.user))

        return query.filter(
            or_(
                ParsingTemplate.user_id == user_id,
                ParsingTemplate.is_public == True
            )
        ).order_by(ParsingTemplate.created_at.desc()).all()

    def update(self, template: ParsingTemplate) -> ParsingTemplate:
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template: ParsingTemplate) -> None:
        self.db.delete(template)
        self.db.commit()
