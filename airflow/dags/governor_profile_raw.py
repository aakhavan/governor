"""Profile governor's raw schema as a container workload (airflow-platform spec section 8, ADR 0001).

Manual only. The task runs ``python -m governor.build profile`` inside the existing ``governor:local``
image and writes ``/data/profiles/<run id>.json`` to the governor data volume, where the governor API
serves it at ``GET /profiles/{run_id}``. Every connection value comes from an Airflow Variable rendered
at run time (see docs/airflow.md); this file holds no credentials and imports only Airflow, the docker
provider, ``docker.types`` and the standard library.
"""

from __future__ import annotations

from datetime import datetime

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG
from docker.types import Mount


class _RenderedDockerOperator(DockerOperator):
    """DockerOperator that also renders ``docker_url`` and ``mounts`` (Variables read at run time, not parse time)."""

    template_fields = (*DockerOperator.template_fields, "docker_url", "mounts")


with DAG(
    dag_id="governor_profile_raw",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["governor"],
    doc_md=__doc__,
) as dag:
    _RenderedDockerOperator(
        task_id="profile",
        image="governor:local",
        command=(
            "python -m governor.build profile --schema raw --policy knowledge/shop/policy.yaml "
            "--out /data/profiles/{{ run_id | replace(':', '_') }}.json"
        ),
        mounts=[
            Mount(
                source="{{ var.value.get('governor_data_volume', 'governor_governor-data') }}",
                target="/data",
                type="volume",
            )
        ],
        environment={
            "GOVERNOR_PG_HOST": "{{ var.value.get('governor_pg_host', 'host.docker.internal') }}",
            "GOVERNOR_PG_PORT": "{{ var.value.get('governor_pg_port', '55432') }}",
            "GOVERNOR_PG_DB": "{{ var.value.get('governor_pg_db', 'shop') }}",
            "GOVERNOR_BUILD_USER": "{{ var.value.get('governor_build_user', 'governor_build') }}",
            "GOVERNOR_BUILD_PASSWORD": "{{ var.value.get('governor_build_password') }}",
        },
        extra_hosts={"host.docker.internal": "host-gateway"},
        mount_tmp_dir=False,
        docker_url="{{ var.value.get('docker_url', 'tcp://docker-proxy:2375') }}",
        auto_remove="success",
    )
