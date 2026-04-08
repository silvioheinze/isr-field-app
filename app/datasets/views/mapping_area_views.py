import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import GEOSException, MultiPolygon, Polygon
from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..models import DataSet, MappingArea


logger = logging.getLogger(__name__)


def _mapping_areas_disabled_response():
    return JsonResponse(
        {
            'success': False,
            'error': 'Mapping areas are not enabled for this dataset.',
        },
        status=403,
    )


def _serialize_mapping_area_outline(area):
    """GeoJSON payload for read-only map outlines (collaborators)."""
    if not area.geometry:
        return None
    geojson = area.geometry.geojson
    geometry_data = json.loads(geojson)
    return {
        'id': area.id,
        'name': area.name,
        'geometry': geometry_data,
    }


@login_required
def mapping_area_outlines_view(request, dataset_id):
    """
    Read-only polygon outlines for collaborators restricted to specific mapping areas.
    Owners/superusers get an empty list (they use the full mapping-areas API).
    """
    dataset = get_object_or_404(DataSet, id=dataset_id)
    if not dataset.can_access(request.user):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    if not getattr(dataset, 'enable_mapping_areas', False):
        return JsonResponse({'success': True, 'mapping_areas': []})
    if request.user.is_superuser or dataset.owner == request.user:
        return JsonResponse({'success': True, 'mapping_areas': []})

    allowed_ids = dataset.get_user_mapping_area_ids(request.user)
    if not allowed_ids:
        return JsonResponse({'success': True, 'mapping_areas': []})

    try:
        areas_qs = MappingArea.objects.filter(dataset=dataset, id__in=allowed_ids)
    except (ProgrammingError, OperationalError) as db_exc:
        logger.warning(
            "Database error while loading mapping area outlines for dataset %s: %s",
            dataset.id,
            db_exc,
        )
        return JsonResponse({'success': True, 'mapping_areas': []})

    areas_data = []
    for area in areas_qs:
        try:
            payload = _serialize_mapping_area_outline(area)
            if payload:
                areas_data.append(payload)
        except (ValueError, GEOSException, AttributeError) as exc:
            logger.exception(
                "Failed to serialise mapping area outline %s for dataset %s: %s",
                area.id,
                dataset.id,
                exc,
            )
    return JsonResponse({'success': True, 'mapping_areas': areas_data})


@login_required
def mapping_area_list_view(request, dataset_id):
    """Get list of all mapping areas for a dataset"""
    dataset = get_object_or_404(DataSet, id=dataset_id)

    if not getattr(dataset, 'enable_mapping_areas', False):
        return _mapping_areas_disabled_response()

    # Only dataset owner or superuser can access mapping areas
    if dataset.owner != request.user and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        mapping_areas = list(MappingArea.objects.filter(dataset=dataset))
    except (ProgrammingError, OperationalError) as db_exc:
        logger.warning(
            "Database error while loading mapping areas for dataset %s: %s",
            dataset.id,
            db_exc,
        )
        return JsonResponse(
            {
                'success': True,
                'mapping_areas': [],
                'warning': 'Mapping areas are temporarily unavailable. Please try again shortly.'
            }
        )
    try:
        areas_data = []
        for area in mapping_areas:
            try:
                if not area.geometry:
                    logger.warning(
                        "MappingArea %s for dataset %s has no geometry. Skipping.",
                        area.id,
                        dataset.id,
                    )
                    continue
                
                # Convert polygon to GeoJSON format
                geojson = area.geometry.geojson
                geometry_data = json.loads(geojson)
                
                areas_data.append({
                    'id': area.id,
                    'name': area.name,
                    'geometry': geometry_data,
                    'point_count': area.get_point_count(),
                    'allocated_users': [user.id for user in area.allocated_users.all()],
                    'allocated_user_names': [user.username for user in area.allocated_users.all()],
                    'created_at': area.created_at.isoformat(),
                    'created_by': area.created_by.username if area.created_by else None
                })
            except (ValueError, GEOSException, AttributeError) as exc:
                logger.exception(
                    "Failed to serialise mapping area %s for dataset %s: %s",
                    area.id,
                    dataset.id,
                    exc,
                )
                continue
        
        return JsonResponse({
            'success': True,
            'mapping_areas': areas_data
        })
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Unexpected error loading mapping areas for dataset %s: %s",
            dataset.id,
            exc,
        )
        return JsonResponse(
            {
                'success': True,
                'mapping_areas': [],
                'warning': 'Failed to load some mapping areas. Check server logs for details.'
            }
        )


