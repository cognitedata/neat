FROM python:3.11-slim as base

########################################################################
###########Need to install Rust and other dependencies##################
RUN apt-get -qq update

RUN apt-get install -y -q \
    build-essential \
    openssl \
    make \
    cmake \
    pkg-config \
    libssl-dev \
    clang \
    libpq-dev \
    curl

# Get Rust; NOTE: using sh for better compatibility with other base images
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

# Add .cargo/bin to PATH
ENV PATH="/root/.cargo/bin:${PATH}"
###########Need to above to install Rust and other dependencies#########
########################################################################

#Copy the requirements file from host to container
COPY requirements.txt /app/
WORKDIR /app/
# Copy the application source code from host to container
COPY cognite/neat /app/cognite/neat

RUN mkdir -p /app/data \
    && chmod -R 777 /app/data \
    && pip install -r requirements.txt

WORKDIR /app
# Default config file
ENV NEAT_CONFIG_PATH=/app/data/config.yaml

# Set the default command to run the application
CMD ["uvicorn", "--host","0.0.0.0", "cognite.neat.app.api.explorer:app"]
