@echo off
cd /d %~dp0..
docker compose -f infra/docker-compose.yml up -d
echo Infrastructure starting: Neo4j http://localhost:7474  Kafka localhost:9092  Redis localhost:6379
