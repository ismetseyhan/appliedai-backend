from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.entities.template import Template


class TemplateRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, template: Template) -> Template:
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_by_id(self, template_id: str, load_user: bool = False) -> Optional[Template]:
        query = self.db.query(Template)
        if load_user:
            query = query.options(joinedload(Template.user))
        return query.filter(Template.id == template_id).first()

    def get_by_user_and_name(self, user_id: str, template_name: str) -> Optional[Template]:
        return self.db.query(Template).filter(
            Template.user_id == user_id,
            Template.template_name == template_name
        ).first()

    def get_accessible_templates(self, user_id: str, load_user: bool = False) -> List[Template]:
        query = self.db.query(Template)
        if load_user:
            query = query.options(joinedload(Template.user))

        return query.filter(
            or_(
                Template.user_id == user_id,
                Template.is_public == True
            )
        ).order_by(Template.created_at.desc()).all()

    def update(self, template: Template) -> Template:
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template: Template) -> None:
        self.db.delete(template)
        self.db.commit()
