From ubuntu
Run apt-get update
Run apt-get install nginx -y
COPY index.html /var/www/html
EXPOSE 80
CMD ["nginx","-g","daemon off;"]