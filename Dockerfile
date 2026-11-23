FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

WORKDIR /code

COPY ./pyproject.toml ./README.md ./uv.lock* ./
COPY ./src ./src
COPY ./skills ./skills
COPY ./step2_workflow_agent ./step2_workflow_agent

RUN uv sync --frozen --no-dev

ARG AGENT_VERSION=0.1.0
ENV AGENT_VERSION=${AGENT_VERSION}
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV GOOGLE_CLOUD_LOCATION=global

EXPOSE 8080

CMD ["uv", "run", "--no-dev", "uvicorn", "step2_workflow_agent.fast_api_app:app", "--host", "0.0.0.0", "--port", "8080"]
