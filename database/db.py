from sqlmodel import SQLModel, create_engine, Session, text

from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)

def create_db():
    SQLModel.metadata.create_all(engine)

def clear_database():
    with Session(engine) as session:
        session.exec(text("TRUNCATE TABLE edital RESTART IDENTITY CASCADE"))
        session.commit()