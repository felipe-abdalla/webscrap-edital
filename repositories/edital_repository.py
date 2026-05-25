from sqlmodel import Session, select
from database.db import engine
from domain.edital import Edital

class EditalRepository:
    def save(self, edital: Edital):
        with Session(engine) as session:
            session.add(edital)
            session.commit()
            session.refresh(edital)
            return edital
        
    def exists_by_url(self, url: str) -> bool:
        with Session(engine) as session:
            statement = select(Edital).where(Edital.url == url)
            result = session.exec(statement).first()
            return result is not None
        
    def get_all(self):
        with Session(engine) as session:
            return session.exec(select(Edital)).all()