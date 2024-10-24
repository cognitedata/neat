FROM python:3.11.4-buster as build-toolkit

#### Configuring rust build environment ####
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

####  Building non-python dependencies using build toolkit ####
FROM build-toolkit as build
# Add .cargo/bin to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

#Copy the requirements file from host to container
COPY requirements.txt /app/
WORKDIR /app/
RUN pip install -r requirements.txt

# Building final image
FROM python:3.11.4-slim-buster as runtime
COPY --from=build /usr/local/lib/python3.11/site-packages  /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
# Copy the application source code from host to container
COPY cognite/neat /app/cognite/neat
RUN mkdir -p /app/data && chmod -R 777 /app/data
WORKDIR /app
# Default config file
ENV NEAT_CONFIG_PATH=/app/data/config.yaml

# Set the default command to run the application
CMD ["uvicorn", "--host","0.0.0.0", "cognite.neat._app.api.explorer:app"]
