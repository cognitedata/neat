FROM python:3.11-slim as base

#Copy the requirements file from host to container
COPY requirements.txt /app/
WORKDIR /app/
# Copy the application source code from host to container
COPY cognite/neat /app/cognite/neat

RUN mkdir -p /app/data \
    && cp /app/cognite/neat/examples/. /app/data -r \
    && chmod -R 777 /app/data \
    && pip install -r requirements.txt

WORKDIR /app
# Default config file
ENV NEAT_CONFIG_PATH=/app/data/config.yaml

# Set the default command to run the application
CMD ["uvicorn", "--host","0.0.0.0", "cognite.neat.explorer.explorer:app"]
