# Variables
# NOTE: 定义变量 (Variables)
DOCKER_REGISTRY=langgenius
WEB_IMAGE=$(DOCKER_REGISTRY)/dify-web
API_IMAGE=$(DOCKER_REGISTRY)/dify-api
VERSION=latest

# NOTE: 定义操作目标 (Targets)
# Build Docker images
build-web:
	@echo "Building web Docker image: $(WEB_IMAGE):$(VERSION)..."
	docker build -t $(WEB_IMAGE):$(VERSION) ./web
	@echo "Web Docker image built successfully: $(WEB_IMAGE):$(VERSION)"

build-api:
	@echo "Building API Docker image: $(API_IMAGE):$(VERSION)..."
	docker build -t $(API_IMAGE):$(VERSION) ./api
	@echo "API Docker image built successfully: $(API_IMAGE):$(VERSION)"

# Push Docker images
push-web:
	@echo "Pushing web Docker image: $(WEB_IMAGE):$(VERSION)..."
	docker push $(WEB_IMAGE):$(VERSION)
	@echo "Web Docker image pushed successfully: $(WEB_IMAGE):$(VERSION)"

push-api:
	@echo "Pushing API Docker image: $(API_IMAGE):$(VERSION)..."
	docker push $(API_IMAGE):$(VERSION)
	@echo "API Docker image pushed successfully: $(API_IMAGE):$(VERSION)"

# NOTE: 定义组合目标 (Aggregate Targets)
# Build all images
build-all: build-web build-api

# Push all images
push-all: push-web push-api

build-push-api: build-api push-api
build-push-web: build-web push-web

# Build and push all images
build-push-all: build-all push-all
	@echo "All Docker images have been built and pushed."

# Phony targets
# NOTE: 定义伪目标，确保这些目标总是被执行，即使存在与目标同名的文件
# make 命令通常用来处理文件依赖，如果有一个文件和目标同名，make 可能会跳过执行
# .PHONY 告诉 make，像 build-web、push-api 这些名字并不是指代真实的文件，而是一些抽象的命令，所以无论如何都应该执行它们对应的指令
.PHONY: build-web build-api push-web push-api build-all push-all build-push-all

# NOTE: 用法: make build-push-all