@login_required
def mapping_area_create_view(request, dataset_id):
    """Create a new mapping area"""
    dataset = get_object_or_404(DataSet, id=dataset_id)

    if not getattr(dataset, 'enable_mapping_areas', False):
        return _mapping_areas_disabled_response()

    # Only dataset owner or superuser can create mapping areas
    if dataset.owner != request.user and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)
    
    name = (data.get('name') or '').strip()
    geometry_data = data.get('geometry')
    logger.debug(
        "Mapping area create payload for dataset %s by user %s: name=%s, has_geometry=%s, allocated_users=%s",
        dataset.id,
        request.user.id,
        name,
        bool(geometry_data),
        data.get('allocated_users'),
    )
    
    if not name:
        return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
    
    if not geometry_data or geometry_data.get('type') not in ('Polygon', 'MultiPolygon'):
        return JsonResponse({'success': False, 'error': 'Invalid geometry'}, status=400)
    
    try:
        geos_multipolygon = multipolygon_from_geojson_dict(geometry_data)
    except ValueError as exc:
        logger.warning("Invalid mapping area geometry for dataset %s: %s", dataset.id, exc)
        return JsonResponse({'success': False, 'error': 'Invalid polygon coordinates.'}, status=400)
    except (TypeError, GEOSException) as exc:
        logger.exception("Invalid polygon data for dataset %s: %s", dataset.id, exc)
        return JsonResponse({'success': False, 'error': 'Invalid polygon coordinates.'}, status=400)
    
    try:
        mapping_area = MappingArea.objects.create(
            dataset=dataset,
            name=name,
            geometry=geos_multipolygon,
            created_by=request.user
        )
        
        allocated_user_ids = data.get('allocated_users', [])
        if allocated_user_ids:
            from django.contrib.auth.models import User
            users = User.objects.filter(id__in=allocated_user_ids, is_active=True)
            mapping_area.allocated_users.set(users)
        
        logger.debug(
            "Mapping area created successfully: id=%s for dataset %s (allocated_users=%s)",
            mapping_area.id,
            dataset.id,
            list(mapping_area.allocated_users.values_list('id', flat=True)),
        )

        return JsonResponse({
            'success': True,
            'message': f'Mapping area "{name}" created successfully',
            'mapping_area': {
                'id': mapping_area.id,
                'name': mapping_area.name,
                'point_count': mapping_area.get_point_count(),
                'allocated_users': [user.id for user in mapping_area.allocated_users.all()],
                'allocated_user_names': [user.username for user in mapping_area.allocated_users.all()]
            }
        })
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error creating mapping area for dataset %s: %s", dataset.id, exc)
        return JsonResponse({'success': False, 'error': 'Failed to create mapping area.'})


@login_required
def mapping_area_update_view(request, dataset_id, area_id):
    """Update an existing mapping area"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    mapping_area = get_object_or_404(MappingArea, id=area_id, dataset=dataset)

    if not getattr(dataset, 'enable_mapping_areas', False):
        return _mapping_areas_disabled_response()

    # Only dataset owner or superuser can update mapping areas
    if dataset.owner != request.user and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)
    
    name = data.get('name')
    geometry_data = data.get('geometry')
    allocated_user_ids = data.get('allocated_users')
    logger.debug(
        "Mapping area update payload for dataset %s (area %s) by user %s: name=%s, has_geometry=%s, allocated_users=%s",
        dataset.id,
        mapping_area.id,
        request.user.id,
        name,
        bool(geometry_data),
        allocated_user_ids,
    )
    
    if name is not None:
        mapping_area.name = name.strip()
    
    if geometry_data:
        if geometry_data.get('type') not in ('Polygon', 'MultiPolygon'):
            return JsonResponse({'success': False, 'error': 'Invalid geometry'}, status=400)
        try:
            mapping_area.geometry = multipolygon_from_geojson_dict(geometry_data)
        except ValueError as exc:
            logger.warning("Invalid mapping area geometry while updating area %s: %s", mapping_area.id, exc)
            return JsonResponse({'success': False, 'error': 'Invalid polygon coordinates.'}, status=400)
        except (TypeError, GEOSException) as exc:
            logger.exception("Invalid polygon data while updating mapping area %s: %s", mapping_area.id, exc)
            return JsonResponse({'success': False, 'error': 'Invalid polygon coordinates.'}, status=400)
    
    try:
        mapping_area.save()
        
        if allocated_user_ids is not None:
            from django.contrib.auth.models import User
            users = User.objects.filter(id__in=allocated_user_ids, is_active=True)
            mapping_area.allocated_users.set(users)
        
        logger.debug(
            "Mapping area updated successfully: id=%s for dataset %s (allocated_users=%s)",
            mapping_area.id,
            dataset.id,
            list(mapping_area.allocated_users.values_list('id', flat=True)),
        )

        return JsonResponse({
            'success': True,
            'message': f'Mapping area "{mapping_area.name}" updated successfully',
            'mapping_area': {
                'id': mapping_area.id,
                'name': mapping_area.name,
                'point_count': mapping_area.get_point_count(),
                'allocated_users': [user.id for user in mapping_area.allocated_users.all()],
                'allocated_user_names': [user.username for user in mapping_area.allocated_users.all()]
            }
        })
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error updating mapping area %s: %s", mapping_area.id, exc)
        return JsonResponse({'success': False, 'error': 'Failed to update mapping area.'})


@login_required
def mapping_area_delete_view(request, dataset_id, area_id):
    """Delete a mapping area"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    mapping_area = get_object_or_404(MappingArea, id=area_id, dataset=dataset)

    if not getattr(dataset, 'enable_mapping_areas', False):
        return _mapping_areas_disabled_response()

    # Only dataset owner or superuser can delete mapping areas
    if dataset.owner != request.user and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        try:
            area_name = mapping_area.name
            mapping_area.delete()
            return JsonResponse({
                'success': True,
                'message': f'Mapping area "{area_name}" deleted successfully'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

