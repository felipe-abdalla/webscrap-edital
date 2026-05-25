import requests
from config.settings import API_KEY

# Aumentado de 3 para 5: maior cobertura sem impacto proporcional no custo da API.
# Com 20 queries e teto de 50 resultados brutos no pipeline, 3 resultados/query
# significava que apenas ~17 queries chegavam ao limite — as últimas 3 eram
# desperdiçadas. Com 5, o teto é atingido em ~10 queries, usando menos chamadas.
_MAX_RESULTS_PER_QUERY = 5


def search_api(query: str) -> list[dict]:
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": _MAX_RESULTS_PER_QUERY,
    }

    try:
        print(f"Buscando: {query}")
        response = requests.post(url, json=payload, timeout=(5, 10))

        print(f"Status: {response.status_code}")

        response.raise_for_status()

        data = response.json()

        if not data or "results" not in data:
            print("Sem resultados")
            return []

        return [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
            }
            for item in data.get("results", [])
        ]

    except requests.exceptions.ConnectTimeout:
        print("[ERRO] Timeout ao conectar com Tavily")
        return []

    except requests.exceptions.ReadTimeout:
        print("[ERRO] Tavily demorou para responder")
        return []

    except requests.exceptions.ConnectionError as e:
        print(f"[ERRO] Falha de conexão: {e}")
        return []

    except requests.exceptions.RequestException as e:
        print(f"[ERRO] Requisição inválida: {e}")
        return []

    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")
        return []
