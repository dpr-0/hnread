run:
	python bot.py

build:
	docker build --platform=linux/amd64 --tag hnread:latest .
