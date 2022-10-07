docker build -t testImage .
docker stop test 
docker rm -f test
docker run -p 80:80 --name test testImage
