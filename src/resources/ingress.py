"""Ingress creation for workshops."""

from typing import Any, Dict
import kubernetes.client as k8s


def create_workshop_ingress(
    workshop_name: str, 
    namespace: str, 
    ingress_config: Dict[str, Any]
) -> k8s.V1Ingress:
    """
    Create a Kubernetes Ingress for a workshop.
    
    Args:
        workshop_name: Name of the workshop
        namespace: Kubernetes namespace
        ingress_config: Ingress configuration from workshop spec
        
    Returns:
        V1Ingress object ready to be created
    """
    host = ingress_config.get('host')
    annotations = ingress_config.get('annotations', {})
    
    # Default annotations for Traefik
    default_annotations = {
        'kubernetes.io/ingress.class': 'traefik'
    }
    default_annotations.update(annotations)
    
    ingress = k8s.V1Ingress(
        api_version='networking.k8s.io/v1',
        kind='Ingress',
        metadata=k8s.V1ObjectMeta(
            name=f"{workshop_name}-ingress",
            namespace=namespace,
            labels={
                'app': workshop_name,
                'component': 'rstudio'
            },
            annotations=default_annotations
        ),
        spec=k8s.V1IngressSpec(
            rules=[
                k8s.V1IngressRule(
                    host=host,
                    http=k8s.V1HTTPIngressRuleValue(
                        paths=[
                            k8s.V1HTTPIngressPath(
                                path='/',
                                path_type='Prefix',
                                backend=k8s.V1IngressBackend(
                                    service=k8s.V1IngressServiceBackend(
                                        name=f"{workshop_name}-service",
                                        port=k8s.V1ServiceBackendPort(
                                            number=80
                                        )
                                    )
                                )
                            )
                        ]
                    )
                )
            ]
        )
    )
    
    return ingress
