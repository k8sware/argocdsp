
# ArgoCD SP Operator

The ArgoCD SP Operator provides a Kubernetes controller that automates the management of secrets for ArgoCD service principals. The operator leverages [Kopf](https://kopf.readthedocs.io/) for building Kubernetes operators and the [Kubernetes Python client](https://github.com/kubernetes-client/python) to interact with the cluster.

## Contents

- [ArgoCD SP Operator](#argocd-sp-operator)
  - [Contents](#contents)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Installation](#installation)
    - [Pre-requisites](#pre-requisites)
    - [Build and Deploy](#build-and-deploy)
  - [Usage](#usage)
  - [Custom Resource Definition (CRD)](#custom-resource-definition-crd)
  - [Operator Controller](#operator-controller)
  - [Testing](#testing)
  - [License](#license)

## Features

- **Automated Secret Management:** Creates, updates, and deletes Kubernetes secrets used by ArgoCD.
- **Token Refresh:** Uses a timer to refresh tokens periodically.
- **Robust Error Handling:** Permanent and temporary error signals ensure proper operator reaction.
- **Kubernetes RBAC Support:** Deployed with ClusterRole and ClusterRoleBinding for necessary permissions.

## Architecture

The operator is implemented in [Python (`src/controller.py`)](src/controller.py) and uses the following libraries:
- **Kopf:** For Kubernetes event handling.
- **Kubernetes Python Client:** To interact with your Kubernetes secret API.
- **Requests:** To retrieve an Azure AD token used for authenticating with Microsoft.

## Installation

### Pre-requisites

- Python 3.7+
- A running Kubernetes cluster
- Access with necessary privileges (RBAC configured via the provided manifests)

### Build and Deploy

1. **Docker Image Build**:  
   The Docker image is defined in the [Dockerfile](Dockerfile). To build the image locally, run:

   ```sh
   docker build -t k8sware/argocdsp:latest .
   ```

2. **Deploy CRDs and Manifests**:  
   Deploy the CRD, RBAC, and deployment manifests contained in the [kubernetes](kubernetes/) folder. For example:

   ```sh
   kubectl apply -f kubernetes/pre-requisite.yaml
   kubectl apply -f kubernetes/deploy.yaml
   ```

3. **Custom Resource Application**:  
   An example custom resource is provided in [example/secret.yaml](example/secret.yaml). Adjust the values as needed and apply:

   ```sh
   kubectl apply -f example/secret.yaml
   ```

## Usage

The operator watches for changes to `ArgoCDSP` custom resources (defined in your CRD) and performs the following steps:

1. **Secret Retrieval:**  
   Reads the client secret from Kubernetes using the provided reference. See function [`get_secret`](src/controller.py).

2. **Token Acquisition:**  
   Requests an access token from Microsoft using the client credentials. Check out [`get_auth_token`](src/controller.py).

3. **Secret Management in ArgoCD:**  
   Creates or updates the target secret in an ArgoCD namespace with project details and token information. See [`create_update_secret`](src/controller.py).

Any failures during these operations are logged and retried if possible.

## Custom Resource Definition (CRD)

The operator introduces a new CRD of kind `ArgoCDSP` under the API group `k8sware.com`. See the [CRD manifest](kubernetes/pre-requisite.yaml) for full details. The CRD schema includes:

- `clientId`: The client ID for token acquisition.
- `clientSecretRef`: A reference to the secret containing the client secret.
- `tenantId`: The tenant ID for Azure AD.
- `gitUrl`: The Git repository URL.
- `secretType`: Type of secret (`repository` or `repo-creds`).

## Operator Controller

The main controller logic is implemented in [`src/controller.py`](src/controller.py). The important handlers include:

- **Create/Update/Resume Handler:**  
  Handles the creation, update, and resume events for the custom resource using Kopf decorators.

- **Delete Handler:**  
  Removes the associated secret when the custom resource is deleted.

- **Timer Handler:**  
  Refreshes the secret every hour based on the specified interval.

## Testing

For local testing, use the provided test configurations in the [tests](tests/) directory. You can simulate CR events and validate secrets are managed correctly.

## License

The project is licensed under the [Apache License 2.0](LICENSE).

---

For more detailed development instructions, please refer to the inline comments within [`src/controller.py`](src/controller.py).
