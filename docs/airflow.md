# Airflow: the `governor_profile_raw` DAG

`airflow/dags/governor_profile_raw.py` is loaded by **airflow-platform** as a DAG bundle (its `projects.yaml`, spec §6). The platform's Airflow image has no governor code (ADR 0001). The DAG starts a container from the `governor:local` image through the Docker socket proxy and runs `python -m governor.build profile --schema raw --policy knowledge/shop/policy.yaml --out /data/profiles/<run id>.json`. The `:` characters in the run id become `_`.

The DAG is manual only (`schedule=None`). Before you trigger it: start the test bed (`testbed/`, port 55432) and `docker compose up` here, so the image and the `governor-data` volume exist. Run `up.ps1` in airflow-platform, then trigger the DAG from the Airflow UI. The profile lands on the governor data volume. The API serves it at `GET /profiles/{run_id}` (bearer token), and the Streamlit page **Profiles** opens it with `?run_id=<run id>`.

Airflow Variables (all of them are rendered when the task runs, not when the DAG is parsed):

| Variable | Default | Used for |
|---|---|---|
| `governor_data_volume` | `governor_governor-data` | the volume mounted at `/data` |
| `docker_url` | `tcp://docker-proxy:2375` | the Docker API, through the socket proxy |
| `governor_pg_host` / `governor_pg_port` / `governor_pg_db` | `host.docker.internal` / `55432` / `shop` | `GOVERNOR_PG_HOST/PORT/DB` |
| `governor_build_user` | `governor_build` | `GOVERNOR_BUILD_USER` |
| `governor_build_password` | none; it must be set | `GOVERNOR_BUILD_PASSWORD` (Airflow masks it in logs) |

The DAG file contains no password. The local test-bed values are in `testbed/README.md`.
