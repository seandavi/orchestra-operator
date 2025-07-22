"""Workshop event handlers for the Orchestra Operator."""

import logging
from typing import Any, Dict, Optional

import kopf
import kubernetes.client as k8s_client
from kubernetes.client.rest import ApiException

from resources.deployment import create_rstudio_deployment
from resources.service import create_workshop_service  
from resources.ingress import create_workshop_ingress
from resources.pvc import create_workshop_pvc
from utils.time_utils import parse_duration, get_expiration_time


logger = logging.getLogger(__name__)


def register_workshop_handlers() -> None:
    """Register all workshop-related Kopf handlers."""
    # Handlers are registered via decorators below
    pass


@kopf.on.create('orchestra.io', 'v1', 'workshops')
async def workshop_create_handler(
    spec: Dict[str, Any],
    meta: Dict[str, Any], 
    status: Dict[str, Any],
    namespace: str,
    name: str,
    **kwargs: Any
) -> Dict[str, Any]:
    """Handle Workshop creation events."""
    logger.info(f"Creating workshop {name} in namespace {namespace}")
    
    try:
        # Update status to Creating
        await update_workshop_status(namespace, name, "Creating", "Workshop creation started")
        
        # Extract workshop configuration
        workshop_name = spec.get('name', name)
        duration = spec.get('duration', '4h')
        image = spec.get('image', 'rocker/rstudio:latest')
        resources = spec.get('resources', {})
        storage = spec.get('storage', {})
        ingress_config = spec.get('ingress', {})
        
        # Calculate expiration time
        expiration_time = get_expiration_time(duration)
        
        # Create Kubernetes client
        k8s_apps_v1 = k8s_client.AppsV1Api()
        k8s_core_v1 = k8s_client.CoreV1Api()
        k8s_networking_v1 = k8s_client.NetworkingV1Api()
        
        # Create PersistentVolumeClaim for workshop data
        if storage:
            try:
                pvc = create_workshop_pvc(workshop_name, namespace, storage)
                k8s_core_v1.create_namespaced_persistent_volume_claim(
                    namespace=namespace, body=pvc
                )
                logger.info(f"Created PVC for workshop {workshop_name}")
            except ApiException as e:
                if e.status == 409:  # Already exists
                    logger.info(f"PVC for workshop {workshop_name} already exists")
                else:
                    raise
        
        # Create Deployment for RStudio
        try:
            deployment = create_rstudio_deployment(
                workshop_name, namespace, image, resources, storage
            )
            k8s_apps_v1.create_namespaced_deployment(
                namespace=namespace, body=deployment
            )
            logger.info(f"Created deployment for workshop {workshop_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"Deployment for workshop {workshop_name} already exists")
            else:
                raise
        
        # Create Service
        try:
            service = create_workshop_service(workshop_name, namespace)
            k8s_core_v1.create_namespaced_service(
                namespace=namespace, body=service
            )
            logger.info(f"Created service for workshop {workshop_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"Service for workshop {workshop_name} already exists")
            else:
                raise
        
        # Create Ingress (if configured)
        workshop_url = None
        if ingress_config.get('host'):
            try:
                ingress = create_workshop_ingress(workshop_name, namespace, ingress_config)
                k8s_networking_v1.create_namespaced_ingress(
                    namespace=namespace, body=ingress
                )
                workshop_url = f"https://{ingress_config['host']}"
                logger.info(f"Created ingress for workshop {workshop_name}")
            except ApiException as e:
                if e.status == 409:  # Already exists
                    workshop_url = f"https://{ingress_config['host']}"
                    logger.info(f"Ingress for workshop {workshop_name} already exists")
                else:
                    raise
        
        # Update status to Ready
        return {
            'phase': 'Ready',
            'url': workshop_url,
            'createdAt': kwargs.get('created', ''),
            'expiresAt': expiration_time.isoformat(),
            'conditions': [{
                'type': 'Ready',
                'status': 'True',
                'reason': 'WorkshopCreated',
                'message': 'Workshop resources created successfully'
            }]
        }
        
    except Exception as e:
        logger.error(f"Failed to create workshop {name}: {e}")
        return {
            'phase': 'Failed',
            'conditions': [{
                'type': 'Ready', 
                'status': 'False',
                'reason': 'CreationFailed',
                'message': str(e)
            }]
        }


@kopf.on.update('orchestra.io', 'v1', 'workshops')
async def workshop_update_handler(
    spec: Dict[str, Any],
    meta: Dict[str, Any],
    status: Dict[str, Any], 
    namespace: str,
    name: str,
    **kwargs: Any
) -> Dict[str, Any]:
    """Handle Workshop update events."""
    logger.info(f"Updating workshop {name} in namespace {namespace}")
    
    # For now, we'll just log updates
    # In the future, we might support scaling or configuration changes
    return {'phase': status.get('phase', 'Ready')}


@kopf.on.delete('orchestra.io', 'v1', 'workshops')
async def workshop_delete_handler(
    meta: Dict[str, Any],
    namespace: str, 
    name: str,
    **kwargs: Any
) -> None:
    """Handle Workshop deletion events."""
    logger.info(f"Deleting workshop {name} in namespace {namespace}")
    
    try:
        workshop_name = meta.get('name', name)
        
        # Create Kubernetes clients
        k8s_apps_v1 = k8s_client.AppsV1Api()
        k8s_core_v1 = k8s_client.CoreV1Api()
        k8s_networking_v1 = k8s_client.NetworkingV1Api()
        
        # Delete in reverse order: Ingress -> Service -> Deployment -> PVC
        
        # Delete Ingress
        try:
            k8s_networking_v1.delete_namespaced_ingress(
                name=f"{workshop_name}-ingress", namespace=namespace
            )
            logger.info(f"Deleted ingress for workshop {workshop_name}")
        except ApiException as e:
            if e.status != 404:  # Ignore not found errors
                logger.warning(f"Failed to delete ingress: {e}")
        
        # Delete Service  
        try:
            k8s_core_v1.delete_namespaced_service(
                name=f"{workshop_name}-service", namespace=namespace
            )
            logger.info(f"Deleted service for workshop {workshop_name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete service: {e}")
                
        # Delete Deployment
        try:
            k8s_apps_v1.delete_namespaced_deployment(
                name=f"{workshop_name}-deployment", namespace=namespace
            )
            logger.info(f"Deleted deployment for workshop {workshop_name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete deployment: {e}")
        
        # Delete PVC (optionally preserve data by commenting this out)
        try:
            k8s_core_v1.delete_namespaced_persistent_volume_claim(
                name=f"{workshop_name}-pvc", namespace=namespace
            )
            logger.info(f"Deleted PVC for workshop {workshop_name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete PVC: {e}")
        
    except Exception as e:
        logger.error(f"Failed to delete workshop {name}: {e}")
        raise kopf.PermanentError(f"Workshop deletion failed: {e}")


async def update_workshop_status(
    namespace: str, 
    name: str, 
    phase: str, 
    message: str
) -> None:
    """Update the status of a Workshop resource."""
    # This would update the Workshop's status field
    # Implementation depends on how Kopf handles status updates
    logger.info(f"Workshop {name} status: {phase} - {message}")
