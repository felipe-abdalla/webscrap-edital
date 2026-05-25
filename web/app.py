"""
web/app.py
Servidor Flask para o painel de gerenciamento de editais.
Executar a partir da raiz do projeto:  python -m web.app
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, render_template, request, jsonify
from sqlmodel import Session, select

from database.db import engine, create_db
from domain.edital import Edital

from pipeline.pipeline import EditalPipeline
from pipeline.search.query_builder import generate_queries, prioritize_queries
from pipeline.search.query_ranker import score_query
from pipeline.search.query_storage import load_stats, save_stats

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_topics() -> list[str]:
    """Lê os tópicos actuais directamente do query_builder."""
    import pipeline.search.query_builder as qb
    return list(qb.TOPICS)


def _set_topics(topics: list[str]) -> None:
    import pipeline.search.query_builder as qb
    qb.TOPICS = topics


def _get_year() -> str:
    import pipeline.search.query_ranker as qr
    return qr.YEAR


def _set_year(year: str) -> None:
    import pipeline.search.query_ranker as qr
    qr.YEAR = year


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html",
                           topics=_get_topics(),
                           year=_get_year())


@app.route("/api/editais")
def api_editais():
    """Retorna editais do banco. Query param: include_no_deadline=true|false"""
    include_no_deadline = request.args.get("include_no_deadline", "false").lower() == "true"

    with Session(engine) as session:
        stmt = select(Edital).order_by(Edital.deadline.asc().nullslast(), Edital.score.desc())
        rows = session.exec(stmt).all()

    com_deadline = []
    sem_deadline = []

    for e in rows:
        item = {
            "id": e.id,
            "title": e.title or "Sem título",
            "url": e.url,
            "domain": e.domain or "",
            "deadline": e.deadline.isoformat() if e.deadline else None,
            "score": e.score,
            "phrase": e.phrase or "",
            "created_at": e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "",
        }
        if e.deadline:
            com_deadline.append(item)
        else:
            sem_deadline.append(item)

    result = com_deadline
    if include_no_deadline:
        result = com_deadline + sem_deadline

    return jsonify({"editais": result, "total": len(result)})


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify({"topics": _get_topics(), "year": _get_year()})


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json(force=True)

    topics = data.get("topics", [])
    year = data.get("year", "").strip()

    if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
        return jsonify({"error": "topics deve ser uma lista de strings"}), 400

    if not year.isdigit() or len(year) != 4:
        return jsonify({"error": "year deve ser um ano com 4 dígitos"}), 400

    _set_topics([t.strip() for t in topics if t.strip()])
    _set_year(year)

    return jsonify({"ok": True, "topics": _get_topics(), "year": _get_year()})


@app.route("/api/run", methods=["POST"])
def api_run():
    """Dispara o pipeline e retorna quantos editais foram encontrados."""
    try:
        pipeline = EditalPipeline()
        results = pipeline.run()
        return jsonify({"ok": True, "found": len(results)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/editais/<int:edital_id>", methods=["DELETE"])
def api_delete_edital(edital_id: int):
    with Session(engine) as session:
        edital = session.get(Edital, edital_id)
        if not edital:
            return jsonify({"error": "Não encontrado"}), 404
        session.delete(edital)
        session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    create_db()
    app.run(debug=True, port=5000)
