from pathlib import Path

import yaml

data = yaml.safe_load(Path("docker/docker-compose.yml").read_text())
services = data["services"]
assert {"postgres", "migrate", "redis", "backend", "bot", "worker"} <= set(services)
assert services["backend"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
assert services["backend"]["healthcheck"]["test"][-1].endswith("/health/ready")
assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
assert Path("docker/Dockerfile.backend").read_text().count("COPY alembic.ini ./") == 1
print("compose validation: OK")
