"""
web/app.py
Servidor Flask do WebGate: exibe os editais abertos que estão no banco e
mantém o banco atualizado, executando o pipeline a cada UPDATE_INTERVAL_HOURS.
Executar a partir da raiz do projeto:  python -m web.app
"""

import json
import logging
import mimetypes
import os
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify, render_template
from sqlmodel import Session, select

from config.settings import AUTO_UPDATE, UPDATE_INTERVAL_HOURS
from database.db import create_db, engine
from domain.edital import Edital
from pipeline.pipeline import EditalPipeline
from pipeline.snapshot import DATASETS_DIR

log = logging.getLogger("webgate")

# No Windows, o registro pode associar .js a text/plain, e o navegador recusa
# carregar módulos ES (<script type="module">) servidos com esse tipo
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Atualização periódica do banco
# ---------------------------------------------------------------------------

class Updater:
    """Executa o pipeline (coleta + processamento + persistência) a cada
    `interval`. O instante da última coleta é lido do snapshot mais recente
    em datasets/, de modo que reiniciar o servidor não antecipa a coleta."""

    RETRY_AFTER = timedelta(hours=1)  # espera após uma coleta que falhou

    def __init__(self, interval: timedelta):
        self.interval = interval
        self.running = False
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._retry_at: datetime | None = None

    @staticmethod
    def last_collection() -> datetime | None:
        runs = sorted(DATASETS_DIR.glob("run_*/manifest.json"))
        if not runs:
            return None
        with open(runs[-1], encoding="utf-8") as f:
            return datetime.fromisoformat(json.load(f)["run_at"])

    def next_update(self) -> datetime:
        last = self.last_collection()
        due = last + self.interval if last else datetime.now().astimezone()
        if self._retry_at and self._retry_at > due:
            return self._retry_at
        return due

    def run_once(self) -> None:
        if not self._lock.acquire(blocking=False):
            return  # já existe uma coleta em andamento

        self.running = True
        try:
            log.info("Iniciando coleta agendada")
            found = EditalPipeline().run()
            self.last_error = None
            self._retry_at = None
            log.info("Coleta concluída: %d edital(is) novo(s)", len(found))
        except Exception as e:
            self.last_error = str(e)
            self._retry_at = datetime.now().astimezone() + self.RETRY_AFTER
            log.exception("Falha na coleta agendada")
        finally:
            self.running = False
            self._lock.release()

    def loop(self) -> None:
        while not self._stop.is_set():
            wait = (self.next_update() - datetime.now().astimezone()).total_seconds()
            if wait > 0:
                # Acorda pelo menos a cada hora para reavaliar o horário
                self._stop.wait(min(wait, 3600))
                continue
            self.run_once()

    def start(self) -> None:
        threading.Thread(target=self.loop, name="webgate-updater", daemon=True).start()


updater = Updater(timedelta(hours=UPDATE_INTERVAL_HOURS))


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _as_date(value: date | datetime) -> date:
    """A coluna deadline pode ser timestamp em bancos criados com uma versão
    antiga do modelo, e então chega como datetime."""
    return value.date() if isinstance(value, datetime) else value


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29/02 em ano não bissexto
        return d.replace(year=d.year + years, day=28)


# Prazos além disso, contados da data da coleta, são erros de extração do ano
MAX_DEADLINE_YEARS = 5


def _plausible(e: Edital) -> bool:
    collected = _as_date(e.created_at) if e.created_at else date.today()
    return _as_date(e.deadline) <= _add_years(collected, MAX_DEADLINE_YEARS)


def _card_key(e: Edital) -> tuple[str, date]:
    """Mesmo título e mesmo prazo: o mesmo edital publicado em URLs diferentes"""
    title = " ".join((e.title or "").casefold().split())
    return title, _as_date(e.deadline)


def _unique(rows: list[Edital]) -> list[Edital]:
    seen, unique = set(), []
    for e in rows:  # já ordenados por prazo e score: fica o de maior score
        key = _card_key(e)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/editais")
def api_editais():
    """Editais com inscrições abertas, do prazo mais próximo ao mais distante,
    sem prazos implausíveis e sem cards repetidos"""

    try:
        with Session(engine) as session:
            stmt = (
                select(Edital)
                .where(Edital.deadline >= date.today())
                .order_by(Edital.deadline.asc(), Edital.score.desc())
            )
            rows = session.exec(stmt).all()
    except Exception:
        log.exception("Falha ao consultar o banco")
        return jsonify({"error": "Banco de dados indisponível"}), 503

    editais = [
        {
            "id": e.id,
            "title": e.title or "Sem título",
            "url": e.url,
            "domain": e.domain or "",
            "deadline": _as_date(e.deadline).isoformat(),
        }
        for e in _unique([e for e in rows if _plausible(e)])
    ]

    return jsonify({
        "editais": editais,
        "total": len(editais),
        "updated_at": _iso(updater.last_collection()),
        "next_update_at": _iso(updater.next_update()) if AUTO_UPDATE else None,
        "updating": updater.running,
    })


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    create_db()

    if AUTO_UPDATE:
        updater.start()

    # Sem reloader: com ele, o Flask sobe dois processos e a coleta rodaria duas vezes
    app.run(debug=True, use_reloader=False, port=5000)
