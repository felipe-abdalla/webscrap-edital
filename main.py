import sys
import logging

from pipeline.pipeline import EditalPipeline
from database.db import create_db, clear_database

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def main():
    create_db()

    if "--reset" in sys.argv:
        print("Limpando banco de dados...")
        clear_database()
    else:
        print("Mantendo dados existentes...")

    pipeline = EditalPipeline()
    results = pipeline.run()

    print(f"\nEditais encontrados: {len(results)}")
    # DEBUG
    for e in results:
        print("\n----------------------------")
        print(f"Título: {e.title}")
        print(f"URL: {e.url}")
        print(f"Domínio: {e.domain}")
        print(f"Prazo: {e.deadline}")
        print(f"Frase: {e.phrase}")
        print(f"Pontuação: {e.score}")

if __name__ == "__main__":
    main()