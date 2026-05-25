## Conferir se a porta de criação do banco de dados está disponível
## Conferir se as portas do banco de dados e a configurada no .env estão compatíveis

## Acessar terminal do docker
docker exec -it postgres-editais psql -U postgres -d editais_db

## Criação do banco de dados
docker run --name postgres-editais `
  -e POSTGRES_PASSWORD=1234 `
  -e POSTGRES_DB=editais_db `
  -e POSTGRES_INITDB_ARGS="--auth-host=md5 --auth-local=trust" `
  -p 5433:5433 `
  -d postgres

OU

docker run --name postgres-editais -e POSTGRES_PASSWORD=1234 -e POSTGRES_DB=editais_db -e POSTGRES_INITDB_ARGS="--auth-host=md5 --auth-local=trust" -p 5433:5432 -d postgres

## Remoção de banco de dados
docker stop postgres-editais
docker rm postgres-editais

## Remoção de volume
docker volume prune

## Checar se o banco subiu (deve sair "database system is ready to accept connections")
docker logs -f postgres-editais

## Testar conexão
docker exec -it postgres-editais psql -U postgres -d editais_db

## RECOMENDAÇÃO: Usar DBeaver para visualização de tabelas do banco de dados