"""This module contains the controller logic for the ArgoCD Service Principal"""
import kopf
from kubernetes import client as k8s_client
import requests

def get_secret(client_secret_ref, namespace, body):
    """
    Get the secret with the given name and namespace
    """
    secret_name = client_secret_ref.get("name")
    key_name = client_secret_ref.get("key")
    if not all([secret_name, key_name]):
        kopf.exception(body, reason="Secret Error", message="Name and key must be provided in client_secret_ref")
        raise kopf.PermanentError("name and key must be provided in client_secret_ref")
    api_instance = k8s_client.CoreV1Api()
    try:
        secret = api_instance.read_namespaced_secret(name=secret_name, namespace=namespace)
        return secret.data.get(key_name).decode("utf-8")
    except k8s_client.rest.ApiException as e:
            kopf.exception(body, reason="Secret Error", message=f"Failed to get secret {str(e)}")
            raise kopf.TemporaryError(f"Failed to get secret {str(e)}", delay=10)

def get_auth_token(client_id, client_secret, tenant_id):
    """
    Get the auth token from the given client_id, client_secret, and tenant_id
    """
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "499b84ac-1321-427f-aa17-267ca6975798/.default"
    }
    response = requests.post(url, headers=headers, data=payload, timeout=60)
    print(response.text) # Write events back if error or success
    response.raise_for_status()
    return response.json()["access_token"]

def create_update_secret(token, name, namespace ,git_url, secret_type):
    """
    Create or update a secret with the given token
    """
    api_instance = k8s_client.CoreV1Api()
    deploy_namespace = "argocd"
    secret_name = f"{name}-{namespace}-{deploy_namespace}-token" # secret name is the name of the CRD with namespace to support multi-tenant
    secret_body = k8s_client.V1Secret(
        metadata=k8s_client.V1ObjectMeta(name=secret_name, namespace=deploy_namespace, labels={
            "argocd.argoproj.io/secret-type": secret_type
        }),
        type="Opaque",
        string_data={"password": token, "url": git_url, "project": namespace}
    )
    try:
        api_instance.read_namespaced_secret(name=secret_name, namespace=deploy_namespace)
        api_instance.replace_namespaced_secret(name=secret_name, namespace=deploy_namespace, body=secret_body)
    except k8s_client.rest.ApiException as e:
        if e.status == 404:
            api_instance.create_namespaced_secret(namespace=deploy_namespace, body=secret_body)
        else:
            raise kopf.TemporaryError(f"Failed to create/update secret {str(e)}", delay=10)

@kopf.on.create('k8sware.com', 'v1', 'argocdsp')
@kopf.on.update('k8sware.com', 'v1', 'argocdsp')
@kopf.on.resume('k8sware.com', 'v1', 'argocdsp')
def create_update_argocdsp(spec, name, namespace, body, **kwargs) -> None:
    """
    Create or update a secret with sp
    """
    client_id = spec.get("clientId")
    client_secret_ref = spec.get("clientSecretRef")
    tenant_id = spec.get("tenantId")
    git_url = spec.get("gitUrl")
    secret_type = spec.get("secretType")
    if not all([client_id, client_secret_ref, tenant_id, git_url, secret_type]):
        raise kopf.PermanentError("client_id, client_secret_ref, tenant_id, git_url, and secret_type must be provided")
    try:
        client_secret = get_secret(client_secret_ref, namespace, body)
        if not client_secret:
            kopf.exception(body, reason="Token Error", message=f"Secret {client_secret_ref} not found")
            raise kopf.PermanentError(f"Secret {client_secret_ref} not found")
        token = get_auth_token(client_id, client_secret, tenant_id)
        create_update_secret(token, name, namespace, git_url, secret_type)
    except Exception as e:
        kopf.exception(body, reason="Token Error", message=f"Failed to get token {str(e)}")
        raise kopf.PermanentError(f"Failed to get token {str(e)}")

@kopf.timer('k8sware.com', 'v1', 'argocdsp', interval=3500, sharp=True, initial_delay=10, idle=10)
def refresh_secret(spec, name, namespace, body, **kwargs) -> None:
    """
    Refresh the secret every hour
    """
    create_update_argocdsp(spec, name, namespace, body, **kwargs)


@kopf.on.delete('k8sware.com', 'v1', 'argocdsp')
def create_delete_argocdsp(spec, name, namespace, body, **kwargs) -> None:
    """
    Delete the secret
    """
    deploy_namespace = "argocd"
    secret_name = f"{name}-{namespace}-{deploy_namespace}-token"
    api_instance = k8s_client.CoreV1Api()
    try:
        api_instance.delete_namespaced_secret(name=secret_name, namespace=deploy_namespace)
        kopf.info(body, reason="DeletedSecret", message=f"Secret {secret_name} deleted successfully.")
    except k8s_client.rest.ApiException as e:
        if e.status == 404:
            kopf.info(body, reason="SecretNotFound", message=f"Secret {secret_name} not found.")
        else:
            raise kopf.TemporaryError(f"Failed to delete secret {str(e)}", delay=10)