import argparse
import logging

from pipeline.pipeline import EditalPipeline
from pipeline.snapshot import load_snapshot
from database.db import create_db, clear_database

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Limpa o banco antes de rodar")
    parser.add_argument("--replay", metavar="RUN_DIR",
                        help="Reprocessa um snapshot salvo, sem conexão e sem banco")
    return parser.parse_args()

def main():
    args = parse_args()

    if args.replay:
        snapshot = load_snapshot(args.replay)
        results = EditalPipeline(persist=False).process(snapshot)
    else:
        create_db()

        if args.reset:
            print("Limpando banco de dados...")
            clear_database()
        else:
            print("Mantendo dados existentes...")

        results = EditalPipeline().run()

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