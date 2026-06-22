SHELL := bash

.PHONY: bootstrap infra kubeconfig build-push configure-argocd argocd deploy validate happy-path destroy

bootstrap:
	bash ./scripts/bootstrap.sh

infra:
	bash ./scripts/deploy-infra.sh

kubeconfig:
	aws eks update-kubeconfig --region "$$(terraform -chdir=terraform output -raw region)" --name "$$(terraform -chdir=terraform output -raw cluster_name)"

build-push:
	bash ./scripts/build-and-push.sh

configure-argocd:
	bash ./scripts/configure-argocd-repo.sh

argocd:
	bash ./scripts/install-argocd.sh

deploy:
	bash ./scripts/deploy-apps.sh

validate:
	bash ./scripts/validate.sh

happy-path:
	bash ./scripts/happy-path-deploy.sh

destroy:
	bash ./scripts/destroy.sh
