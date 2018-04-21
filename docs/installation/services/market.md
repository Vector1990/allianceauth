# Alliance Market

## Dependencies
Alliance Market requires PHP installed in your web server. Apache has `mod_php`, NGINX requires `php-fpm`.

## Prepare Your Settings
In your auth project's settings file, do the following:
 - Add `'allianceauth.services.modules.market',` to your `INSTALLED_APPS` list
 - Append the following to the bottom of the settings file


    # Alliance Market
    MARKET_URL = ''
    DATABASES['market'] = {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'alliance_market',
        'USER': 'allianceserver-market',
        'PASSWORD': 'password',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }

## Setup Alliance Market
Alliance Market needs a database. Create one in MySQL/MariaDB. Default name is `alliance_market`:

    mysql -u root -p
    create database alliance_market;
    grant all privileges on alliance_market . * to 'allianceserver'@'localhost';
    exit;

Install required packages to clone the repository:

    apt-get install mercurial meld

Change to the web folder:

    cd /var/www

Now clone the repository

    hg clone https://bitbucket.org/krojew/evernus-alliance-market

Make cache and log directories

    mkdir evernus-alliance-market/app/cache
    mkdir evernus-alliance-market/app/logs
    chmod -R 777 evernus-alliance-market/app/cache
    chmod -R 777 evernus-alliance-market/app/logs

Change ownership to apache

    chown -R www-data:www-data evernus-alliance-market

Enter directory

    cd evernus-alliance-market

Set environment variable

    export SYMFONY_ENV=prod

Copy configuration

    cp app/config/parameters.yml.dist  app/config/parameters.yml

Edit, changing the following:
 - `database_name` to `alliance_market`
 - `database_user` to your MySQL user (usually `allianceserver`)
 - `database_password` to your MySQL user password
 - email settings, eg Gmail/Mailgun etc.

Edit `app/config/config.yml` and add the following:

    services:
        fos_user.doctrine_registry:
            alias: doctrine

Install composer [as per these instructions.](https://getcomposer.org/download/)

Update dependencies.

    php composer.phar update --optimize-autoloader

Prepare the cache:

    php app/console cache:clear --env=prod --no-debug


Dump assets:

    php app/console assetic:dump --env=prod --no-debug


Create DB entries

    php app/console doctrine:schema:update --force

Install SDE:

    php app/console evernus:update:sde

Configure your web server to serve alliance market.

A minimal Apache config might look like:

    <VirtualHost *:80>
        ServerName market.example.com
        DocumentRoot /var/www/evernus-alliance-market/web
        <Directory "/var/www/evernus-alliance-market/web/">
            DirectoryIndex app.php
            Require all granted
            AllowOverride all
        </Directory>
    </VirtualHost>

A minimal Nginx config might look like:

    server {
        listen 80;
        server_name  market.example.com;
        root   /var/www/evernus-alliance-market/web;
        index  app.php;
        access_log  /var/logs/market.access.log;

        # strip app.php/ prefix if it is present
        rewrite ^/app\.php/?(.*)$ /$1 permanent;
    
        location / {
            index app.php;
            try_files $uri @rewriteapp;
        }
    
        location @rewriteapp {
            rewrite ^(.*)$ /app.php/$1 last;
        }
    
        # pass the PHP scripts to FastCGI server from upstream phpfcgi
        location ~ ^/(app|app_dev|config)\.php(/|$) {
            fastcgi_pass 127.0.0.1:9000;
            fastcgi_split_path_info ^(.+\.php)(/.*)$;
            include fastcgi_params;
            fastcgi_param  SCRIPT_FILENAME $document_root$fastcgi_script_name;
            fastcgi_param  HTTPS off;
        }
    
        location ~ /\.ht {
            deny all;
        }
    }

Once again, set cache permissions:

    chown -R www-data:www-data app/

Add a user account through auth, then make it a superuser:

    php app/console fos:user:promote your_username --super

Now edit your auth project's settings file and fill in the web URL to your market as well as the database details.

Finally run migrations and restart Gunicorn and Celery.
