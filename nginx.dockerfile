# Multi-stage build, see https://docs.docker.com/develop/develop-images/multistage-build/
FROM alpine AS builder

ARG VERSION=0.11.1

ADD https://github.com/sabre-io/Baikal/releases/download/$VERSION/baikal-$VERSION.zip .
RUN apk add unzip && unzip -q baikal-$VERSION.zip

# Final Docker image
FROM nginx:1

# Install dependencies: PHP (with libffi6 dependency) & SQLite3
RUN curl -o /etc/apt/trusted.gpg.d/php.gpg https://packages.sury.org/php/apt.gpg &&\
  apt update                  &&\
  apt install -y lsb-release  &&\
  apt install -y libcurl4-openssl-dev      &&\
  echo "deb https://packages.sury.org/php/ $(lsb_release -sc) main" > /etc/apt/sources.list.d/php.list &&\
  apt remove -y lsb-release   &&\
  apt update                  &&\
    apt install -y            \
    php8.5-curl               \
    php8.5-fpm                \
    php8.5-mbstring           \
    php8.5-mysql              \
    php8.5-pgsql              \
    php8.5-sqlite3            \
    php8.5-xml                \
    sqlite3                   \
    msmtp msmtp-mta           &&\
  rm -rf /var/lib/apt/lists/* &&\
  sed -i 's/www-data/nginx/' /etc/php/8.5/fpm/pool.d/www.conf &&\
  sed -i 's/^listen = .*/listen = \/var\/run\/php-fpm.sock/' /etc/php/8.5/fpm/pool.d/www.conf

# Add Baikal & nginx configuration
COPY files/docker-entrypoint.d/*.sh files/docker-entrypoint.d/*.php files/docker-entrypoint.d/nginx/ /docker-entrypoint.d/
COPY --from=builder --chown=nginx:nginx baikal /var/www/baikal
COPY files/nginx.conf /etc/nginx/conf.d/default.conf

RUN mkdir /etc/nginx/ssl
RUN openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -subj "/C=/ST=/L=/O=/CN=" -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt

VOLUME /var/www/baikal/config
VOLUME /var/www/baikal/Specific
VOLUME /etc/nginx/ssl